# Moodle Scraper

Scraper que descarga todos los recursos de cursos en Moodle y los organiza como archivos Markdown compatibles con [Obsidian](https://obsidian.md/).

## Funcionalidades

- Login automático en Moodle via formulario web
- Descubrimiento automático de cursos matriculados
- Descarga de archivos (PDF, DOCX, PPTX, etc.)
- Conversión de páginas y tareas a Markdown
- Generación de índices por materia con links de Obsidian (`[[wikilinks]]`)
- Cache con manifiesto para evitar re-descargas (modo incremental)
- Rate limiting para no saturar el servidor

## Requisitos

- Python 3.12+
- Cuenta activa en la instancia de Moodle

## Instalación

```bash
git clone https://github.com/YOUR_USER/moodle-scraper.git
cd moodle-scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuración

1. Copiar el archivo de ejemplo y completar las credenciales:

```bash
cp .env.example .env
```

2. Editar `.env` con tu usuario y contraseña de Moodle:

```
MOODLE_USER=tu_usuario
MOODLE_PASS=tu_contraseña
```

3. Editar `config.py` para ajustar:
   - `MOODLE_BASE`: URL base de tu instancia Moodle
   - `VAULT_PATH`: ruta a tu vault de Obsidian
   - `COURSE_MAP`: mapeo de nombres de curso a carpetas del vault

## Uso

```bash
# Procesar todos los cursos mapeados
python main.py

# Procesar un curso específico por ID
python main.py -c 12345

# Ver la estructura sin descargar nada
python main.py --dry-run

# Re-procesar todo ignorando la cache
python main.py --force

# Modo verbose
python main.py -v
```

## Estructura del proyecto

```
moodle-scraper/
├── main.py              # Entry point y orquestación
├── config.py            # Configuración (URLs, paths, mapeos)
├── requirements.txt     # Dependencias Python
├── .env.example         # Template de variables de entorno
└── scraper/
    ├── auth.py          # Autenticación en Moodle
    ├── discovery.py     # Descubrimiento de cursos
    ├── crawler.py       # Crawling de secciones y recursos
    ├── downloader.py    # Descarga de archivos
    ├── extractor.py     # Extracción HTML → Markdown
    ├── organizer.py     # Generación de índices para Obsidian
    └── manifest.py      # Cache/manifiesto de recursos procesados
```

## Licencia

MIT
