"""Extracción y conversión de contenido HTML a Markdown."""

import logging
import re
import time

from bs4 import BeautifulSoup
from markdownify import markdownify as md

from config import MOODLE_BASE, MATERIAS_PATH, REQUEST_DELAY

logger = logging.getLogger(__name__)


def extract_page_content(session, page_url: str) -> dict:
    """Extrae el contenido de una página Moodle (mod/page) como Markdown.

    Returns:
        Dict con 'title', 'markdown', 'error'.
    """
    result = {"title": "", "markdown": "", "error": None}

    try:
        time.sleep(REQUEST_DELAY)
        resp = session.get(page_url)
        resp.raise_for_status()
    except Exception as e:
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Título de la página
    title_el = soup.select_one(
        "h2.page-title, .page-header-headings h1, #page-header h1, "
        ".breadcrumb-item:last-child"
    )
    if title_el:
        result["title"] = title_el.get_text(strip=True)

    # Contenido principal
    content_el = soup.select_one(
        "#region-main .box.generalbox .no-overflow, "
        "#region-main .box.generalbox, "
        ".book_content, "
        "#page-content .box.generalbox"
    )

    if not content_el:
        # Fallback: buscar el contenido principal
        content_el = soup.select_one("#region-main")

    if not content_el:
        result["error"] = "No se encontró contenido en la página"
        return result

    # Limpiar HTML antes de convertir
    _clean_html(content_el)

    # Convertir a Markdown
    markdown = md(
        str(content_el),
        heading_style="ATX",
        bullets="-",
        strip=["script", "style", "nav"],
    )

    # Post-procesar markdown
    markdown = _clean_markdown(markdown)
    result["markdown"] = markdown

    return result


def extract_assign_content(session, assign_url: str) -> dict:
    """Extrae el enunciado y archivos de una tarea (mod/assign).

    Returns:
        Dict con 'title', 'markdown', 'files' (lista de URLs), 'error'.
    """
    result = {"title": "", "markdown": "", "files": [], "error": None}

    try:
        time.sleep(REQUEST_DELAY)
        resp = session.get(assign_url)
        resp.raise_for_status()
    except Exception as e:
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Título
    title_el = soup.select_one("h2, .page-header-headings h1")
    if title_el:
        result["title"] = title_el.get_text(strip=True)

    # Descripción del enunciado
    desc_el = soup.select_one(".assign-description, .submissionstatustable")
    if desc_el:
        _clean_html(desc_el)
        result["markdown"] = md(str(desc_el), heading_style="ATX", bullets="-")

    # Archivos adjuntos al enunciado
    for link in soup.select(".fileuploadsubmission a, .introattachment a, a[href*='pluginfile.php']"):
        href = link.get("href", "")
        if "/pluginfile.php/" in href:
            result["files"].append(href)

    return result


def save_page_as_markdown(
    title: str, markdown: str, materia: str, frontmatter: dict | None = None
) -> str | None:
    """Guarda contenido Markdown como archivo en Recursos/.

    Returns:
        Path del archivo creado, o None si ya existe.
    """
    # Sanitizar nombre de archivo
    safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
    safe_title = safe_title.strip(". ")
    if not safe_title:
        safe_title = "Página sin título"

    dest_dir = MATERIAS_PATH / materia / "Recursos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{safe_title}.md"

    # No sobreescribir archivos existentes que no fueron creados por el scraper
    if dest_path.exists():
        content = dest_path.read_text(encoding="utf-8")
        if "fuente: Moodle" not in content and "moodle-scraper" not in content:
            logger.info("  ⏭ Archivo existente (manual): %s", safe_title)
            return None
        # Si fue creado por el scraper, actualizar
        logger.info("  🔄 Actualizando: %s", safe_title)
    else:
        logger.info("  📝 Creando: %s.md", safe_title)

    # Construir contenido con frontmatter
    fm = frontmatter or {}
    lines = [
        "---",
        f"tipo: recurso",
        f"materia: {materia}",
        f"fuente: Moodle - Campus Virtual UGD",
        f"tags:",
        f"  - referencia",
        f"  - moodle",
    ]
    for key, value in fm.items():
        if key not in ("tipo", "materia", "fuente", "tags"):
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(markdown)
    lines.append("")

    dest_path.write_text("\n".join(lines), encoding="utf-8")
    return str(dest_path)


def _clean_html(element):
    """Limpia elementos HTML innecesarios antes de la conversión."""
    # Quitar scripts, styles, navigation
    for tag in element.find_all(["script", "style", "nav", "footer"]):
        tag.decompose()

    # Quitar elementos de UI de Moodle
    for selector in [".activity-navigation", ".activity-header",
                     ".modified-info", ".singlebutton", ".editing_",
                     "#page-footer", ".logininfo"]:
        for el in element.select(selector):
            el.decompose()


def _clean_markdown(text: str) -> str:
    """Post-procesa el markdown generado para limpiarlo."""
    # Quitar líneas vacías excesivas
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    # Quitar espacios trailing
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Quitar líneas vacías al inicio y final
    text = text.strip()
    return text
