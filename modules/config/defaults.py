"""
modules/config/defaults.py
Constantes y valores por defecto del proyecto.
Sin dependencias internas: puede importarse desde cualquier módulo.
"""

import re

# ── Nombres de archivo ────────────────────────────────────────────────────────

NOMBRE_CONFIG          = ".codigo_config.json"
CARPETA_SALIDA_DEFAULT = ".codigo_completo"

DEFAULT_NOMBRE_SALIDA  = "contexto_codigo.txt"
DEFAULT_NOMBRE_CAMBIOS = "cambios_git.txt"
DEFAULT_NOMBRE_CO      = "mapa_contexto.txt"

# ── Inclusión / exclusión ─────────────────────────────────────────────────────

DEFAULT_EXTENSIONES = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"}

DEFAULT_IGNORAR = {
    "node_modules", ".git", "__pycache__", "dist", ".env",
    "venv", ".venv", "build", "coverage", ".next", ".nuxt",
}

# ── Archivos auto-generados ───────────────────────────────────────────────────

ARCHIVOS_AUTOGENERADOS = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "composer.lock",
    "Gemfile.lock", "cargo.lock", "go.sum",
    "shrinkwrap.json", ".DS_Store", "thumbs.db",
}

PATRONES_AUTOGENERADOS = [
    re.compile(r"\.min\.(js|css)$"),
    re.compile(r"\.bundle\.(js|css)$"),
    re.compile(r"\.chunk\.js$"),
    re.compile(r"_pb2\.py$"),
    re.compile(r"\.generated\.\w+$"),
    re.compile(r"migration_\d+"),
]

# ── Archivos de alta prioridad (aparecen primero en el output) ────────────────

ARCHIVOS_PRIORITARIOS = {
    "main", "index", "app", "server", "init",
    "__init__", "__main__", "manage", "run",
    "wsgi", "asgi", "settings", "config",
}