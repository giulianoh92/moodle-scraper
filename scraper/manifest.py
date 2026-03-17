"""Manifiesto de recursos ya procesados para evitar requests redundantes."""

import json
import logging
from pathlib import Path

from config import PROJECT_PATH

logger = logging.getLogger(__name__)

MANIFEST_PATH = PROJECT_PATH / "manifest.json"


def load_manifest() -> dict:
    """Carga el manifiesto desde disco."""
    if not MANIFEST_PATH.exists():
        return {"resources": {}, "url_resolutions": {}}
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        # Asegurar estructura
        data.setdefault("resources", {})
        data.setdefault("url_resolutions", {})
        return data
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Manifiesto corrupto, recreando: %s", e)
        return {"resources": {}, "url_resolutions": {}}


def save_manifest(manifest: dict):
    """Guarda el manifiesto a disco."""
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def is_resource_known(manifest: dict, resource_url: str) -> dict | None:
    """Verifica si un recurso ya fue procesado.

    Returns:
        Dict con info del recurso si ya existe, None si es nuevo.
        Info incluye: 'filename', 'type', 'materia', 'action' (downloaded/page/external/error).
    """
    return manifest["resources"].get(resource_url)


def record_resource(manifest: dict, resource_url: str, info: dict):
    """Registra un recurso procesado en el manifiesto."""
    manifest["resources"][resource_url] = info


def get_url_resolution(manifest: dict, url: str) -> dict | None:
    """Obtiene la resolución cacheada de un mod/url."""
    return manifest["url_resolutions"].get(url)


def record_url_resolution(manifest: dict, url: str, resolution: dict):
    """Cachea la resolución de un mod/url."""
    manifest["url_resolutions"][url] = resolution
