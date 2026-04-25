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
VAULT_PATH = Path("/home/giuliano/Desarrollo/Personal/Facultad/Vault")
MATERIAS_PATH = VAULT_PATH / "10_Materias"
PROJECT_PATH = Path(__file__).parent

# --- Mapeo curso Moodle → carpeta vault ---
# Las claves se normalizan a mayúsculas sin acentos para matching flexible
COURSE_MAP = {
    "METODOLOGIAS AVANZADAS": "Metodologias Avanzadas",
    "METODOLOGÍAS AVANZADAS": "Metodologias Avanzadas",
    "AUTOMATAS Y LENGUAJES FORMALES": "Automatas y Lenguajes Formales",
    "AUTÓMATAS Y LENGUAJES FORMALES": "Automatas y Lenguajes Formales",
    "INVESTIGACION OPERATIVA": "Investigacion Operativa",
    "INVESTIGACIÓN OPERATIVA": "Investigacion Operativa",
    "TECNOLOGIAS DE BASES DE DATOS": "Tecnologias de Bases de Datos",
    "TECNOLOGÍAS DE BASES DE DATOS": "Tecnologias de Bases de Datos",
    "TECNOLOGIA DE BASES DE DATOS": "Tecnologias de Bases de Datos",
    "TECNOLOGÍA DE BASES DE DATOS": "Tecnologias de Bases de Datos",
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
