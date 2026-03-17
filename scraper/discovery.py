"""Descubrimiento de cursos matriculados."""

import logging
import re
import unicodedata
from dataclasses import dataclass

from config import MOODLE_BASE, COURSE_MAP

logger = logging.getLogger(__name__)


@dataclass
class Course:
    """Curso descubierto en Moodle."""
    id: str
    name: str
    url: str
    materia: str  # nombre de carpeta en vault, o "" si no mapeado


def normalize_name(name: str) -> str:
    """Normaliza un nombre de curso para matching: mayúsculas, sin acentos."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_name.upper().strip()


def match_course_to_materia(course_name: str) -> str:
    """Intenta mapear un nombre de curso Moodle a una carpeta del vault."""
    normalized = normalize_name(course_name)

    # Match exacto
    for key, materia in COURSE_MAP.items():
        if normalize_name(key) == normalized:
            return materia

    # Match parcial
    for key, materia in COURSE_MAP.items():
        if normalize_name(key) in normalized or normalized in normalize_name(key):
            return materia

    return ""


def discover_courses(session) -> list[Course]:
    """Descubre cursos matriculados via el endpoint AJAX interno de Moodle."""
    courses = []

    ajax_url = (
        f"{MOODLE_BASE}/lib/ajax/service.php"
        f"?sesskey={session.sesskey}"
        f"&info=core_course_get_enrolled_courses_by_timeline_classification"
    )

    payload = [{
        "index": 0,
        "methodname": "core_course_get_enrolled_courses_by_timeline_classification",
        "args": {
            "offset": 0,
            "limit": 0,
            "classification": "all",
            "sort": "fullname",
            "customfieldname": "",
            "customfieldvalue": "",
        },
    }]

    logger.info("Consultando cursos matriculados via AJAX...")
    try:
        resp = session.post(ajax_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("Error en endpoint AJAX: %s", e)
        return courses

    if not isinstance(data, list) or not data:
        logger.error("Respuesta AJAX inesperada: %s", str(data)[:200])
        return courses

    if "error" in data[0] and data[0]["error"]:
        msg = data[0].get("exception", {}).get("message", str(data[0]))
        logger.error("Error del servidor: %s", msg)
        return courses

    course_list = data[0].get("data", {}).get("courses", [])

    for c in course_list:
        course_id = str(c.get("id", ""))
        name = c.get("fullname", "").strip()
        if not course_id or not name:
            continue

        url = f"{MOODLE_BASE}/course/view.php?id={course_id}"
        materia = match_course_to_materia(name)

        courses.append(Course(id=course_id, name=name, url=url, materia=materia))

    logger.info("Cursos encontrados: %d", len(courses))
    for c in courses:
        status = f"→ {c.materia}" if c.materia else "(sin mapeo al vault)"
        logger.info("  - [%s] %s %s", c.id, c.name, status)

    return courses
