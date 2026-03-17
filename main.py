#!/usr/bin/env python3
"""Moodle Scraper → Obsidian Vault.

Descarga todos los recursos de cursos Moodle y los organiza
en la estructura del vault de Obsidian.
"""

import argparse
import logging
import sys
import time

from config import REQUEST_DELAY

sys.path.insert(0, ".")
from scraper.auth import create_session
from scraper.discovery import discover_courses, Course
from scraper.crawler import crawl_course, crawl_folder, resolve_url_resource
from scraper.downloader import download_file, resolve_file_url
from scraper.extractor import extract_page_content, extract_assign_content, save_page_as_markdown
from scraper.organizer import generate_index
from scraper.manifest import (
    load_manifest, save_manifest, is_resource_known,
    record_resource, get_url_resolution, record_url_resolution,
)

logger = logging.getLogger("moodle-scraper")

# Manifiesto global — cargado una vez, guardado al final
_manifest = {}


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def process_course(session, course: Course) -> dict:
    """Procesa un curso completo: crawl, descarga, extracción, organización."""
    stats = {
        "downloaded": 0,
        "skipped": 0,
        "pages_created": 0,
        "errors": 0,
        "sections": 0,
        "total_resources": 0,
    }

    materia = course.materia
    if not materia:
        logger.warning("Curso '%s' no tiene mapeo al vault — omitiendo", course.name)
        return stats

    logger.info("=" * 60)
    logger.info("Procesando: %s → %s", course.name, materia)
    logger.info("=" * 60)

    structure = crawl_course(session, course.id, course.name)
    stats["sections"] = len(structure.sections)

    sections_data = []

    for section in structure.sections:
        section_data = {
            "number": section.number,
            "title": section.title,
            "resources": [],
            "labels": section.labels,
        }

        for resource in section.resources:
            stats["total_resources"] += 1
            res_data = {
                "name": resource.name,
                "type": resource.resource_type,
                "filename": None,
                "url": resource.url,
                "page_file": None,
                "description": resource.description,
            }

            # === MANIFIESTO: verificar si ya fue procesado ===
            cached = is_resource_known(_manifest, resource.url) if resource.url else None
            if cached and cached.get("action") != "error":
                # Recurso ya conocido — usar info cacheada
                res_data["filename"] = cached.get("filename")
                res_data["page_file"] = cached.get("page_file")
                res_data["url"] = cached.get("target_url", resource.url)
                if cached.get("type"):
                    res_data["type"] = cached["type"]
                stats["skipped"] += 1
                logger.info("  ⏭ [cache] %s", resource.name)

                section_data["resources"].append(res_data)
                # Para carpetas, agregar los archivos individuales
                if cached.get("action") == "folder":
                    for f in cached.get("folder_files", []):
                        section_data["resources"].append({
                            "name": f["filename"],
                            "type": "file",
                            "filename": f["filename"],
                            "url": None,
                            "page_file": None,
                            "description": f"(desde carpeta: {resource.name})",
                        })
                continue

            # === Recurso nuevo — procesar con HTTP ===
            time.sleep(REQUEST_DELAY)

            if resource.resource_type == "file":
                result = _process_file(session, resource, materia)
                res_data["filename"] = result.get("filename")
                if result.get("error"):
                    stats["errors"] += 1
                    record_resource(_manifest, resource.url, {
                        "action": "error", "error": result["error"],
                    })
                else:
                    if result.get("skipped"):
                        stats["skipped"] += 1
                    else:
                        stats["downloaded"] += 1
                    record_resource(_manifest, resource.url, {
                        "action": "downloaded", "filename": result.get("filename"),
                        "type": "file", "materia": materia,
                    })

            elif resource.resource_type == "folder":
                folder_results = _process_folder(session, resource, materia)
                folder_files = []
                for fr in folder_results:
                    if fr.get("error"):
                        stats["errors"] += 1
                    elif fr.get("skipped"):
                        stats["skipped"] += 1
                    else:
                        stats["downloaded"] += 1
                    if fr.get("filename"):
                        folder_files.append({"filename": fr["filename"]})
                        section_data["resources"].append({
                            "name": fr["filename"],
                            "type": "file",
                            "filename": fr["filename"],
                            "url": None,
                            "page_file": None,
                            "description": f"(desde carpeta: {resource.name})",
                        })
                record_resource(_manifest, resource.url, {
                    "action": "folder", "folder_files": folder_files,
                    "type": "folder", "materia": materia,
                })
                continue

            elif resource.resource_type == "page":
                result = _process_page(session, resource, materia)
                res_data["page_file"] = result.get("path")
                if result.get("error"):
                    stats["errors"] += 1
                    record_resource(_manifest, resource.url, {
                        "action": "error", "error": result["error"],
                    })
                else:
                    stats["pages_created"] += 1
                    record_resource(_manifest, resource.url, {
                        "action": "page", "page_file": result.get("path"),
                        "type": "page", "materia": materia,
                    })

            elif resource.resource_type == "assign":
                result = _process_assign(session, resource, materia)
                res_data["page_file"] = result.get("path")
                for fr in result.get("files_downloaded", []):
                    if fr.get("error"):
                        stats["errors"] += 1
                    elif fr.get("skipped"):
                        stats["skipped"] += 1
                    else:
                        stats["downloaded"] += 1
                record_resource(_manifest, resource.url, {
                    "action": "assign", "page_file": result.get("path"),
                    "type": "assign", "materia": materia,
                })

            elif resource.resource_type == "url":
                result = _process_url(session, resource, materia)
                if result.get("resolved_as") == "file":
                    res_data["filename"] = result.get("filename")
                    res_data["type"] = "file"
                    if result.get("error"):
                        stats["errors"] += 1
                    elif result.get("skipped"):
                        stats["skipped"] += 1
                    else:
                        stats["downloaded"] += 1
                    record_resource(_manifest, resource.url, {
                        "action": "downloaded", "filename": result.get("filename"),
                        "type": "file", "materia": materia,
                    })
                elif result.get("resolved_as") == "page":
                    res_data["page_file"] = result.get("path")
                    res_data["type"] = "page"
                    if result.get("error"):
                        stats["errors"] += 1
                    else:
                        stats["pages_created"] += 1
                    record_resource(_manifest, resource.url, {
                        "action": "page", "page_file": result.get("path"),
                        "type": "page", "materia": materia,
                    })
                elif result.get("target_url"):
                    res_data["url"] = result["target_url"]
                    record_resource(_manifest, resource.url, {
                        "action": "external", "target_url": result["target_url"],
                        "type": "url", "materia": materia,
                    })
                elif result.get("error"):
                    record_resource(_manifest, resource.url, {
                        "action": "error", "error": result.get("error"),
                    })

            elif resource.resource_type == "label":
                pass

            section_data["resources"].append(res_data)

        sections_data.append(section_data)

    if sections_data:
        generate_index(materia, sections_data)

    return stats


def _process_file(session, resource, materia: str) -> dict:
    url = resolve_file_url(session, resource.url)
    return download_file(session, url, materia)


def _process_folder(session, resource, materia: str) -> list[dict]:
    files = crawl_folder(session, resource.url)
    results = []
    for f in files:
        result = download_file(session, f["url"], materia)
        results.append(result)
    return results


def _process_page(session, resource, materia: str) -> dict:
    content = extract_page_content(session, resource.url)
    result = {"path": None, "error": content.get("error")}
    if content["markdown"]:
        title = content["title"] or resource.name
        path = save_page_as_markdown(title, content["markdown"], materia)
        result["path"] = path
    return result


def _process_url(session, resource, materia: str) -> dict:
    # Verificar cache de resolución de URL
    cached_res = get_url_resolution(_manifest, resource.url)
    if cached_res:
        resolved = cached_res
    else:
        resolved = resolve_url_resource(session, resource.url)
        record_url_resolution(_manifest, resource.url, resolved)

    result = {
        "resolved_as": None,
        "target_url": resolved.get("target_url", ""),
        "filename": None,
        "path": None,
        "error": resolved.get("error"),
        "skipped": False,
    }

    if resolved.get("error"):
        logger.warning("  No se pudo resolver URL '%s': %s", resource.name, resolved["error"])
        return result

    target = resolved["target_url"]
    rtype = resolved.get("resolved_type", "external")

    if rtype == "file":
        logger.info("  URL '%s' → archivo interno, descargando...", resource.name)
        result["resolved_as"] = "file"
        file_url = resolve_file_url(session, target)
        dl = download_file(session, file_url, materia)
        result["filename"] = dl.get("filename")
        result["error"] = dl.get("error")
        result["skipped"] = dl.get("skipped", False)
    elif rtype == "page":
        logger.info("  URL '%s' → página interna, extrayendo...", resource.name)
        result["resolved_as"] = "page"
        content = extract_page_content(session, target)
        result["error"] = content.get("error")
        if content.get("markdown"):
            title = content.get("title") or resource.name
            result["path"] = save_page_as_markdown(title, content["markdown"], materia)
    elif rtype == "folder":
        logger.info("  URL '%s' → carpeta interna", resource.name)
        result["target_url"] = target
    else:
        logger.info("  URL '%s' → externo: %s", resource.name, target)
        result["target_url"] = target

    return result


def _process_assign(session, resource, materia: str) -> dict:
    content = extract_assign_content(session, resource.url)
    result = {"path": None, "files_downloaded": [], "error": content.get("error")}
    if content["markdown"]:
        title = content["title"] or resource.name
        path = save_page_as_markdown(
            title, content["markdown"], materia,
            frontmatter={"tipo": "recurso"},
        )
        result["path"] = path
    for file_url in content.get("files", []):
        fr = download_file(session, file_url, materia)
        result["files_downloaded"].append(fr)
    return result


def main():
    global _manifest

    parser = argparse.ArgumentParser(
        description="Moodle Scraper → Obsidian Vault"
    )
    parser.add_argument(
        "-c", "--course-id",
        help="ID específico de un curso a procesar (omitir para todos)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostrar logs de debug",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo crawlear y mostrar estructura, sin descargar",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignorar manifiesto y re-procesar todo",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Cargar manifiesto (cache de recursos procesados)
    if args.force:
        _manifest = {"resources": {}, "url_resolutions": {}}
        logger.info("Modo --force: ignorando manifiesto anterior")
    else:
        _manifest = load_manifest()
        cached_count = len(_manifest.get("resources", {}))
        if cached_count:
            logger.info("Manifiesto cargado: %d recursos conocidos", cached_count)

    # 1. Autenticación
    logger.info("Iniciando sesión en Moodle...")
    try:
        session = create_session()
    except RuntimeError as e:
        logger.error("Error de autenticación: %s", e)
        sys.exit(1)

    # 2. Descubrimiento de cursos
    logger.info("Descubriendo cursos matriculados...")
    courses = discover_courses(session)

    if not courses:
        logger.error("No se encontraron cursos. Verificá las credenciales.")
        sys.exit(1)

    if args.course_id:
        courses = [c for c in courses if c.id == args.course_id]
        if not courses:
            logger.error("No se encontró el curso con ID %s", args.course_id)
            sys.exit(1)

    mapped = [c for c in courses if c.materia]
    unmapped = [c for c in courses if not c.materia]

    if unmapped:
        logger.warning(
            "Cursos sin mapeo al vault (ignorados): %s",
            ", ".join(c.name for c in unmapped),
        )

    if not mapped:
        logger.error("Ningún curso tiene mapeo al vault. Revisá COURSE_MAP en config.py")
        sys.exit(1)

    # 3. Dry run
    if args.dry_run:
        logger.info("\n=== DRY RUN — Solo mostrando estructura ===\n")
        for course in mapped:
            structure = crawl_course(session, course.id, course.name)
            for section in structure.sections:
                logger.info("  [Sección %d] %s", section.number, section.title)
                for res in section.resources:
                    cached = is_resource_known(_manifest, res.url) if res.url else None
                    marker = " [cache]" if cached else " [NEW]"
                    logger.info("    - [%s]%s %s", res.resource_type, marker, res.name)
                for label in section.labels:
                    logger.info("    - [label] %s", label[:80])
            time.sleep(REQUEST_DELAY)
        sys.exit(0)

    # 4. Procesar cursos
    total_stats = {
        "downloaded": 0,
        "skipped": 0,
        "pages_created": 0,
        "errors": 0,
        "courses_processed": 0,
    }

    for course in mapped:
        stats = process_course(session, course)
        total_stats["downloaded"] += stats["downloaded"]
        total_stats["skipped"] += stats["skipped"]
        total_stats["pages_created"] += stats["pages_created"]
        total_stats["errors"] += stats["errors"]
        total_stats["courses_processed"] += 1
        # Guardar manifiesto después de cada curso (por si se interrumpe)
        save_manifest(_manifest)

    # 5. Guardar manifiesto final
    save_manifest(_manifest)

    # 6. Resumen
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN")
    logger.info("=" * 60)
    logger.info("Cursos procesados:    %d", total_stats["courses_processed"])
    logger.info("Archivos descargados: %d (nuevos)", total_stats["downloaded"])
    logger.info("Recursos omitidos:    %d (ya en cache/disco)", total_stats["skipped"])
    logger.info("Páginas creadas:      %d", total_stats["pages_created"])
    logger.info("Errores:              %d", total_stats["errors"])


if __name__ == "__main__":
    main()
