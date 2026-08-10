"""Configuración central del scraper."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Credenciales (desde .env) ---
MOODLE_USER = os.environ.get("MOODLE_USER", "")
MOODLE_PASS = os.environ.get("MOODLE_PASS", "")

# --- URLs ---
MOODLE_BASE = "https://campusvirtual.ugd.edu.ar/moodle"
LOGIN_URL = f"{MOODLE_BASE}/login/index.php"
DASHBOARD_URL = f"{MOODLE_BASE}/my/"
COURSE_URL = f"{MOODLE_BASE}/course/view.php"

# --- Paths ---
PROJECT_PATH = Path(__file__).parent
VAULT_PATH = PROJECT_PATH.parent.parent.resolve()
MATERIAS_PATH = VAULT_PATH / "10_Materias"

# --- Mapeo curso Moodle → carpeta vault ---
# Las claves se normalizan a mayúsculas sin acentos para matching flexible,
# así que no hace falta duplicar variantes acentuadas.
#
# Cursada activa: 2.º cuatrimestre 2026 (4.º año, comisión "A").
COURSE_MAP = {
    "CALCULO NUMERICO": "Calculo Numerico",
    "COMPILADORES": "Compiladores",
    "INGENIERIA DEL SOFTWARE": "Ingenieria del Software",
    "MODELOS Y SIMULACION": "Modelos y Simulacion",
    "REDES DE COMPUTADORAS II": "Redes de Computadoras II",
}

# --- Rate limiting ---
REQUEST_DELAY = 1.5  # segundos entre requests
DOWNLOAD_DELAY = 2.0  # segundos entre descargas de archivos

# --- Extensiones binarias ---
BINARY_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".bmp",
    ".mp4", ".mp3", ".avi", ".mkv",
    ".odt", ".ods", ".odp",
}
