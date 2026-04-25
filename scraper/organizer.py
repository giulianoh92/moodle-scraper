"""Organización de recursos en la estructura del vault de Obsidian."""

import logging
import re
from datetime import date
from pathlib import Path

from config import MATERIAS_PATH

logger = logging.getLogger(__name__)

# Emojis por tipo de recurso para el índice
TYPE_ICONS = {
    "file": "\U0001f4c4",      # 📄
    "folder": "\U0001f4c1",    # 📁
    "page": "\U0001f4dd",      # 📝
    "url": "\U0001f517",       # 🔗
    "forum": "\U0001f4ac",     # 💬
    "assign": "\U0001f4cb",    # 📋
    "label": "\U0001f3f7️",  # 🏷️
    "unknown": "❓",       # ❓
}

# Marcadores para bloque auto-generado (idempotencia frente a anotaciones manuales)
MOODLE_START = "<!-- moodle:start -->"
MOODLE_END = "<!-- moodle:end -->"


def _build_auto_block(materia: str, sections_data: list[dict], today: str) -> str:
    """Arma el bloque de contenido auto-generado (entre marcadores)."""
    lines = [
        MOODLE_START,
        "",
        f"> Índice auto-generado por moodle-scraper. Última actualización: {today}",
        "",
    ]

    for section in sections_data:
        title = section["title"]
        number = section["number"]
        lines.append(f"## Sección {number}: {title}")
        lines.append("")

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
                lines.append(f"- {icon} [[{res['filename']}]] — {name}")
            elif res.get("page_file"):
                page_name = Path(res["page_file"]).stem
                lines.append(f"- {icon} [[{page_name}]] — {name}")
            elif res.get("url") and res["type"] == "url":
                lines.append(f"- {icon} [{name}]({res['url']})")
            elif res.get("url"):
                lines.append(f"- {icon} {name}")
            else:
                if res.get("description"):
                    lines.append(f"- {icon} {name}: {res['description']}")
                else:
                    lines.append(f"- {icon} {name}")

        lines.append("")

    lines.append(MOODLE_END)
    return "\n".join(lines)


def _build_new_file(materia: str, auto_block: str) -> str:
    """Arma el contenido completo cuando el archivo no existe."""
    overview_link = f"{materia} - Overview"
    header = [
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
        f"> [!info] Indice de recursos del campus virtual de la materia [[{overview_link}|{materia}]].",
        "",
        auto_block,
        "",
    ]
    return "\n".join(header)


def _replace_auto_block(existing: str, auto_block: str) -> str:
    """Reemplaza solo el bloque entre MOODLE_START y MOODLE_END, preservando el resto.

    Si los marcadores no existen en el archivo, los inserta al final para
    migrar archivos legacy a la nueva convención de forma no destructiva.
    """
    pattern = re.compile(
        re.escape(MOODLE_START) + r".*?" + re.escape(MOODLE_END),
        re.DOTALL,
    )
    if pattern.search(existing):
        return pattern.sub(auto_block, existing)
    # Legacy: sin marcadores → apendar el bloque al final
    return existing.rstrip() + "\n\n" + auto_block + "\n"


def _legacy_path(dest_dir: Path) -> Path | None:
    """Devuelve el path del índice viejo `Moodle - Recursos.md` si existe."""
    legacy = dest_dir / "Moodle - Recursos.md"
    return legacy if legacy.exists() else None


def generate_index(materia: str, sections_data: list[dict]) -> str:
    """Genera/actualiza el archivo índice de recursos Moodle para una materia.

    Archivo destino: `Moodle - <Materia>.md` dentro de `<Materia>/Recursos/`.
    El contenido auto-generado se envuelve entre marcadores HTML para permitir
    regeneraciones idempotentes sin pisar anotaciones manuales del usuario.

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
                        "filename": str | None,
                        "url": str | None,
                        "page_file": str | None,
                        "description": str,
                    }
                ],
                "labels": [str],
            }

    Returns:
        Path del archivo índice creado/actualizado.
    """
    dest_dir = MATERIAS_PATH / materia / "Recursos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"Moodle - {materia}.md"

    today = date.today().isoformat()
    auto_block = _build_auto_block(materia, sections_data, today)

    # Migración transparente: si existe el nombre viejo, usarlo como base
    # y renombrar a la nueva convención al escribir.
    source_path = dest_path if dest_path.exists() else _legacy_path(dest_dir)

    if source_path and source_path.exists():
        existing = source_path.read_text(encoding="utf-8")
        content = _replace_auto_block(existing, auto_block)
        if source_path != dest_path:
            source_path.unlink()  # eliminar legacy tras migrar
            logger.info("Migrado legacy → %s", dest_path.name)
    else:
        content = _build_new_file(materia, auto_block)

    dest_path.write_text(content, encoding="utf-8")
    logger.info("Índice generado: %s", dest_path)
    return str(dest_path)


def ensure_recursos_dir(materia: str) -> Path:
    """Asegura que exista el directorio de recursos para una materia."""
    path = MATERIAS_PATH / materia / "Recursos"
    path.mkdir(parents=True, exist_ok=True)
    return path
