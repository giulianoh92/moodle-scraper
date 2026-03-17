"""Crawling de estructura de un curso Moodle."""

import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from config import MOODLE_BASE, REQUEST_DELAY

logger = logging.getLogger(__name__)


@dataclass
class Resource:
    """Un recurso individual dentro de una sección del curso."""
    name: str
    url: str
    resource_type: str  # file, folder, page, url, forum, assign, label, unknown
    description: str = ""  # texto descriptivo/etiqueta


@dataclass
class Section:
    """Una sección/tema del curso."""
    number: int
    title: str
    resources: list[Resource] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)  # texto de etiquetas


@dataclass
class CourseStructure:
    """Estructura completa de un curso."""
    course_id: str
    course_name: str
    sections: list[Section] = field(default_factory=list)


# Mapeo de mod paths a tipos de recurso
MOD_TYPE_MAP = {
    "resource": "file",
    "folder": "folder",
    "page": "page",
    "url": "url",
    "forum": "forum",
    "assign": "assign",
    "quiz": "quiz",
    "label": "label",
    "book": "page",
    "lesson": "page",
}


def detect_resource_type(url: str) -> str:
    """Detecta el tipo de recurso a partir de la URL del mod."""
    for mod_path, rtype in MOD_TYPE_MAP.items():
        if f"/mod/{mod_path}/" in url:
            return rtype
    if "/pluginfile.php/" in url:
        return "file"
    return "unknown"


def _discover_section_count(session, course_id: str) -> int:
    """Descubre cuántas secciones tiene un curso mirando los links de navegación."""
    url = f"{MOODLE_BASE}/course/view.php?id={course_id}"
    try:
        resp = session.get(url)
        resp.raise_for_status()
    except Exception:
        return 10  # fallback

    soup = BeautifulSoup(resp.text, "html.parser")
    sections = {0}  # sección 0 siempre existe

    for link in soup.find_all("a", href=re.compile(r"section=\d+")):
        match = re.search(r"section=(\d+)", link["href"])
        if match:
            sections.add(int(match.group(1)))

    return max(sections) + 1 if sections else 10


def crawl_course(session, course_id: str, course_name: str) -> CourseStructure:
    """Crawlea la estructura completa de un curso iterando todas las secciones.

    Moodle puede mostrar solo una sección a la vez, así que navega
    cada sección individualmente via ?id=X&section=N.

    Args:
        session: Sesión HTTP autenticada.
        course_id: ID del curso en Moodle.
        course_name: Nombre del curso.

    Returns:
        CourseStructure con todas las secciones y recursos.
    """
    base_url = f"{MOODLE_BASE}/course/view.php?id={course_id}"
    logger.info("Crawleando curso: %s (%s)", course_name, base_url)

    structure = CourseStructure(
        course_id=course_id,
        course_name=course_name,
    )

    # Paso 1: Descubrir cuántas secciones tiene el curso usando AJAX
    num_sections = _discover_section_count(session, course_id)
    logger.info("  Secciones a explorar: %d", num_sections)

    # Rastrear URLs de recursos ya vistos para deduplicar globales
    global_urls = set()
    global_labels = set()

    for sec_num in range(num_sections):
        url = f"{base_url}&section={sec_num}"
        time.sleep(REQUEST_DELAY)

        try:
            resp = session.get(url)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("  Error en sección %d: %s", sec_num, e)
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        section_elements = soup.select("li.section.main")
        if not section_elements:
            section_elements = soup.select("[data-sectionid]")
        if not section_elements:
            continue

        # Moodle puede devolver múltiples secciones en la página
        # (ej: section-0 General + section-N la pedida).
        # Buscar la que corresponde al sec_num pedido.
        target_el = None
        for el in section_elements:
            el_id = el.get("id", "")
            if el_id == f"section-{sec_num}":
                target_el = el
                break
        if target_el is None:
            # Fallback: tomar la última (la sección específica suele ser la 2da)
            target_el = section_elements[-1]

        section = _parse_section(target_el, sec_num)
        section.number = sec_num

        # Deduplicar recursos por URL
        unique_resources = []
        for res in section.resources:
            key = res.url or res.name
            if key and key not in global_urls:
                global_urls.add(key)
                unique_resources.append(res)
        section.resources = unique_resources

        # Deduplicar labels
        unique_labels = []
        for label in section.labels:
            label_key = label[:100]
            if label_key not in global_labels:
                global_labels.add(label_key)
                unique_labels.append(label)
        section.labels = unique_labels

        if section.resources or section.labels:
            structure.sections.append(section)
            if section.resources:
                logger.info(
                    "  Sección %d: %s — %d recursos, %d etiquetas",
                    section.number, section.title,
                    len(section.resources), len(section.labels),
                )

    total = sum(len(s.resources) for s in structure.sections)
    logger.info("Total: %d secciones, %d recursos", len(structure.sections), total)
    return structure


def _parse_section(element: Tag, default_number: int) -> Section:
    """Parsea un elemento de sección HTML a un objeto Section."""
    # Número de sección
    section_id = element.get("id", "")
    num_match = re.search(r"section-(\d+)", section_id)
    number = int(num_match.group(1)) if num_match else default_number

    # Título de sección
    title = ""
    title_el = element.select_one(
        ".sectionname, .section-title, [data-for='section_title'] a, "
        ".course-section-header h3"
    )
    if title_el:
        title = title_el.get_text(strip=True)
    if not title:
        aria = element.get("aria-label", "")
        if aria:
            title = aria
    if not title:
        title = f"Sección {number}"

    section = Section(number=number, title=title)

    # Extraer etiquetas (labels): contenido de texto entre recursos
    for label_el in element.select(".label .contentafterlink, .modtype_label .contentafterlink"):
        text = label_el.get_text(strip=True)
        if text:
            section.labels.append(text)

    # También buscar descripciones inline
    for desc_el in element.select(".summary, .section_availability, .content .no-overflow"):
        text = desc_el.get_text(strip=True)
        if text and len(text) > 5 and text not in section.labels:
            section.labels.append(text)

    # Extraer recursos
    section.resources = _extract_resources_from_element(element)

    return section


def _extract_resources_from_element(element: Tag) -> list[Resource]:
    """Extrae todos los recursos (activities) de un elemento HTML."""
    resources = []
    seen_urls = set()

    # Buscar actividades: cada una es un <li> con class "activity"
    activities = element.select("li.activity")
    if not activities:
        activities = element.select("[data-activityname]")

    if activities:
        for act in activities:
            resource = _parse_activity(act)
            if resource:
                key = resource.url or resource.name
                if key not in seen_urls:
                    seen_urls.add(key)
                    resources.append(resource)
    else:
        # Fallback: buscar links directos a mods
        for link in element.find_all("a", href=re.compile(r"/mod/\w+/view\.php\?id=\d+")):
            name = link.get_text(strip=True)
            url = link["href"]
            if name and url not in seen_urls:
                seen_urls.add(url)
                rtype = detect_resource_type(url)
                resources.append(Resource(name=name, url=url, resource_type=rtype))

    return resources


def _parse_activity(element: Tag) -> Resource | None:
    """Parsea un elemento de actividad a un Resource."""
    # Buscar el link principal de la actividad
    link = element.select_one(
        ".activityname a, .aalink, .activityinstance a, "
        "[data-activityname] a"
    )

    if not link:
        # Podría ser un label (sin link)
        name_el = element.select_one(
            ".activityname .instancename, .instancename, [data-activityname]"
        )
        if name_el:
            text = name_el.get_text(strip=True)
            # Limpiar texto tipo "Archivo  Archivo" que Moodle genera
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                return Resource(
                    name=text, url="", resource_type="label",
                    description=text,
                )
        return None

    name = ""
    # Intentar obtener nombre de instancename
    instance = link.select_one(".instancename")
    if instance:
        # Quitar el <span class="accesshide"> que Moodle agrega
        for hidden in instance.select(".accesshide"):
            hidden.decompose()
        name = instance.get_text(strip=True)

    if not name:
        name = link.get_text(strip=True)

    if not name:
        name = element.get("data-activityname", "")

    name = re.sub(r'\s+', ' ', name).strip()
    if not name:
        return None

    url = link.get("href", "")
    if url and not url.startswith("http"):
        url = urljoin(MOODLE_BASE + "/", url)

    rtype = detect_resource_type(url)

    # Descripción (si hay)
    desc = ""
    desc_el = element.select_one(".contentafterlink, .activity-description")
    if desc_el:
        desc = desc_el.get_text(strip=True)

    return Resource(name=name, url=url, resource_type=rtype, description=desc)


def resolve_url_resource(session, url: str) -> dict:
    """Resuelve un mod/url para obtener la URL destino real.

    Returns:
        Dict con 'target_url', 'is_internal' (apunta a otro mod de Moodle),
        'resolved_type' (file, page, folder, etc.), 'error'.
    """
    result = {"target_url": "", "is_internal": False, "resolved_type": "url", "error": None}

    try:
        time.sleep(REQUEST_DELAY)
        resp = session.get(url)
        resp.raise_for_status()
    except Exception as e:
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Buscar el link real dentro de la página mod/url
    target = None
    for selector in [
        ".urlworkaround a",
        "#region-main .box.generalbox a[href]",
        "#region-main a.btn[href]",
    ]:
        el = soup.select_one(selector)
        if el and el.get("href"):
            target = el["href"]
            break

    if not target:
        # Fallback: Moodle a veces hace redirect directo
        if resp.url != url and "/mod/url/" not in resp.url:
            target = resp.url

    if not target:
        result["error"] = "No se pudo resolver URL destino"
        return result

    result["target_url"] = target

    # Determinar si es interno (otro recurso Moodle)
    if MOODLE_BASE in target:
        result["is_internal"] = True
        result["resolved_type"] = detect_resource_type(target)
    else:
        result["is_internal"] = False
        result["resolved_type"] = "external"

    return result


def crawl_folder(session, folder_url: str) -> list[dict]:
    """Crawlea una carpeta Moodle y retorna la lista de archivos.

    Returns:
        Lista de dicts con 'name' y 'url' de cada archivo en la carpeta.
    """
    logger.info("Crawleando carpeta: %s", folder_url)
    time.sleep(REQUEST_DELAY)

    resp = session.get(folder_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    files = []

    # Buscar links a archivos dentro de la carpeta
    for link in soup.select(".fp-filename-icon a, .folder-content a, .foldertree a"):
        href = link.get("href", "")
        name = link.get_text(strip=True)
        if href and name and "/pluginfile.php/" in href:
            files.append({"name": name, "url": href})

    # Fallback: buscar cualquier link a pluginfile
    if not files:
        for link in soup.find_all("a", href=re.compile(r"/pluginfile\.php/")):
            name = link.get_text(strip=True)
            href = link["href"]
            if name and href not in [f["url"] for f in files]:
                files.append({"name": name, "url": href})

    logger.info("  Archivos en carpeta: %d", len(files))
    return files
