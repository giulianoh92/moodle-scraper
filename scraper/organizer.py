"""Organización de recursos en la estructura del vault de Obsidian."""

import logging
import re
from datetime import date
from pathlib import Path

from config import MATERIAS_PATH, ADJUNTOS_PATH

logger = logging.getLogger(__name__)

# Emojis por tipo de recurso para el índice
TYPE_ICONS = {
    "file": "\U0001f4c4",      # 📄
    "folder": "\U0001f4c1",    # 📁
    "page": "\U0001f4dd",      # 📝
    "url": "\U0001f517",       # 🔗
    "forum": "\U0001f4ac",     # 💬
    "assign": "\U0001f4cb",    # 📋
    "label": "\U0001f3f7\ufe0f",  # 🏷️
    "unknown": "\u2753",       # ❓
}


def generate_index(materia: str, sections_data: list[dict]) -> str:
    """Genera/actualiza el archivo índice de recursos Moodle para una materia.

    Args:
        materia: Nombre de la materia (carpeta del vault).
        sections_data: Lista de dicts con estructura:
            {
                "number": int,
                "title": str,
                "resources": [
                    {
                        "name": str,
                        "type": str,
                        "filename": str | None,  # archivo descargado
                        "url": str | None,        # link externo
                        "page_file": str | None,  # archivo .md creado
                        "description": str,
                    }
                ],
                "labels": [str],
            }

    Returns:
        Path del archivo índice creado.
    """
    dest_dir = MATERIAS_PATH / materia / "Recursos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / "Moodle - Recursos.md"

    today = date.today().isoformat()

    lines = [
        "---",
        "tipo: recurso",
        f"materia: {materia}",
        "fuente: Moodle - Campus Virtual UGD",
        "tags:",
        "  - referencia",
        "  - moodle",
        "---",
        "",
        f"# Recursos Moodle — {materia}",
        "",
        f"> Índice auto-generado por moodle-scraper. Última actualización: {today}",
        "",
    ]

    for section in sections_data:
        title = section["title"]
        number = section["number"]
        lines.append(f"## Sección {number}: {title}")
        lines.append("")

        # Agregar etiquetas como texto
        for label in section.get("labels", []):
            lines.append(f"> {label}")
            lines.append("")

        resources = section.get("resources", [])
        if not resources:
            lines.append("*Sin recursos*")
            lines.append("")
            continue

        for res in resources:
            icon = TYPE_ICONS.get(res["type"], "")
            name = res["name"]

            if res.get("filename"):
                # Archivo descargado → link de Obsidian
                lines.append(f"- {icon} [[{res['filename']}]] — {name}")
            elif res.get("page_file"):
                # Página convertida a MD → link de Obsidian
                page_name = Path(res["page_file"]).stem
                lines.append(f"- {icon} [[{page_name}]] — {name}")
            elif res.get("url") and res["type"] == "url":
                # Link externo
                lines.append(f"- {icon} [{name}]({res['url']})")
            elif res.get("url"):
                # Otro recurso con URL pero no descargado
                lines.append(f"- {icon} {name}")
            else:
                # Label o recurso sin URL
                if res.get("description"):
                    lines.append(f"- {icon} {name}: {res['description']}")
                else:
                    lines.append(f"- {icon} {name}")

        lines.append("")

    content = "\n".join(lines)
    dest_path.write_text(content, encoding="utf-8")
    logger.info("Índice generado: %s", dest_path)
    return str(dest_path)


def ensure_adjuntos_dir(materia: str) -> Path:
    """Asegura que exista el directorio de adjuntos para una materia."""
    path = ADJUNTOS_PATH / materia
    path.mkdir(parents=True, exist_ok=True)
    return path
