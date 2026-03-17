"""Autenticación en Moodle via formulario web."""

import logging
import re

import requests
from bs4 import BeautifulSoup

from config import LOGIN_URL, MOODLE_USER, MOODLE_PASS

logger = logging.getLogger(__name__)


def create_session() -> requests.Session:
    """Crea una sesión HTTP autenticada en Moodle.

    Returns:
        requests.Session con cookies de sesión activa.

    Raises:
        RuntimeError: Si el login falla.
    """
    if not MOODLE_USER or not MOODLE_PASS:
        raise RuntimeError(
            "Credenciales no configuradas. "
            "Definí MOODLE_USER y MOODLE_PASS en .env"
        )

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    })

    # GET login page para obtener logintoken
    logger.info("Obteniendo página de login...")
    resp = session.get(LOGIN_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    token_input = soup.find("input", {"name": "logintoken"})
    logintoken = token_input["value"] if token_input else ""

    # POST login
    logger.info("Enviando credenciales...")
    login_data = {
        "username": MOODLE_USER,
        "password": MOODLE_PASS,
        "logintoken": logintoken,
        "anchor": "",
    }
    resp = session.post(LOGIN_URL, data=login_data, allow_redirects=True)
    resp.raise_for_status()

    # Verificar login exitoso: buscar indicadores de error
    if "loginerrors" in resp.text or "invalid" in resp.url.lower():
        raise RuntimeError("Login fallido — verificá usuario y contraseña en .env")

    # Verificar que hay sesskey (indica sesión activa)
    sesskey_match = re.search(r'"sesskey":"([^"]+)"', resp.text)
    if not sesskey_match:
        # Intentar otro patrón
        sesskey_match = re.search(r'sesskey=([a-zA-Z0-9]+)', resp.text)

    if sesskey_match:
        session.sesskey = sesskey_match.group(1)
        logger.info("Login exitoso. sesskey=%s...", session.sesskey[:8])
    else:
        logger.warning("Login aparentemente exitoso pero no se encontró sesskey")
        session.sesskey = ""

    return session
