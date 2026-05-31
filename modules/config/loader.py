"""
modules/config/loader.py
Carga y generación del archivo .codigo_config.json.
"""

import json
from pathlib import Path

from modules.ai import MODELOS_TOKENS, MODELOS_VALIDOS
from modules.config.defaults import (
    NOMBRE_CONFIG, CARPETA_SALIDA_DEFAULT,
    DEFAULT_EXTENSIONES, DEFAULT_IGNORAR,
    DEFAULT_NOMBRE_SALIDA, DEFAULT_NOMBRE_CAMBIOS, DEFAULT_NOMBRE_CO,
)


def cargar_config(raiz: Path) -> dict:
    config_path = raiz / NOMBRE_CONFIG
    overrides   = {}

    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                overrides = json.load(f)
            print(f"[CONFIG] Configuración cargada desde {config_path.name}")
        except json.JSONDecodeError as e:
            print(f"[AVISO]  {NOMBRE_CONFIG} tiene JSON inválido ({e}). Usando defaults.")
    else:
        print(f"[CONFIG] Sin {NOMBRE_CONFIG} — usando configuración por defecto.")

    carpeta_salida_raw = overrides.get("carpeta_salida", None)
    if carpeta_salida_raw:
        cs = Path(carpeta_salida_raw)
        carpeta_salida = (raiz / cs).resolve() if not cs.is_absolute() else cs.resolve()
    else:
        carpeta_salida = raiz / CARPETA_SALIDA_DEFAULT

    modelo_config = str(overrides.get("modelo", "default")).lower()
    if modelo_config not in MODELOS_TOKENS:
        print(f"[AVISO]  Modelo '{modelo_config}' en config no reconocido. Se usará 'default'.")
        modelo_config = "default"

    return {
        "descripcion":           overrides.get("descripcion",           None),
        "extensiones":           set(overrides.get("extensiones",       DEFAULT_EXTENSIONES)),
        "ignorar":               set(overrides.get("ignorar",           DEFAULT_IGNORAR)),
        "nombre_salida":         overrides.get("nombre_salida",         DEFAULT_NOMBRE_SALIDA),
        "nombre_salida_cambios": overrides.get("nombre_salida_cambios", DEFAULT_NOMBRE_CAMBIOS),
        "nombre_salida_co":      overrides.get("nombre_salida_co",      DEFAULT_NOMBRE_CO),
        "incluir_solo":          overrides.get("incluir_solo",          None),
        "carpeta_salida":        carpeta_salida,
        "limite_lineas":         overrides.get("limite_lineas",         None),
        "omitir_autogenerados":  overrides.get("omitir_autogenerados",  False),
        "modelo":                modelo_config,
        "objetivo":              None,
        "archivos_forzados":     None,
        "comprimir":             overrides.get("comprimir",             None),
    }


def generar_config_ejemplo(raiz: Path, limpio: bool = False) -> None:
    """
    Genera .codigo_config.json de ejemplo.
    limpio=True → solo claves y valores, sin comentarios explicativos.
    """
    destino = raiz / NOMBRE_CONFIG

    if destino.exists():
        resp = input(f"[AVISO] Ya existe '{NOMBRE_CONFIG}'. ¿Sobreescribir? (s/N): ").strip().lower()
        if resp != "s":
            print("[OK] Operación cancelada.")
            return

    modelos_str = ", ".join(MODELOS_VALIDOS)

    if limpio:
        config = {
            "descripcion":          "Describe aquí tu proyecto en una o dos oraciones.",
            "extensiones":          [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"],
            "ignorar":              ["node_modules", ".git", "__pycache__", "dist", "venv", "build"],
            "incluir_solo":         ["src", "app", "api"],
            "limite_lineas":        None,
            "omitir_autogenerados": True,
            "carpeta_salida":       ".codigo_completo",
            "nombre_salida":        "contexto_codigo.txt",
            "nombre_salida_cambios":"cambios_git.txt",
            "nombre_salida_co":     "mapa_contexto.txt",
            "modelo":               "default",
            "comprimir":            None,
        }
    else:
        config = {
            "_comentario_descripcion": (
                "Una oración que describe tu proyecto. La IA la leerá primero "
                "y orientará todo el análisis."
            ),
            "descripcion": "Describe aquí tu proyecto en una o dos oraciones.",

            "_comentario_extensiones": (
                "Extensiones de archivo a incluir. "
                "Default: .py .js .ts .jsx .tsx .html .css"
            ),
            "extensiones": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"],

            "_comentario_ignorar": (
                "Carpetas o archivos a excluir completamente. "
                "Default: node_modules .git __pycache__ dist venv build ..."
            ),
            "ignorar": ["node_modules", ".git", "__pycache__", "dist", "venv", "build"],

            "_comentario_incluir_solo": (
                "Si lo defines, solo se incluyen estas carpetas raíz. "
                "Quitá esta clave (o ponla en null) para incluir todo."
            ),
            "incluir_solo": ["src", "app", "api"],

            "_comentario_limite_lineas": (
                "Archivos con más líneas que este valor se omiten. "
                "Útil para reducir tokens. null = sin límite. "
                "También disponible como --limite N en CLI."
            ),
            "limite_lineas": None,

            "_comentario_omitir_autogenerados": (
                "true omite lockfiles (package-lock.json, poetry.lock, etc.), "
                "archivos minificados (*.min.js), protobuf (_pb2.py), "
                "y migraciones auto-numeradas. "
                "También disponible como --sin-minimos en CLI."
            ),
            "omitir_autogenerados": True,

            "_comentario_carpeta_salida": (
                "Dónde guardar los archivos generados. "
                "Ruta relativa al proyecto o absoluta. "
                "Default: .codigo_completo/"
            ),
            "carpeta_salida": ".codigo_completo",

            "_comentario_nombres": (
                "Nombres de los archivos de salida. Podés cambiarlos si preferís otros nombres."
            ),
            "nombre_salida":          "contexto_codigo.txt",
            "nombre_salida_cambios":  "cambios_git.txt",
            "nombre_salida_co":       "mapa_contexto.txt",

            "_comentario_modelo": (
                f"Modelo/agente de IA destino para estimar tokens y costo aproximado. "
                f"Opciones: {modelos_str}. "
                f"Default: 'default' (estimación genérica, sin costo). "
                f"También disponible como --modelo NOMBRE en CLI (CLI tiene prioridad)."
            ),
            "modelo": "default",

            "_comentario_comprimir": (
                "Nivel de compresión: 'leve', 'medio', 'agresivo', o null para desactivar. "
                "Elimina comentarios y docstrings antes de escribir el contexto. "
                "Requiere modules/compresor.py. "
                "También disponible como --comprimir [nivel] en CLI."
            ),
            "comprimir": None,
        }

    with open(destino, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    modo = "mínimo (sin comentarios)" if limpio else "completo (con comentarios)"
    print(f"[OK] Configuración creada ({modo}): {destino}")
    print(f"     Editá los valores según tu proyecto y volvé a ejecutar el script.")