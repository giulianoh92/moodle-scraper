"""Descarga de archivos binarios desde Moodle."""

import logging
import re
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from config import ADJUNTOS_PATH, DOWNLOAD_DELAY, BINARY_EXTENSIONS

logger = logging.getLogger(__name__)


def get_filename_from_response(resp, url: str) -> str:
    """Extrae el nombre de archivo del header Content-Disposition o la URL."""
    # Intentar Content-Disposition
    cd = resp.headers.get("Content-Disposition", "")
    if cd:
        # filename*=UTF-8''nombre.pdf
        match = re.search(r"filename\*=(?:UTF-8''|utf-8'')(.+)", cd)
        if match:
            return unquote(match.group(1)).strip()
        # filename="nombre.pdf"
        match = re.search(r'filename="?([^";\n]+)"?', cd)
        if match:
            return unquote(match.group(1)).strip()

    # Fallback: extraer de la URL
    parsed = urlparse(url)
    path = unquote(parsed.path)
    name = path.split("/")[-1]
    if name and "." in name:
        return name

    return ""


def is_binary_file(filename: str) -> bool:
    """Determina si un archivo es binario basado en su extensión."""
    ext = Path(filename).suffix.lower()
    return ext in BINARY_EXTENSIONS


def download_file(session, url: str, materia: str, prefix: str = "") -> dict:
    """Descarga un archivo de Moodle.

    Args:
        session: Sesión HTTP autenticada.
        url: URL del archivo a descargar.
        materia: Nombre de la materia (para organizar en carpetas).
        prefix: Prefijo opcional para el nombre del archivo.

    Returns:
        Dict con 'path', 'filename', 'skipped', 'error'.
    """
    result = {"path": None, "filename": "", "skipped": False, "error": None}

    if not url:
        result["error"] = "URL vacía"
        return result

    try:
        # Para recursos tipo mod/resource, seguimos el redirect al archivo real
        resp = session.get(url, stream=True, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        result["error"] = str(e)
        logger.error("Error descargando %s: %s", url, e)
        return result

    # Rechazar si la respuesta es HTML (no es un archivo real)
    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        result["error"] = "Recurso devuelve HTML, no es un archivo descargable"
        logger.warning("  ⚠ Recurso no descargable (HTML): %s", url)
        return result

    # Determinar nombre del archivo
    filename = get_filename_from_response(resp, resp.url)
    if not filename:
        result["error"] = "No se pudo determinar nombre de archivo"
        logger.warning("Sin nombre de archivo para: %s", url)
        return result

    if prefix:
        filename = f"{prefix} - {filename}"

    result["filename"] = filename

    # Crear directorio destino
    dest_dir = ADJUNTOS_PATH / materia
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    # Idempotencia: no re-descargar si ya existe
    if dest_path.exists():
        result["path"] = dest_path
        result["skipped"] = True
        logger.info("  ⏭ Ya existe: %s", filename)
        return result

    # Descargar
    logger.info("  ⬇ Descargando: %s", filename)
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    result["path"] = dest_path
    time.sleep(DOWNLOAD_DELAY)
    return result


def resolve_file_url(session, resource_url: str) -> str:
    """Resuelve la URL real de un archivo desde una página mod/resource.

    Moodle a veces redirige automáticamente al archivo, pero a veces
    muestra una página intermedia con el link de descarga.
    """
    try:
        resp = session.head(resource_url, allow_redirects=True)
        content_type = resp.headers.get("Content-Type", "")

        # Si ya es un archivo binario (no HTML), la URL del redirect es el archivo
        if "text/html" not in content_type:
            return resp.url

        # Si es HTML, buscar el link de descarga en la página
        resp = session.get(resource_url)
        resp.raise_for_status()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Buscar link al archivo
        for link in soup.select("a.btn, .resourceworkaround a, a[href*='pluginfile.php']"):
            href = link.get("href", "")
            if "/pluginfile.php/" in href or "/webservice/pluginfile.php/" in href:
                return href

        # El redirect original podría ser suficiente
        return resp.url

    except Exception as e:
        logger.warning("Error resolviendo URL %s: %s", resource_url, e)
        return resource_url
