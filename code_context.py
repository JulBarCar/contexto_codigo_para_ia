"""
code_context.py
Recorre la carpeta del proyecto y unifica todos los archivos de código
en un único archivo de texto, listo para pasar a una IA.

Genera hasta cinco archivos:
  1. contexto_codigo.txt          → todo el proyecto
  2. cambios_git.txt              → solo archivos modificados desde el último pull
  3. mapa_contexto.txt            → con --co: árbol + dependencias, sin código
  4. ia_[objetivo]_contexto.txt   → con --objetivo: contexto optimizado para IA
  5. ia_[objetivo]_solicitado.txt → con --objetivo + --archivos: archivos pedidos por IA

Configuración opcional: crea '.codigo_config.json' en la raíz del proyecto.
Si no existe, funciona con los valores por defecto.
Usa `--init` para generar un archivo de configuración de ejemplo.

USO:
  python code_context.py [carpeta] [opciones]

OPCIONES CLI:
  --init                    Genera .codigo_config.json de ejemplo con comentarios
  --init --limpio           Genera .codigo_config.json mínimo, sin comentarios
  --co                      Solo contexto: árbol + dependencias + fichas, sin código
  --solo-cambios            Solo genera el archivo de cambios git
  --limite N                Omite archivos con más de N líneas (default: sin límite)
  --sin-minimos             Omite lockfiles, *.min.js, migraciones auto-numeradas, etc.
  --verbose                 Muestra qué archivos se omiten y por qué
  --preview                 Muestra qué archivos se incluirían, sin generar nada
  --stats                   Muestra estimación de tokens sin generar archivos
  --ignorar-extra f1 f2 ... Agrega carpetas/archivos a ignorar sin tocar el config
  --objetivo "texto"        Define el objetivo de la sesión. Genera un archivo
                            optimizado para IA con nombre ia_[slug]_contexto.txt
  --archivos f1 f2 ...      Incluye solo los archivos indicados (rutas relativas).
                            Con --objetivo genera ia_[slug]_solicitado.txt
  --continua                Segunda vuelta: omite <context_metadata>, <file_tree> e
                            <file_index> en ia_[slug]_solicitado.txt (la IA ya los vio).
                            Solo válido con --objetivo + --archivos.
  --modelo NOMBRE           Modelo/agente destino para estimar tokens y costo.
                            Opciones: claude, gpt-4, gpt-4o, gpt-3.5, gemini,
                                      gemini-pro, llama, mistral, deepseek, default
                            Default: "default" (estimación genérica, sin costo)
  --comprimir [leve|medio|agresivo]
                            Elimina comentarios y docstrings antes de escribir los archivos.
                            Sin argumento usa nivel "medio". Niveles:
                              leve      → solo elimina comentarios de línea/bloque
                              medio     → también docstrings de módulo (default)
                              agresivo  → todos los docstrings + colapsa líneas vacías
                            Soporta .py .js .ts .jsx .tsx .html .css
                            Requiere compresor.py en la misma carpeta.
  --ayuda                   Muestra esta ayuda

OPCIONES DISPONIBLES EN .codigo_config.json (pero no como argumento CLI):
  descripcion               Una oración sobre tu proyecto. La IA la leerá primero.
  extensiones               Lista de extensiones a incluir (ej: [".py", ".ts"]).
  ignorar                   Carpetas/archivos a excluir.
  incluir_solo              Si se define, solo se analizan estas carpetas raíz.
  carpeta_salida            Dónde guardar los archivos generados.
  nombre_salida             Nombre del archivo de contexto completo.
  nombre_salida_cambios     Nombre del archivo de cambios git.
  nombre_salida_co          Nombre del archivo de mapa de contexto.
  modelo                    Igual que --modelo (la CLI tiene prioridad si se usan ambos).
  comprimir                 Igual que --comprimir (la CLI tiene prioridad si se usan ambos).

  → Las opciones de config sin equivalente CLI (descripcion, extensiones, ignorar,
    incluir_solo, carpeta_salida, nombres de salida) están ahí porque se configuran
    una sola vez por proyecto y no tiene sentido escribirlas en cada ejecución.

EJEMPLO .codigo_config.json:
{
    "descripcion": "API REST en FastAPI para gestión de inventario.",
    "extensiones": [".py", ".js", ".ts"],
    "ignorar": ["node_modules", ".git", "dist"],
    "incluir_solo": ["src", "api"],
    "limite_lineas": 500,
    "omitir_autogenerados": true,
    "carpeta_salida": ".codigo_completo",
    "nombre_salida": "contexto_codigo.txt",
    "nombre_salida_cambios": "cambios_git.txt",
    "nombre_salida_co": "mapa_contexto.txt",
    "modelo": "claude"
}
"""

import sys
import ast
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

try:
    from compresor import comprimir_texto, NivelCompresion, EXTENSIONES_SOPORTADAS
    COMPRESION_DISPONIBLE = True
except ImportError:
    COMPRESION_DISPONIBLE = False

# ── Valores por defecto ───────────────────────────────────────────────────────

DEFAULT_EXTENSIONES    = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"}
DEFAULT_IGNORAR        = {"node_modules", ".git", "__pycache__", "dist", ".env",
                          "venv", ".venv", "build", "coverage", ".next", ".nuxt"}
DEFAULT_NOMBRE_SALIDA  = "contexto_codigo.txt"
DEFAULT_NOMBRE_CAMBIOS = "cambios_git.txt"
DEFAULT_NOMBRE_CO      = "mapa_contexto.txt"
CARPETA_SALIDA_DEFAULT = ".codigo_completo"
NOMBRE_CONFIG          = ".codigo_config.json"

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

ARCHIVOS_PRIORITARIOS = {
    "main", "index", "app", "server", "init",
    "__init__", "__main__", "manage", "run",
    "wsgi", "asgi", "settings", "config",
}

# ── Modelos y estimación de tokens ───────────────────────────────────────────

MODELOS_TOKENS: dict[str, dict] = {
    "claude": {
        "nombre_display":  "Claude Sonnet (Anthropic)",
        "chars_por_token": 3.8,
        "precio_input":    3.00,
        "context_window":  200_000,
    },
    "gpt-4": {
        "nombre_display":  "GPT-4 Turbo (OpenAI)",
        "chars_por_token": 4.0,
        "precio_input":    30.00,
        "context_window":  128_000,
    },
    "gpt-4o": {
        "nombre_display":  "GPT-4o (OpenAI)",
        "chars_por_token": 4.0,
        "precio_input":    5.00,
        "context_window":  128_000,
    },
    "gpt-3.5": {
        "nombre_display":  "GPT-3.5 Turbo (OpenAI)",
        "chars_por_token": 4.0,
        "precio_input":    0.50,
        "context_window":  16_385,
    },
    "gemini": {
        "nombre_display":  "Gemini 1.5 Flash (Google)",
        "chars_por_token": 4.2,
        "precio_input":    0.075,
        "context_window":  1_000_000,
    },
    "gemini-pro": {
        "nombre_display":  "Gemini 1.5 Pro (Google)",
        "chars_por_token": 4.2,
        "precio_input":    1.25,
        "context_window":  2_000_000,
    },
    "llama": {
        "nombre_display":  "LLaMA (Meta)",
        "chars_por_token": 3.9,
        "precio_input":    None,
        "context_window":  128_000,
    },
    "mistral": {
        "nombre_display":  "Mistral Large",
        "chars_por_token": 3.9,
        "precio_input":    4.00,
        "context_window":  128_000,
    },
    "deepseek": {
        "nombre_display":  "DeepSeek V3",
        "chars_por_token": 3.8,
        "precio_input":    0.27,
        "context_window":  64_000,
    },
    "default": {
        "nombre_display":  "Genérico (sin modelo específico)",
        "chars_por_token": 4.0,
        "precio_input":    None,
        "context_window":  None,
    },
}

MODELOS_VALIDOS = list(MODELOS_TOKENS.keys())


def estimar_tokens(texto: str, modelo: str = "default") -> dict:
    info   = MODELOS_TOKENS.get(modelo, MODELOS_TOKENS["default"])
    chars  = len(texto)
    tokens = int(chars / info["chars_por_token"])
    costo_usd = (tokens / 1_000_000) * info["precio_input"] \
                if info["precio_input"] is not None else None
    porcentaje_window = (tokens / info["context_window"]) * 100 \
                        if info["context_window"] is not None else None
    return {
        "chars": chars, "tokens": tokens, "costo_usd": costo_usd,
        "porcentaje_window": porcentaje_window,
        "info_modelo": info, "modelo_key": modelo,
    }


def formatear_estimacion_tokens(est: dict) -> str:
    sep  = "=" * 72
    info = est["info_modelo"]
    lines = [
        f"\n# {sep}",
        f"# ESTIMACIÓN DE TOKENS",
        f"# {sep}",
        f"#",
        f"#  Modelo           : {info['nombre_display']}",
        f"#  Caracteres       : {est['chars']:,}".replace(",", "."),
        f"#  Tokens estimados : ~{est['tokens']:,}".replace(",", "."),
    ]
    if est["costo_usd"] is not None:
        lines.append(f"#  Costo estimado   : ~${est['costo_usd']:.4f} USD  (solo tokens de entrada)")
    else:
        lines.append(f"#  Costo estimado   : no disponible (varía según proveedor)")
    if est["porcentaje_window"] is not None:
        cw_fmt = f"{info['context_window']:,}".replace(",", ".")
        pct    = est["porcentaje_window"]
        estado = "✓ entra" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE EL LÍMITE")
        lines.append(f"#  Context window   : {cw_fmt} tokens  →  {pct:.1f}% usado  [{estado}]")
    else:
        lines.append(f"#  Context window   : no especificado para este modelo")
    lines += [
        f"#",
        f"#  Nota: los precios y límites pueden haber cambiado. Verificá en",
        f"#  la documentación oficial del modelo antes de tomar decisiones de costo.",
        f"# {sep}",
    ]
    return "\n".join(lines) + "\n"


# ── Nombres de archivo para modo --objetivo ───────────────────────────────────

def objetivo_a_slug(objetivo: str, sufijo: str) -> str:
    """
    Convierte el texto del objetivo en un slug limpio para usar en el nombre del archivo.
    Ej: "Agregar autenticación JWT" → "ia_agregar_autenticacion_jwt_contexto.txt"
    """
    slug = objetivo.lower()
    for src, dst in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),
                     ("ñ","n"),("ü","u"),("à","a"),("è","e"),("ì","i"),
                     ("ò","o"),("ù","u")]:
        slug = slug.replace(src, dst)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    slug = re.sub(r"_+", "_", slug)
    slug = slug[:40].rstrip("_")
    return f"ia_{slug}_{sufijo}.txt"


# ── CLI ───────────────────────────────────────────────────────────────────────

def parsear_args(argv: list[str]) -> dict:
    args = {
        "carpeta":       ".",
        "init":          False,
        "init_limpio":   False,
        "co":            False,
        "solo_cambios":  False,
        "limite":        None,
        "sin_minimos":   False,
        "verbose":       False,
        "preview":       False,
        "stats":         False,
        "ignorar_extra": [],
        "objetivo":      None,
        "archivos":      None,
        "modelo":        None,
        "continua":      False,
        "comprimir":     None,
    }

    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("--ayuda", "--help", "-h"):
            print(__doc__)
            sys.exit(0)
        elif tok == "--init":
            args["init"] = True
        elif tok == "--limpio":
            args["init_limpio"] = True
        elif tok == "--co":
            args["co"] = True
        elif tok == "--solo-cambios":
            args["solo_cambios"] = True
        elif tok == "--sin-minimos":
            args["sin_minimos"] = True
        elif tok == "--verbose":
            args["verbose"] = True
        elif tok == "--preview":
            args["preview"] = True
        elif tok == "--stats":
            args["stats"] = True
        elif tok == "--continua":
            args["continua"] = True
        elif tok == "--limite":
            i += 1
            if i >= len(argv):
                print("[ERROR] --limite requiere un número. Ej: --limite 500")
                sys.exit(1)
            try:
                args["limite"] = int(argv[i])
            except ValueError:
                print(f"[ERROR] --limite necesita un entero, recibió: '{argv[i]}'")
                sys.exit(1)
        elif tok == "--objetivo":
            i += 1
            if i >= len(argv):
                print("[ERROR] --objetivo requiere un texto. Ej: --objetivo \"Agregar JWT\"")
                sys.exit(1)
            args["objetivo"] = argv[i]
        elif tok == "--modelo":
            i += 1
            if i >= len(argv):
                print(f"[ERROR] --modelo requiere un nombre. Opciones: {', '.join(MODELOS_VALIDOS)}")
                sys.exit(1)
            m = argv[i].lower()
            if m not in MODELOS_TOKENS:
                print(f"[ERROR] Modelo '{argv[i]}' no reconocido.")
                print(f"        Opciones: {', '.join(MODELOS_VALIDOS)}")
                sys.exit(1)
            args["modelo"] = m
        elif tok == "--ignorar-extra":
            i += 1
            extras = []
            while i < len(argv) and not argv[i].startswith("--"):
                extras.append(argv[i])
                i += 1
            if not extras:
                print("[ERROR] --ignorar-extra requiere al menos un nombre. Ej: --ignorar-extra tmp logs")
                sys.exit(1)
            args["ignorar_extra"] = extras
            continue
        elif tok == "--archivos":
            i += 1
            archivos_lista = []
            while i < len(argv) and not argv[i].startswith("--"):
                archivos_lista.append(argv[i])
                i += 1
            if not archivos_lista:
                print("[ERROR] --archivos requiere al menos un archivo.")
                sys.exit(1)
            args["archivos"] = archivos_lista
            continue
        elif tok == "--comprimir":
            i += 1
            niveles_validos = ["leve", "medio", "agresivo"]
            if i >= len(argv) or argv[i].startswith("--"):
                args["comprimir"] = "medio"
                continue
            nivel = argv[i].lower()
            if nivel not in niveles_validos:
                print(f"[ERROR] --comprimir acepta: {', '.join(niveles_validos)}")
                sys.exit(1)
            args["comprimir"] = nivel
        elif not tok.startswith("--"):
            args["carpeta"] = tok
        else:
            print(f"[AVISO] Argumento desconocido: '{tok}'. Usa --ayuda para ver opciones.")
        i += 1

    return args

# ── Configuración ─────────────────────────────────────────────────────────────

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
                "Requiere compresor.py en la misma carpeta. "
                "También disponible como --comprimir [nivel] en CLI."
            ),
            "comprimir": None,
        }

    with open(destino, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    modo = "mínimo (sin comentarios)" if limpio else "completo (con comentarios)"
    print(f"[OK] Configuración creada ({modo}): {destino}")
    print(f"     Editá los valores según tu proyecto y volvé a ejecutar el script.")

# ── Detección de auto-generados ───────────────────────────────────────────────

def es_autogenerado(archivo: Path, limite_lineas: int | None = None,
                    verbose: bool = False) -> bool:
    nombre = archivo.name
    if nombre in ARCHIVOS_AUTOGENERADOS:
        if verbose:
            print(f"  [OMITIDO] {nombre}  →  lockfile conocido")
        return True
    for patron in PATRONES_AUTOGENERADOS:
        if patron.search(nombre):
            if verbose:
                print(f"  [OMITIDO] {nombre}  →  patrón auto-generado")
            return True
    if archivo.suffix in {".js", ".css", ".ts"}:
        try:
            primera_linea = archivo.open(encoding="utf-8", errors="replace").readline()
            if len(primera_linea) > 500:
                if verbose:
                    print(f"  [OMITIDO] {nombre}  →  primera línea de {len(primera_linea)} chars (posible minificado)")
                return True
        except Exception:
            pass
    if limite_lineas is not None:
        try:
            lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            if lineas > limite_lineas:
                if verbose:
                    print(f"  [OMITIDO] {nombre}  →  {lineas} líneas (límite: {limite_lineas})")
                return True
        except Exception:
            pass
    return False

# ── Git ───────────────────────────────────────────────────────────────────────

def _fix_encoding(texto: str) -> str:
    """
    Corrige texto mal decodificado en Windows (latin-1 interpretado como UTF-8).
    Ej: 'rediseÃ±o' → 'rediseño'
    """
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texto


def obtener_archivos_modificados(raiz: Path) -> list[Path] | None:
    def run(cmd):
        r = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []

    check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=raiz, capture_output=True, text=True
    )
    if check.returncode != 0:
        print("[GIT]    No es un repositorio git — se omite el archivo de cambios.")
        return None

    orig_head = run(["git", "rev-parse", "--verify", "ORIG_HEAD"])
    if orig_head:
        archivos = run(["git", "diff", "--name-only", "--diff-filter=ACMR", "ORIG_HEAD", "HEAD"])
        origen   = "ORIG_HEAD → HEAD (último pull/merge)"
    else:
        staged   = run(["git", "diff", "--name-only", "--diff-filter=ACMR", "--cached"])
        unstaged = run(["git", "diff", "--name-only", "--diff-filter=ACMR"])
        archivos = list(dict.fromkeys(staged + unstaged))
        origen   = "working tree (cambios sin commitear)"

    if not archivos:
        print("[GIT]    Sin archivos modificados detectados.")
        return []

    print(f"[GIT]    {len(archivos)} archivo(s) modificado(s)  ({origen})")
    return [raiz / p for p in archivos if (raiz / p).exists()]


def obtener_ultimos_commits(raiz: Path, n: int = 5) -> list[str]:
    r = subprocess.run(
        ["git", "log", "--oneline", f"-{n}"],
        cwd=raiz, capture_output=True,
        encoding="utf-8", errors="replace"
    )
    if r.returncode != 0:
        return []
    lineas = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return [_fix_encoding(l) for l in lineas]

# ── Ordenación ────────────────────────────────────────────────────────────────

def _prioridad(archivo: Path) -> tuple:
    partes         = archivo.parts
    profundidad    = len(partes)
    stem_lower     = archivo.stem.lower().lstrip("_")
    es_prioritario = 0 if stem_lower in ARCHIVOS_PRIORITARIOS else 1
    return (profundidad, es_prioritario, archivo.name.lower())


def ordenar_archivos(archivos: list[Path]) -> list[Path]:
    return sorted(archivos, key=_prioridad)

# ── Resolución de aliases de módulos ─────────────────────────────────────────
#
# Soporta la lectura de aliases desde los siguientes archivos de configuración:
#
#   JavaScript / TypeScript
#   ├── tsconfig.json / tsconfig.base.json   compilerOptions.paths + baseUrl
#   ├── jsconfig.json                         ídem (proyectos JS sin TS)
#   ├── vite.config.js / .ts                  resolve.alias
#   ├── webpack.config.js / .ts               resolve.alias
#   ├── babel.config.js / .json               plugin module-resolver → alias
#   ├── .babelrc / .babelrc.js                ídem
#   ├── nuxt.config.js / .ts                  alias: { ... }
#   └── jest.config.js / .ts                  moduleNameMapper
#
#   Python
#   ├── pyproject.toml                        [tool.pytest.ini_options] o
#   │                                         [tool.setuptools] → packages
#   └── setup.cfg / setup.py                  packages / package_dir
#       (los imports de Python se resuelven por ruta real, no por alias,
#        así que esto solo aplica para rutas relativas directas)
#
# Nota: Next.js no define aliases propios; delega en tsconfig.paths (ya cubierto).
# Remix y SvelteKit usan vite.config o tsconfig (ya cubiertos).
# Astro usa tsconfig.paths (ya cubierto) y opcionalmente vite.config.

def _leer_json_permisivo(texto: str) -> dict:
    """Lee JSON con comentarios estilo // y /* */ (jsconfig, tsconfig)."""
    sin_comentarios = re.sub(r"/\*[\s\S]*?\*/", "", texto)
    sin_comentarios = re.sub(r"//[^\n]*", "", sin_comentarios)
    try:
        return json.loads(sin_comentarios)
    except Exception:
        return {}


def _extraer_aliases_tsconfig(datos: dict, raiz: Path) -> dict[str, Path]:
    """
    Extrae compilerOptions.paths de tsconfig.json / jsconfig.json.
    Ej: "@/*": ["src/*"]  →  "@" → raiz/src
    También respeta baseUrl para paths relativos.
    """
    aliases: dict[str, Path] = {}
    opts = datos.get("compilerOptions", {})
    base = (raiz / opts.get("baseUrl", ".")).resolve()
    for alias_pat, targets in opts.get("paths", {}).items():
        if not targets:
            continue
        # "@/*" → "@",  "~utils" → "~utils"
        clave    = alias_pat.rstrip("/*").rstrip("/")
        primera  = targets[0].rstrip("/*").rstrip("/")
        try:
            aliases[clave] = (base / primera).resolve()
        except Exception:
            pass
    return aliases


def _extraer_aliases_vite(texto: str, raiz: Path) -> dict[str, Path]:
    """
    Extrae resolve.alias de vite.config.js/ts.
    Cubre: '@': path.resolve(__dirname, 'src'),
           '@': fileURLToPath(new URL('./src', import.meta.url)),
           '@': '/ruta/absoluta'
    """
    aliases: dict[str, Path] = {}
    patron = re.compile(
        r"""['"](@[\w/.-]*|~[\w/.-]*|[\w][\w/.-]*)['"]\s*:\s*"""
        r"""(?:"""
        r"""(?:path\.resolve|path\.join)\s*\([^,)]*,\s*['"]([^'"]+)['"]"""   # path.resolve(__dirname, 'x')
        r"""|fileURLToPath\s*\(new\s+URL\s*\(\s*['"]([^'"]+)['"]"""           # fileURLToPath(new URL('./x', ...))
        r"""|['"]([^'"]+)['"])""",                                             # string literal directo
        re.MULTILINE,
    )
    for m in patron.finditer(texto):
        alias    = m.group(1)
        ruta_str = (m.group(2) or m.group(3) or m.group(4) or "").strip("/")
        if ruta_str:
            try:
                aliases[alias] = (raiz / ruta_str).resolve()
            except Exception:
                pass
    return aliases


def _extraer_aliases_webpack(texto: str, raiz: Path) -> dict[str, Path]:
    """
    Extrae resolve.alias de webpack.config.js/ts.
    Cubre: '@': path.resolve(__dirname, 'src'),
           '@': path.join(__dirname, 'src'),
           '@': '/ruta/absoluta'
    """
    aliases: dict[str, Path] = {}
    patron = re.compile(
        r"""['"](@[\w/.-]*|~[\w/.-]*|[\w][\w$/-]+)['"]\s*:\s*"""
        r"""(?:"""
        r"""(?:path\.resolve|path\.join)\s*\([^,)]*,\s*['"]([^'"]+)['"]"""
        r"""|['"]([^'"]+)['"])""",
        re.MULTILINE,
    )
    for m in patron.finditer(texto):
        alias    = m.group(1)
        ruta_str = (m.group(2) or m.group(3) or "").strip("/")
        if ruta_str:
            try:
                aliases[alias] = (raiz / ruta_str).resolve()
            except Exception:
                pass
    return aliases


def _extraer_aliases_nuxt(texto: str, raiz: Path) -> dict[str, Path]:
    """
    Extrae alias: { ... } de nuxt.config.js/ts.
    Nuxt usa ~ y @ como aliases de la raíz por defecto; aquí capturamos
    los que el usuario define explícitamente.
    """
    aliases: dict[str, Path] = {}
    bloque = re.search(r"\balias\s*:\s*\{([^}]+)\}", texto, re.DOTALL)
    if not bloque:
        return aliases
    patron = re.compile(
        r"""['"]?([@~][\w/.-]*|[\w][\w/.-]*)['"']?\s*:\s*['"]([^'"]+)['"]"""
    )
    for m in patron.finditer(bloque.group(1)):
        alias    = m.group(1)
        ruta_str = (m.group(2)
                    .replace("~", str(raiz))
                    .replace("<rootDir>", str(raiz))
                    .replace("__dirname", str(raiz)))
        try:
            aliases[alias] = Path(ruta_str).resolve()
        except Exception:
            pass
    return aliases


def _extraer_aliases_jest(texto: str, raiz: Path) -> dict[str, Path]:
    """
    Extrae moduleNameMapper de jest.config.js/ts.
    Ej: '^@/(.*)$': '<rootDir>/src/$1'  →  '@' → raiz/src
    """
    aliases: dict[str, Path] = {}
    bloque = re.search(r"moduleNameMapper\s*:\s*\{([^}]+)\}", texto, re.DOTALL)
    if not bloque:
        return aliases
    patron = re.compile(
        r"""['"]\^?([@~][\w/.-]*?)(?:/\(|\\/).*?['\"]\s*:\s*['"]<rootDir>/([^'"$]*)"""
    )
    for m in patron.finditer(bloque.group(1)):
        alias    = m.group(1)
        ruta_str = m.group(2).rstrip("/")
        if ruta_str:
            try:
                aliases[alias] = (raiz / ruta_str).resolve()
            except Exception:
                pass
    return aliases


def _extraer_aliases_babel(texto: str, raiz: Path) -> dict[str, Path]:
    """
    Extrae el bloque alias: { ... } del plugin module-resolver en
    babel.config.js, .babelrc o equivalentes.
    """
    aliases: dict[str, Path] = {}
    bloque = re.search(r"\balias\s*:\s*\{([^}]+)\}", texto, re.DOTALL)
    if not bloque:
        return aliases
    patron = re.compile(
        r"""['"]?([@~][\w/.-]*)['"']?\s*:\s*['"]([^'"]+)['"]"""
    )
    for m in patron.finditer(bloque.group(1)):
        alias    = m.group(1)
        ruta_str = m.group(2).lstrip("./")
        try:
            aliases[alias] = (raiz / ruta_str).resolve()
        except Exception:
            pass
    return aliases


def cargar_aliases(raiz: Path) -> dict[str, Path]:
    """
    Busca archivos de configuración en la raíz del proyecto y extrae los aliases
    de módulos definidos en cada uno. Devuelve:
        { alias_prefix: Path_absoluto_a_carpeta_destino }

    La última escritura gana si el mismo alias aparece en varios archivos.
    Los archivos se leen en orden de prioridad creciente (tsconfig al final
    porque suele ser la fuente canónica en proyectos TS).
    """
    aliases: dict[str, Path] = {}

    # Configs JS con parser de texto plano
    configs_texto = [
        ("webpack.config.js",  _extraer_aliases_webpack),
        ("webpack.config.ts",  _extraer_aliases_webpack),
        ("nuxt.config.js",     _extraer_aliases_nuxt),
        ("nuxt.config.ts",     _extraer_aliases_nuxt),
        ("jest.config.js",     _extraer_aliases_jest),
        ("jest.config.ts",     _extraer_aliases_jest),
        ("babel.config.js",    _extraer_aliases_babel),
        ("babel.config.json",  _extraer_aliases_babel),
        (".babelrc",           _extraer_aliases_babel),
        (".babelrc.js",        _extraer_aliases_babel),
        # Vite al final para que pise webpack si ambos existen
        ("vite.config.js",     _extraer_aliases_vite),
        ("vite.config.ts",     _extraer_aliases_vite),
    ]
    for nombre, fn in configs_texto:
        ruta = raiz / nombre
        if ruta.exists():
            try:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
                aliases.update(fn(texto, raiz))
            except Exception:
                pass

    # tsconfig / jsconfig: JSON con comentarios, mayor prioridad
    for nombre in ("jsconfig.json", "tsconfig.base.json", "tsconfig.json"):
        ruta = raiz / nombre
        if ruta.exists():
            try:
                datos = _leer_json_permisivo(
                    ruta.read_text(encoding="utf-8", errors="replace")
                )
                aliases.update(_extraer_aliases_tsconfig(datos, raiz))
            except Exception:
                pass

    return aliases


# ── Resolución de importaciones a rutas de archivo ───────────────────────────

# Extensiones a probar cuando el import no trae extensión explícita
_EXTENSIONES_RESOLVE = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
                        ".vue", ".svelte", ".astro")


def resolver_importacion(
    imp: str,
    archivo: Path,
    raiz: Path,
    indice_archivos: dict[Path, str],
    aliases: dict[str, Path],
) -> str | None:
    """
    Resuelve un string de importación a la ruta relativa posix del archivo
    dentro del proyecto, o None si no se puede resolver internamente.

    Orden de resolución:
      1. Ruta relativa (empieza con '.' o '..')
      2. Alias conocido (prefijo más largo que coincida)
      3. Módulo externo sin alias → None (ignorado)

    Para cada candidato se prueban:
      - Ruta exacta (si ya tiene extensión)
      - Ruta + cada extensión de _EXTENSIONES_RESOLVE
      - Ruta/index + cada extensión (patrón barrel/index)
    """
    ruta_candidata: Path | None = None

    if imp.startswith("."):
        # Ruta relativa al directorio del archivo importador
        ruta_candidata = (archivo.parent / imp).resolve()
    else:
        # Buscar el alias más largo que coincida (evita que '@' pise '@components')
        mejor_alias: str | None = None
        mejor_len = 0
        for prefijo in aliases:
            if (imp == prefijo or imp.startswith(prefijo + "/")) and len(prefijo) > mejor_len:
                mejor_alias = prefijo
                mejor_len   = len(prefijo)

        if mejor_alias is not None:
            destino = aliases[mejor_alias]
            resto   = imp[len(mejor_alias):].lstrip("/")
            ruta_candidata = (destino / resto).resolve() if resto else destino

    if ruta_candidata is None:
        return None  # módulo externo sin alias conocido, se ignora

    # Búsqueda 1: coincidencia exacta (import con extensión explícita)
    if ruta_candidata in indice_archivos:
        return indice_archivos[ruta_candidata]

    # Búsqueda 2: añadir extensión
    for ext in _EXTENSIONES_RESOLVE:
        candidato = Path(str(ruta_candidata) + ext)
        if candidato in indice_archivos:
            return indice_archivos[candidato]

    # Búsqueda 3: barrel / index file
    for ext in _EXTENSIONES_RESOLVE:
        candidato = ruta_candidata / f"index{ext}"
        if candidato in indice_archivos:
            return indice_archivos[candidato]

    return None


# ── Análisis de importaciones ─────────────────────────────────────────────────

def extraer_importaciones(archivo: Path) -> list[str]:
    """
    Devuelve la lista de strings de importación crudos del archivo.

    Python:
      - Imports absolutos: devuelve nombre de módulo de primer nivel.
      - Imports relativos (level > 0): intenta resolver a ruta real relativa
        al archivo actual; si no existe en disco, devuelve el especificador
        con puntos (ej: '..utils.helpers').

    JS/TS/JSX/TSX/MJS/CJS:
      - import ... from '...'           (incluyendo multilínea con {})
      - export { ... } from '...'       (re-exports nombrados y default)
      - export * from '...'             (re-exports de namespace)
      - import('...')                   (dinámico con string literal)
      - import(`./prefijo/${var}`)      (dinámico con template literal: extrae prefijo estático)
      - require('...')                  (CommonJS, incluso con desestructuración)
      - Comentarios inline /* ... */ en la sentencia son ignorados correctamente.

    Vue/Svelte: igual que JS/TS dentro del bloque <script>.
    """
    importaciones: list[str] = []
    try:
        texto = archivo.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return importaciones

    # ── Python ────────────────────────────────────────────────────────────────
    if archivo.suffix == ".py":
        try:
            tree = ast.parse(texto)
        except SyntaxError:
            return importaciones

        dir_actual = archivo.parent

        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Import):
                # import os, import os.path  → módulo de primer nivel
                for alias in nodo.names:
                    importaciones.append(alias.name.split(".")[0])

            elif isinstance(nodo, ast.ImportFrom):
                level  = nodo.level   # 0 = absoluto, 1 = '.', 2 = '..', etc.
                module = nodo.module  # puede ser None en "from . import x"

                if level == 0:
                    # Absoluto: solo módulo de primer nivel
                    if module:
                        importaciones.append(module.split(".")[0])
                else:
                    # Relativo: intentar resolver a ruta real
                    # Subimos (level-1) directorios desde el directorio del archivo
                    base = dir_actual
                    for _ in range(level - 1):
                        base = base.parent

                    if module:
                        # "from ..utils.helpers import parse_date"
                        # → base/../utils/helpers  (convertimos '.' en separador)
                        subpath = Path(*module.split("."))
                        candidato = base / subpath
                    else:
                        # "from . import models"
                        # Los nombres importados son submódulos directos de base
                        # Añadimos cada nombre como candidato de archivo/paquete
                        for alias in nodo.names:
                            sub = base / alias.name
                            # ¿es un archivo .py?
                            if (base / f"{alias.name}.py").exists():
                                try:
                                    importaciones.append(
                                        str((base / f"{alias.name}.py")
                                            .relative_to(dir_actual))
                                        .replace("\\", "/")
                                    )
                                except ValueError:
                                    importaciones.append(
                                        f"{'.' * level}{alias.name}"
                                    )
                            # ¿es un paquete?
                            elif (sub / "__init__.py").exists():
                                try:
                                    importaciones.append(
                                        str(sub.relative_to(dir_actual))
                                        .replace("\\", "/")
                                    )
                                except ValueError:
                                    importaciones.append(
                                        f"{'.' * level}{alias.name}"
                                    )
                            else:
                                # No existe en disco; devolvemos especificador legible
                                importaciones.append(f"{'.' * level}{alias.name}")
                        continue  # ya procesamos los names, siguiente nodo

                    # Resolver candidato: ¿archivo .py o paquete?
                    if (Path(str(candidato) + ".py")).exists():
                        ruta_resuelta = Path(str(candidato) + ".py")
                    elif (candidato / "__init__.py").exists():
                        ruta_resuelta = candidato
                    else:
                        ruta_resuelta = None

                    if ruta_resuelta is not None:
                        try:
                            importaciones.append(
                                str(ruta_resuelta.relative_to(dir_actual))
                                .replace("\\", "/")
                            )
                        except ValueError:
                            # Fuera del directorio actual → ruta posix relativa desde raíz
                            importaciones.append(str(ruta_resuelta).replace("\\", "/"))
                    else:
                        # Fallback: especificador con puntos, igual que antes
                        especificador = "." * level + (module or "")
                        importaciones.append(especificador)

        return list(dict.fromkeys(importaciones))

    # ── JS / TS / JSX / TSX / MJS / CJS ──────────────────────────────────────
    # ── Vue y Svelte (solo dentro de <script>) ────────────────────────────────

    if archivo.suffix in {".vue", ".svelte"}:
        bloques = [
            m.group(1)
            for m in re.finditer(r"<script[^>]*>([\s\S]*?)</script>",
                                 texto, re.IGNORECASE)
        ]
        cuerpo = "\n".join(bloques)
    elif archivo.suffix in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}:
        cuerpo = texto
    else:
        return importaciones

    # Paso 1 — proteger strings para que los comentarios dentro de ellos
    # no interfieran con la limpieza posterior.
    _strings_protegidos: list[str] = []

    def _guardar_string(m: re.Match) -> str:
        idx = len(_strings_protegidos)
        _strings_protegidos.append(m.group(0))
        return f"__STRLIT_{idx}__"

    # Template literals, strings dobles, strings simples
    _patron_strings = re.compile(
        r'(`[^`\\]*(?:\\.[^`\\]*)*`)'
        r'|("(?:[^"\\]|\\.)*")'
        r"|('(?:[^'\\]|\\.)*')",
        re.DOTALL,
    )
    cuerpo_safe = _patron_strings.sub(_guardar_string, cuerpo)

    # Paso 2 — eliminar comentarios de bloque /* ... */ y de línea //
    cuerpo_safe = re.sub(r"/\*[\s\S]*?\*/", " ", cuerpo_safe)
    cuerpo_safe = re.sub(r"//[^\n]*", "", cuerpo_safe)

    # Paso 3 — restaurar strings
    def _restaurar_string(m: re.Match) -> str:
        return _strings_protegidos[int(m.group(1))]

    cuerpo_safe = re.sub(r"__STRLIT_(\d+)__", _restaurar_string, cuerpo_safe)

    def _extraer_especificadores_js(cuerpo: str) -> list[str]:
        """
        Extrae todos los especificadores de módulo de un fragmento JS/TS.
        Cubre:
          • import ... from 'x'                (estático, incluyendo multilínea)
          • export { ... } from 'x'            (re-export nombrado / default)
          • export * from 'x'                  (re-export namespace)
          • import('x')                        (dinámico, string literal)
          • import(`./pre/${var}`)             (dinámico, template literal)
          • require('x')  /  require("x")      (CJS, incl. desestructuración)
        """
        encontrados: list[str] = []

        # ── 1. import estático + re-exports ───────────────────────────────────
        #   import ... from 'x'
        #   export { ... } from 'x'
        #   export * from 'x'
        #   export * as ns from 'x'
        # El bloque entre el keyword y from puede ser multilínea; usamos [\s\S]*?
        _patron_static = re.compile(
            r"""
            (?:
                # a) import <anything> from 'x'
                \bimport\b
                (?:
                    \s+type\b           # import type (TS)
                )?
                \s*
                (?:
                    # lado izquierdo: { A, B }, * as ns, DefaultExport, combinaciones
                    [\s\S]*?
                )?
                \bfrom\b
            |
                # b) export { ... } from 'x'  /  export * from 'x'
                \bexport\b
                (?:\s+type\b)?          # export type (TS)
                \s*
                (?:\{[\s\S]*?\}|\*)
                (?:\s+as\s+\w+)?
                \s*
                \bfrom\b
            )
            \s*
            (?:
                ['"]([^'"]+)['"]        # grupo 1: string simple/doble
            )
            """,
            re.VERBOSE | re.DOTALL,
        )
        for m in _patron_static.finditer(cuerpo):
            especificador = m.group(1)
            if especificador:
                encontrados.append(especificador)

        # ── 2. import side-effect:  import './reset.css' ──────────────────────
        _patron_side = re.compile(
            r"""\bimport\s+['"]([^'"]+)['"]"""
        )
        for m in _patron_side.finditer(cuerpo):
            encontrados.append(m.group(1))

        # ── 3. import() dinámico con string literal ───────────────────────────
        _patron_dyn_str = re.compile(
            r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)"""
        )
        for m in _patron_dyn_str.finditer(cuerpo):
            encontrados.append(m.group(1))

        # ── 4. import() dinámico con template literal  `./pre/${var}` ─────────
        # Extraemos la parte estática anterior al primer ${
        _patron_dyn_tpl = re.compile(
            r"""\bimport\s*\(\s*`([^`$]*)\$\{"""
        )
        for m in _patron_dyn_tpl.finditer(cuerpo):
            prefijo = m.group(1)  # ej: "./plugins/"
            if prefijo:  # solo si hay algo que resolver
                encontrados.append(prefijo)

        # ── 5. require('x') — CJS ────────────────────────────────────────────
        _patron_require = re.compile(
            r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)"""
        )
        for m in _patron_require.finditer(cuerpo):
            encontrados.append(m.group(1))

        return encontrados

    importaciones = _extraer_especificadores_js(cuerpo_safe)
    return list(dict.fromkeys(importaciones))


# ── Helpers ───────────────────────────────────────────────────────────────────

def debe_ignorar(path: Path, ignorar: set) -> bool:
    return any(parte in ignorar for parte in path.parts)


def en_carpetas_permitidas(path: Path, raiz: Path, incluir_solo: list | None) -> bool:
    if not incluir_solo:
        return True
    try:
        relativo = path.relative_to(raiz)
        return any(relativo.parts[0] == c for c in incluir_solo)
    except ValueError:
        return False


def _aplicar_filtros(archivos: list[Path], raiz: Path, config: dict,
                      omitir_autogenerados: bool = False,
                      limite_lineas: int | None = None,
                      verbose: bool = False) -> list[Path]:
    resultado = []
    for archivo in archivos:
        if not archivo.is_file():
            continue
        try:
            rel = archivo.relative_to(raiz)
        except ValueError:
            continue
        if debe_ignorar(rel, config["ignorar"]):
            continue
        if not en_carpetas_permitidas(archivo, raiz, config["incluir_solo"]):
            continue
        if archivo.suffix not in config["extensiones"]:
            continue
        limite = limite_lineas if limite_lineas is not None else config.get("limite_lineas")
        omitir = omitir_autogenerados or config.get("omitir_autogenerados", False)
        if omitir and es_autogenerado(archivo, limite, verbose):
            continue
        elif limite and not omitir:
            if es_autogenerado(archivo, limite, verbose):
                continue
        resultado.append(archivo)
    return ordenar_archivos(resultado)


def recolectar_archivos(raiz: Path, config: dict,
                         omitir_autogenerados: bool = False,
                         limite_lineas: int | None = None,
                         verbose: bool = False) -> list[Path]:
    todos = [archivo for archivo in raiz.rglob("*")]
    return _aplicar_filtros(todos, raiz, config, omitir_autogenerados, limite_lineas, verbose)


def filtrar_por_config(archivos: list[Path], raiz: Path, config: dict,
                        omitir_autogenerados: bool = False,
                        limite_lineas: int | None = None,
                        verbose: bool = False) -> list[Path]:
    return _aplicar_filtros(archivos, raiz, config, omitir_autogenerados, limite_lineas, verbose)


def construir_arbol(archivos: list[Path], raiz: Path) -> str:
    lineas = [f"{raiz.resolve().name}/"]
    directorios_vistos: set = set()
    for archivo in archivos:
        relativo = archivo.relative_to(raiz)
        partes   = relativo.parts
        for i, parte in enumerate(partes[:-1]):
            clave = partes[: i + 1]
            if clave not in directorios_vistos:
                directorios_vistos.add(clave)
                lineas.append(f"{'  ' * (i + 1)}{parte}/")
        lineas.append(f"{'  ' * len(partes)}{partes[-1]}")
    return "\n".join(lineas)

# ── Lectura con compresión opcional ──────────────────────────────────────────

def leer_contenido(archivo: Path, config: dict) -> str:
    """
    Lee el contenido de un archivo, aplicando compresión si está activada.
    Devuelve siempre una string con el contenido listo para escribir.
    """
    try:
        contenido = archivo.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"# [No se pudo leer: {e}]\n"

    nivel_str = config.get("comprimir")
    if not nivel_str or not COMPRESION_DISPONIBLE:
        return contenido

    if archivo.suffix not in EXTENSIONES_SOPORTADAS:
        return contenido

    try:
        resultado = comprimir_texto(contenido, archivo.suffix, NivelCompresion(nivel_str))
        return resultado["texto"]
    except Exception:
        return contenido  # fallback silencioso


# ── Escritura: modo estándar ──────────────────────────────────────────────────

def escribir_encabezado(f, config: dict, raiz: Path, titulo: str,
                         n_archivos: int, nota_extra: str = "") -> None:
    sep = "=" * 72
    f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"# {titulo}\n")
    f.write(f"# Carpeta origen: {raiz}\n")
    if config.get("descripcion"):
        f.write(f"\n# DESCRIPCIÓN DEL PROYECTO\n# {config['descripcion']}\n")
    f.write(f"# Extensiones incluidas : {', '.join(sorted(config['extensiones']))}\n")
    f.write(f"# Ignorados             : {', '.join(sorted(config['ignorar']))}\n")
    if config["incluir_solo"]:
        f.write(f"# Carpetas incluidas    : {', '.join(config['incluir_solo'])}\n")
    if nota_extra:
        f.write(f"# {nota_extra}\n")
    f.write(f"# Total de archivos     : {n_archivos}\n")
    f.write(f"\n# {sep}\n\n")


def _escribir_y_estimar(salida_path: Path, writer_fn, modelo: str,
                         incluir_en_archivo: bool = False) -> dict | None:
    with open(salida_path, "w", encoding="utf-8") as f:
        writer_fn(f)
    try:
        texto = salida_path.read_text(encoding="utf-8", errors="replace")
        est   = estimar_tokens(texto, modelo)
        if incluir_en_archivo:
            with open(salida_path, "a", encoding="utf-8") as f:
                f.write(formatear_estimacion_tokens(est))
        return est
    except Exception:
        return None


def escribir_archivo(salida_path: Path, archivos: list[Path], raiz: Path,
                      config: dict, titulo: str, nota_extra: str = "",
                      modelo: str = "default") -> dict | None:
    sep = "=" * 72

    def writer(f):
        escribir_encabezado(f, config, raiz, titulo, len(archivos), nota_extra)
        f.write(f"# ÁRBOL DE ARCHIVOS\n# {sep}\n\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n\n")
        f.write(f"# {sep}\n# CONTENIDO\n# {sep}\n")
        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            f.write(f"\n\n# --- {relativo} ---\n\n")
            contenido = leer_contenido(archivo, config)
            f.write(contenido)
            if not contenido.endswith("\n"):
                f.write("\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=True)


def _construir_grafo(archivos: list[Path], raiz: Path) -> list[tuple[str, list[str]]]:
    """
    Construye el grafo de dependencias internas entre los archivos del proyecto.

    Usa resolver_importacion con:
      - Un índice por ruta absoluta (evita colisiones de stem entre carpetas)
      - Los aliases leídos desde los archivos de config del proyecto

    Devuelve una lista de (ruta_relativa_posix, [deps_relativas_posix]).
    Solo incluye archivos que tienen al menos una dependencia interna resuelta.
    """
    indice_archivos = {a.resolve(): a.relative_to(raiz).as_posix() for a in archivos}
    aliases         = cargar_aliases(raiz)
    dep_lines: list[tuple[str, list[str]]] = []

    for archivo in archivos:
        importaciones = extraer_importaciones(archivo)
        deps_internas: list[str] = []
        for imp in importaciones:
            resuelto = resolver_importacion(imp, archivo, raiz, indice_archivos, aliases)
            if resuelto:
                deps_internas.append(resuelto)
        if deps_internas:
            rel = archivo.relative_to(raiz).as_posix()
            dep_lines.append((rel, deps_internas))

    return dep_lines


def escribir_context_only(salida_path: Path, archivos: list[Path],
                           raiz: Path, config: dict, commits: list[str],
                           modelo: str = "default") -> dict | None:
    sep = "=" * 72

    def writer(f):
        escribir_encabezado(f, config, raiz, "MAPA DE CONTEXTO (sin código)", len(archivos))
        if commits:
            f.write(f"# ÚLTIMOS COMMITS\n# {sep}\n")
            for c in commits:
                f.write(f"#   {c}\n")
            f.write("\n")
        f.write(f"# ÁRBOL DE ARCHIVOS\n# {sep}\n\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n\n")
        f.write(f"# {sep}\n# FICHA POR ARCHIVO\n# {sep}\n\n")
        for archivo in archivos:
            relativo      = archivo.relative_to(raiz)
            importaciones = extraer_importaciones(archivo)
            try:
                lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            except Exception:
                lineas = "?"
            f.write(f"## {relativo}\n")
            f.write(f"   Líneas   : {lineas}\n")
            f.write(f"   Extensión: {archivo.suffix}\n")
            if importaciones:
                f.write(f"   Importa  : {', '.join(importaciones[:15])}")
                if len(importaciones) > 15:
                    f.write(f" ... (+{len(importaciones)-15} más)")
                f.write("\n")
            else:
                f.write("   Importa  : (ninguna detectada)\n")
            f.write("\n")

        f.write(f"# {sep}\n# GRAFO DE DEPENDENCIAS INTERNAS\n# {sep}\n\n")
        f.write("# (Muestra qué archivos del proyecto se importan entre sí)\n\n")

        dep_lines = _construir_grafo(archivos, raiz)
        if dep_lines:
            for rel, deps in dep_lines:
                f.write(f"  {rel}\n")
                for d in deps:
                    f.write(f"    └─ {d}\n")
                f.write("\n")
        else:
            f.write("  (No se detectaron dependencias internas entre los archivos incluidos)\n\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=True)


# ── Escritura: modo IA mapa (--co + --objetivo) ──────────────────────────────
#
# Combina el contenido de --co (estructura sin código) con el formato XML
# optimizado para IA. Útil cuando querés que la IA analice la arquitectura
# del proyecto y decida qué archivos necesita ver para cumplir el objetivo,
# sin gastar tokens en el código completo.
#
# El bloque <response_instructions> en este caso le pide a la IA que:
# 1. Analice la estructura y dependencias
# 2. Identifique qué archivos son relevantes para el objetivo
# 3. Devuelva el follow_up_command con esos archivos

def escribir_mapa_ia(salida_path: Path, archivos: list[Path],
                      raiz: Path, config: dict, commits: list[str] | None = None,
                      modelo: str = "default") -> dict | None:
    """
    Genera un mapa de contexto (sin código) optimizado para ser leído por una IA.
    Combina la info estructural de --co con el formato XML de --objetivo.
    """
    objetivo    = config.get("objetivo", "")
    descripcion = config.get("descripcion", "")
    ts          = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    modelo_flag = f" --modelo {config.get('modelo', 'default')}" \
                  if config.get("modelo") and config.get("modelo") != "default" else ""
    cmd_followup = (
        f"contexto {raiz} --objetivo \"{objetivo}\"{modelo_flag} --archivos "
        f"[ruta/archivo1] [ruta/archivo2] ..."
    )

    def writer(f):
        # ── Metadatos compactos ──────────────────────────────────────────────
        f.write("<context_metadata>\n")
        f.write(f"  generated_at: {ts}\n")
        f.write(f"  project_root: {raiz}\n")
        if descripcion:
            f.write(f"  project_description: {descripcion}\n")
        f.write(f"  file_count: {len(archivos)}\n")
        f.write(f"  extensions_included: {', '.join(sorted(config['extensiones']))}\n")
        if config.get("incluir_solo"):
            f.write(f"  root_dirs_included: {', '.join(config['incluir_solo'])}\n")
        f.write(f"  content_type: structure_only (no source code)\n")
        if commits:
            f.write(f"  recent_commits:\n")
            for c in commits[:5]:
                f.write(f"    - {c}\n")
        f.write("</context_metadata>\n\n")

        # ── Objetivo / tarea ─────────────────────────────────────────────────
        f.write("<task>\n")
        f.write(f"  {objetivo}\n")
        f.write("</task>\n\n")

        # ── Árbol de archivos ────────────────────────────────────────────────
        f.write("<file_tree>\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n</file_tree>\n\n")

        # ── Fichas por archivo ───────────────────────────────────────────────
        f.write("<file_index>\n")
        for archivo in archivos:
            relativo      = archivo.relative_to(raiz)
            importaciones = extraer_importaciones(archivo)
            try:
                n_lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            except Exception:
                n_lineas = "?"
            f.write(f"  <file path=\"{relativo.as_posix()}\"")
            f.write(f" lines=\"{n_lineas}\"")
            f.write(f" ext=\"{archivo.suffix}\"")
            if importaciones:
                deps_str = ", ".join(importaciones[:15])
                if len(importaciones) > 15:
                    deps_str += f" (+{len(importaciones)-15})"
                f.write(f" imports=\"{deps_str}\"")
            f.write(" />\n")
        f.write("</file_index>\n\n")

        # ── Grafo de dependencias internas ───────────────────────────────────
        dep_lines = _construir_grafo(archivos, raiz)

        f.write("<dependency_graph>\n")
        if dep_lines:
            for rel, deps in dep_lines:
                f.write(f"  <file path=\"{rel}\" depends_on=\"{', '.join(deps)}\" />\n")
        else:
            f.write("  <!-- no internal dependencies detected -->\n")
        f.write("</dependency_graph>\n\n")

        # ── Instrucción de respuesta ─────────────────────────────────────────
        f.write("<response_instructions>\n")
        f.write("  You are receiving the structural map of a codebase (no source code).\n")
        f.write("  Your task is defined in <task>.\n\n")
        f.write("  STEP 1 — Analyze the structure:\n")
        f.write("    Use <file_tree>, <file_index>, and <dependency_graph> to understand\n")
        f.write("    the project layout, module sizes, and how files relate to each other.\n\n")
        f.write("  STEP 2 — Identify relevant files:\n")
        f.write("    Based on the structure and your task, determine which files you need\n")
        f.write("    to read to provide a complete and accurate response.\n\n")
        f.write("  STEP 3 — Output the follow-up command:\n")
        f.write("    Output EXACTLY this block (copy-paste ready, no surrounding text),\n")
        f.write("    replacing the placeholders with the actual file paths you need:\n\n")
        f.write("    <follow_up_command>\n")
        f.write(f"    {cmd_followup}\n")
        f.write("    </follow_up_command>\n\n")
        f.write("    Use forward slashes. Paths are relative to project_root.\n")
        f.write("    Be selective — only request files genuinely needed for the task.\n")
        f.write("</response_instructions>\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=False)


# ── Escritura: modo IA (--objetivo) ──────────────────────────────────────────
#
# Este formato está optimizado para consumo por modelos de lenguaje:
# - Sin decoración visual innecesaria (# ===, emojis, comentarios de usuario)
# - Estructura semántica explícita con etiquetas XML-style que los LLMs
#   reconocen bien como delimitadores de sección
# - Metadatos compactos en bloque único al inicio
# - Instrucción de tarea en primer plano, no enterrada entre metadatos
# - Separadores de archivo limpios con ruta completa relativa
# - Sin bloques orientados al humano (instrucciones de terminal, tips)
# - Comando de seguimiento al final, fuera del contenido principal
#
# Principios aplicados:
# 1. Lo que la IA necesita leer primero va primero (objetivo/tarea)
# 2. El contexto técnico (archivos) va inmediatamente después, sin ruido
# 3. Las instrucciones de respuesta son precisas y sin ambigüedad
# 4. El formato es consistente para facilitar el parsing interno del modelo

def escribir_archivo_ia(salida_path: Path, archivos: list[Path], raiz: Path,
                         config: dict, es_solicitado: bool = False,
                         commits: list[str] | None = None,
                         modelo: str = "default",
                         es_segunda_vuelta: bool = False) -> dict | None:
    """
    Genera un archivo de contexto optimizado para ser leído directamente por una IA.
    Sin decoración visual. Estructura semántica con etiquetas tipo XML.
    """
    objetivo    = config.get("objetivo", "")
    descripcion = config.get("descripcion", "")
    ts          = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    modelo_flag = f" --modelo {config.get('modelo', 'default')}" \
                  if config.get("modelo") and config.get("modelo") != "default" else ""
    cmd_followup = (
        f"contexto {raiz} --objetivo \"{objetivo}\"{modelo_flag} --archivos "
        f"[ruta/archivo1] [ruta/archivo2] ..."
    )

    def writer(f):
        # ── Bloques omitidos en segunda vuelta (--continua) ──────────────────
        if not es_segunda_vuelta:
            # ── Metadatos compactos ──────────────────────────────────────────────
            f.write("<context_metadata>\n")
            f.write(f"  generated_at: {ts}\n")
            f.write(f"  project_root: {raiz}\n")
            if descripcion:
                f.write(f"  project_description: {descripcion}\n")
            f.write(f"  file_count: {len(archivos)}\n")
            f.write(f"  extensions_included: {', '.join(sorted(config['extensiones']))}\n")
            if config.get("incluir_solo"):
                f.write(f"  root_dirs_included: {', '.join(config['incluir_solo'])}\n")
            if commits:
                f.write(f"  recent_commits:\n")
                for c in commits[:5]:
                    f.write(f"    - {c}\n")
            f.write("</context_metadata>\n\n")

            # ── Objetivo / tarea ─────────────────────────────────────────────────
            f.write("<task>\n")
            f.write(f"  {objetivo}\n")
            f.write("</task>\n\n")

            # ── Índice de archivos ───────────────────────────────────────────────
            f.write("<file_index>\n")
            for archivo in archivos:
                relativo      = archivo.relative_to(raiz)
                importaciones = extraer_importaciones(archivo)
                try:
                    n_lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
                except Exception:
                    n_lineas = "?"
                f.write(f"  <file path=\"{relativo.as_posix()}\"")
                f.write(f" lines=\"{n_lineas}\"")
                f.write(f" ext=\"{archivo.suffix}\"")
                if importaciones:
                    deps_str = ", ".join(importaciones[:15])
                    if len(importaciones) > 15:
                        deps_str += f" (+{len(importaciones)-15})"
                    f.write(f" imports=\"{deps_str}\"")
                f.write(" />\n")
            f.write("</file_index>\n\n")

            f.write("<codebase>\n")

        # ── Contenido de archivos ────────────────────────────────────────────
        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            
            if es_segunda_vuelta:
                # Formato ultra crudo para --continua: solo la ruta antes del código
                f.write(f"### Archivo: {relativo.as_posix()} ###\n")
            else:
                f.write(f"\n<file path=\"{relativo.as_posix()}\">\n")
            
            contenido = leer_contenido(archivo, config)
            f.write(contenido)
            if not contenido.endswith("\n"):
                f.write("\n")
                
            if not es_segunda_vuelta:
                f.write(f"</file>\n")

        # ── Cierre e instrucciones (solo en primera vuelta) ──────────────────
        if not es_segunda_vuelta:
            f.write("\n</codebase>\n\n")
            
            f.write("<response_instructions>\n")
            if not es_solicitado:
                f.write("  You are receiving the full codebase for the project described above.\n")
                f.write("  Your task is defined in <task>.\n\n")
                f.write("  STEP 1 — Identify missing context:\n")
                f.write("    If you need additional files not present in <codebase> to complete\n")
                f.write("    the task, list each one with a one-sentence reason.\n\n")
                f.write("  STEP 2 — Provide a follow-up command:\n")
                f.write("    If additional files are needed, output EXACTLY this block\n")
                f.write("    (copy-paste ready, no surrounding text):\n\n")
                f.write("    <follow_up_command>\n")
                f.write(f"    {cmd_followup}\n")
                f.write("    </follow_up_command>\n\n")
                f.write("    Replace the placeholder paths with real relative paths.\n")
                f.write("    Use forward slashes. Paths are relative to project_root.\n\n")
                f.write("  STEP 3 — If you already have enough context:\n")
                f.write("    State that explicitly, then proceed directly with your response.\n")
                f.write("    Do not output <follow_up_command>.\n")
            else:
                f.write("  You are receiving the specific files you requested.\n")
                f.write("  Your task is defined in <task>.\n")
                f.write("  You now have sufficient context. Proceed with your full response.\n")
                f.write("  Do not ask for additional files.\n")
            f.write("</response_instructions>\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=False)
# ── Preview y Stats ───────────────────────────────────────────────────────────

def mostrar_preview(archivos: list[Path], raiz: Path, config: dict,
                    modelo: str) -> None:
    """Muestra qué archivos se incluirían sin generar nada."""
    print(f"\n[PREVIEW] {len(archivos)} archivo(s) que se incluirían:\n")

    ext_count: dict[str, int] = {}
    total_lineas = 0

    for archivo in archivos:
        relativo = str(archivo.relative_to(raiz))
        try:
            n_lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
        except Exception:
            n_lineas = 0
        total_lineas += n_lineas
        ext = archivo.suffix
        ext_count[ext] = ext_count.get(ext, 0) + 1
        print(f"  {relativo:<60}  {n_lineas:>5} líneas")

    print(f"\n[PREVIEW] Resumen:")
    print(f"  Archivos    : {len(archivos)}")
    print(f"  Líneas total: {total_lineas:,}".replace(",", "."))
    for ext, n in sorted(ext_count.items()):
        print(f"  {ext:<8}: {n} archivo(s)")

    try:
        texto_total = "".join(
            a.read_text(encoding="utf-8", errors="replace") for a in archivos
        )
        est = estimar_tokens(texto_total, modelo)
        tokens_fmt = f"{est['tokens']:,}".replace(",", ".")
        print(f"\n[PREVIEW] Estimación de tokens (aprox, sin encabezados):")
        print(f"  Modelo  : {est['info_modelo']['nombre_display']}")
        print(f"  Tokens  : ~{tokens_fmt}")
        if est["costo_usd"] is not None:
            print(f"  Costo   : ~${est['costo_usd']:.4f} USD")
        if est["porcentaje_window"] is not None:
            pct    = est["porcentaje_window"]
            estado = "✓ entra" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE")
            cw_fmt = f"{est['info_modelo']['context_window']:,}".replace(",", ".")
            print(f"  Window  : {pct:.1f}% de {cw_fmt} tokens  [{estado}]")
    except Exception:
        pass
    print()


def mostrar_stats(archivos: list[Path], raiz: Path, modelo: str) -> None:
    """Estimación de tokens en consola, sin generar archivos."""
    print(f"\n[STATS] Analizando {len(archivos)} archivo(s)...\n")
    try:
        texto_total = "".join(
            a.read_text(encoding="utf-8", errors="replace") for a in archivos
        )
        est  = estimar_tokens(texto_total, modelo)
        info = est["info_modelo"]
        tokens_fmt = f"{est['tokens']:,}".replace(",", ".")
        chars_fmt  = f"{est['chars']:,}".replace(",", ".")
        print(f"  Modelo           : {info['nombre_display']}")
        print(f"  Caracteres       : {chars_fmt}")
        print(f"  Tokens estimados : ~{tokens_fmt}")
        if est["costo_usd"] is not None:
            print(f"  Costo estimado   : ~${est['costo_usd']:.4f} USD  (solo tokens de entrada)")
        else:
            print(f"  Costo estimado   : no disponible (varía según proveedor)")
        if est["porcentaje_window"] is not None:
            pct    = est["porcentaje_window"]
            estado = "✓ entra" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE")
            cw_fmt = f"{info['context_window']:,}".replace(",", ".")
            print(f"  Context window   : {pct:.1f}% de {cw_fmt} tokens  [{estado}]")
        print()
    except Exception as e:
        print(f"[ERROR] No se pudo calcular la estimación: {e}\n")

# ── Logs de salida ────────────────────────────────────────────────────────────

def _log_ok(label: str, path: Path, n_archivos: int, est: dict | None) -> None:
    if est:
        tokens_fmt = f"{est['tokens']:,}".replace(",", ".")
        partes     = [f"~{tokens_fmt} tokens"]
        if est["costo_usd"] is not None:
            partes.append(f"~${est['costo_usd']:.4f} USD")
        if est["porcentaje_window"] is not None:
            pct    = est["porcentaje_window"]
            estado = "✓" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE")
            partes.append(f"{pct:.0f}% del context window {estado}")
        token_info = "  [" + "  |  ".join(partes) + "]"
    else:
        token_info = ""
    n = n_archivos
    print(f"[OK]     {label}  →  {path.name}  ({n} archivo{'s' if n != 1 else ''}){token_info}")
    if est and est.get("porcentaje_window") is not None and est["porcentaje_window"] > 100:
        pct = est["porcentaje_window"]
        print(f"[AVISO]  El contexto excede el context window del modelo ({pct:.0f}%).")
        print(f"         Considerá usar --limite, --sin-minimos o 'incluir_solo' en el config.")

# ── Función principal ─────────────────────────────────────────────────────────

def unificar(args: dict) -> None:
    raiz = Path(args["carpeta"]).resolve()

    if not raiz.exists():
        print(f"[ERROR]  La carpeta '{raiz}' no existe.")
        sys.exit(1)

    if args["init"]:
        generar_config_ejemplo(raiz, limpio=args["init_limpio"])
        return

    config     = cargar_config(raiz)
    salida_dir = config["carpeta_salida"]

    # CLI tiene prioridad sobre config file
    if args["limite"] is not None:
        config["limite_lineas"] = args["limite"]
    if args["sin_minimos"]:
        config["omitir_autogenerados"] = True
    if args["objetivo"]:
        config["objetivo"] = args["objetivo"]
    if args["modelo"] is not None:
        config["modelo"] = args["modelo"]
    if args.get("comprimir"):
        config["comprimir"] = args["comprimir"]
    if args["ignorar_extra"]:
        config["ignorar"] = config["ignorar"] | set(args["ignorar_extra"])

    modelo = config.get("modelo", "default")

    try:
        salida_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[ERROR]  No se pudo crear la carpeta de salida '{salida_dir}': {e}")
        sys.exit(1)

    print(f"[CONFIG] Salida en: {salida_dir}")
    if modelo != "default":
        print(f"[CONFIG] Modelo    : {MODELOS_TOKENS[modelo]['nombre_display']}")
    if config.get("comprimir"):
        if COMPRESION_DISPONIBLE:
            print(f"[CONFIG] Compresión  : activada  (nivel={config['comprimir']})")
        else:
            print("[AVISO]  --comprimir requiere compresor.py en la misma carpeta.")
    if args["ignorar_extra"]:
        print(f"[CONFIG] Ignorando extra: {', '.join(args['ignorar_extra'])}")

    con_objetivo = bool(config.get("objetivo"))

    # ── Modo --archivos ───────────────────────────────────────────────────────
    if args["archivos"] is not None:
        archivos_resueltos = []
        for ruta_str in args["archivos"]:
            candidato = (raiz / ruta_str).resolve()
            if not candidato.exists():
                print(f"[AVISO]  Archivo no encontrado, se omite: {ruta_str}")
                continue
            if not candidato.is_file():
                print(f"[AVISO]  No es un archivo, se omite: {ruta_str}")
                continue
            archivos_resueltos.append(candidato)

        if not archivos_resueltos:
            print("[ERROR]  Ninguno de los archivos indicados con --archivos existe.")
            sys.exit(1)

        archivos_resueltos = ordenar_archivos(archivos_resueltos)

        if con_objetivo:
            nombre_salida = objetivo_a_slug(config["objetivo"], "solicitado")
            salida_path   = salida_dir / nombre_salida
            est = escribir_archivo_ia(
                salida_path=salida_path,
                archivos=archivos_resueltos,
                raiz=raiz,
                config=config,
                es_solicitado=True,
                modelo=modelo,
                es_segunda_vuelta=args["continua"],
            )
            _log_ok("Contexto IA solicitado", salida_path, len(archivos_resueltos), est)
        else:
            salida_path = salida_dir / "contexto_solicitado.txt"
            est = escribir_archivo(
                salida_path=salida_path,
                archivos=archivos_resueltos,
                raiz=raiz,
                config=config,
                titulo="CONTEXTO SOLICITADO  |  Objetivo: no especificado",
                modelo=modelo,
            )
            _log_ok("Contexto solicitado", salida_path, len(archivos_resueltos), est)
        return

    todos = recolectar_archivos(
        raiz, config,
        omitir_autogenerados=config.get("omitir_autogenerados", False),
        limite_lineas=config.get("limite_lineas"),
        verbose=args["verbose"],
    )

    if not todos:
        print("[AVISO]  No se encontraron archivos con las extensiones configuradas.")
        return

    # ── Modo --preview ────────────────────────────────────────────────────────
    if args["preview"]:
        mostrar_preview(todos, raiz, config, modelo)
        return

    # ── Modo --stats ──────────────────────────────────────────────────────────
    if args["stats"]:
        mostrar_stats(todos, raiz, modelo)
        return

    # ── Modo --co ─────────────────────────────────────────────────────────────
    if args["co"]:
        commits = obtener_ultimos_commits(raiz)
        if con_objetivo:
            # --co + --objetivo → mapa estructural en formato XML para IA
            nombre_sal = objetivo_a_slug(config["objetivo"], "mapa")
            salida_co  = salida_dir / nombre_sal
            est = escribir_mapa_ia(salida_co, todos, raiz, config, commits, modelo)
            _log_ok("Mapa IA           ", salida_co, len(todos), est)
            print(f"         (estructura sin código, formato IA)")
        else:
            # --co solo → mapa estándar para el humano
            salida_co = salida_dir / config["nombre_salida_co"]
            est = escribir_context_only(salida_co, todos, raiz, config, commits, modelo)
            _log_ok("Mapa de contexto  ", salida_co, len(todos), est)
            print(f"         (sin código fuente)")
            print(f"         Este archivo NO contiene código fuente.")
            print(f"         Úsalo para decidir qué archivos pasarle a la IA.")
            print(f"         Luego ejecuta el script indicando solo esas carpetas en 'incluir_solo'")
            print(f"         o usa --solo-cambios si trabajas con git.")
        return

    # ── Modo --objetivo: contexto completo optimizado para IA ─────────────────
    if con_objetivo:
        commits    = obtener_ultimos_commits(raiz)
        nombre_sal = objetivo_a_slug(config["objetivo"], "contexto")
        salida_ia  = salida_dir / nombre_sal
        est = escribir_archivo_ia(
            salida_path=salida_ia,
            archivos=todos,
            raiz=raiz,
            config=config,
            es_solicitado=False,
            commits=commits,
            modelo=modelo,
        )
        _log_ok("Contexto IA       ", salida_ia, len(todos), est)
        return

    # ── Contexto completo (modo estándar) ─────────────────────────────────────
    if not args["solo_cambios"]:
        salida_completa = salida_dir / config["nombre_salida"]
        est = escribir_archivo(
            salida_path=salida_completa,
            archivos=todos,
            raiz=raiz,
            config=config,
            titulo="CONTEXTO COMPLETO DEL PROYECTO",
            modelo=modelo,
        )
        _log_ok("Contexto completo ", salida_completa, len(todos), est)

    # ── Cambios git ───────────────────────────────────────────────────────────
    modificados_raw = obtener_archivos_modificados(raiz)
    if modificados_raw is None:
        return
    if not modificados_raw:
        print("[OK]     Sin cambios en git — no se genera archivo de cambios.")
        return

    modificados = filtrar_por_config(
        modificados_raw, raiz, config,
        omitir_autogenerados=config.get("omitir_autogenerados", False),
        limite_lineas=config.get("limite_lineas"),
        verbose=args["verbose"],
    )
    if not modificados:
        print("[OK]     Los archivos modificados no coinciden con las extensiones/carpetas configuradas.")
        return

    commits       = obtener_ultimos_commits(raiz)
    lista_nombres = ", ".join(str(m.relative_to(raiz)) for m in modificados)
    nota          = f"Archivos modificados: {lista_nombres}"
    if commits:
        nota += f" | Commits recientes: {' / '.join(commits[:3])}"

    salida_cambios = salida_dir / config["nombre_salida_cambios"]
    est = escribir_archivo(
        salida_path=salida_cambios,
        archivos=modificados,
        raiz=raiz,
        config=config,
        titulo="ARCHIVOS MODIFICADOS DESDE EL ÚLTIMO PULL",
        nota_extra=nota,
        modelo=modelo,
    )
    _log_ok("Cambios git       ", salida_cambios, len(modificados), est)

# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parsear_args(sys.argv[1:])
    unificar(args)

# ── Tests de extraer_importaciones ───────────────────────────────────────────

def _test_extraer_importaciones() -> None:
    """
    Tests unitarios para extraer_importaciones().
    Ejecutar con:
      python -c "from code_context import _test_extraer_importaciones; _test_extraer_importaciones()"
    """
    import tempfile, os, textwrap

    def _archivo_tmp(contenido: str, sufijo: str, directorio=None) -> Path:
        fd, ruta = tempfile.mkstemp(suffix=sufijo, dir=directorio)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(contenido))
        return Path(ruta)

    archivos_tmp: list[Path] = []

    try:
        # ── CASO 1: Import multilínea JS ─────────────────────────────────────
        c1 = _archivo_tmp("""
import {
  ComponenteA,
  ComponenteB,
} from '../components'
""", ".js")
        archivos_tmp.append(c1)
        r1 = extraer_importaciones(c1)
        assert "../components" in r1, (
            f"CASO 1 (multilínea JS): esperaba '../components', obtuve {r1}"
        )
        print("✓ CASO 1 — import multilínea JS")

        # ── CASO 2: Re-exports ────────────────────────────────────────────────
        c2 = _archivo_tmp("""
export { default } from './Modal'
export * from './utils'
export { foo } from "@/helpers"
""", ".ts")
        archivos_tmp.append(c2)
        r2 = extraer_importaciones(c2)
        assert "./Modal"   in r2, f"CASO 2a: esperaba './Modal', obtuve {r2}"
        assert "./utils"   in r2, f"CASO 2b: esperaba './utils', obtuve {r2}"
        assert "@/helpers" in r2, f"CASO 2c: esperaba '@/helpers', obtuve {r2}"
        print("✓ CASO 2 — re-exports (default / * / nombrado)")

        # ── CASO 3: Import dinámico con template literal ──────────────────────
        c3 = _archivo_tmp("""
const mod = await import(`./plugins/${nombre}`)
""", ".js")
        archivos_tmp.append(c3)
        r3 = extraer_importaciones(c3)
        assert "./plugins/" in r3, (
            f"CASO 3 (template literal dinámico): esperaba './plugins/', obtuve {r3}"
        )
        print("✓ CASO 3 — import() dinámico con template literal")

        # ── CASO 4: Import side-effect ────────────────────────────────────────
        c4 = _archivo_tmp("""
import './reset.css'
import './globals.css'
""", ".js")
        archivos_tmp.append(c4)
        r4 = extraer_importaciones(c4)
        assert "./reset.css"   in r4, f"CASO 4a: esperaba './reset.css', obtuve {r4}"
        assert "./globals.css" in r4, f"CASO 4b: esperaba './globals.css', obtuve {r4}"
        print("✓ CASO 4 — import side-effect")

        # ── CASO 5: require() con desestructuración ───────────────────────────
        c5 = _archivo_tmp("""
const { x } = require('../lib/x')
const path = require('path')
""", ".js")
        archivos_tmp.append(c5)
        r5 = extraer_importaciones(c5)
        assert "../lib/x" in r5, f"CASO 5a: esperaba '../lib/x', obtuve {r5}"
        assert "path"     in r5, f"CASO 5b: esperaba 'path', obtuve {r5}"
        print("✓ CASO 5 — require() con desestructuración")

        # ── CASO 6: Import con comentario inline /* ... */ ────────────────────
        c6 = _archivo_tmp("""
import foo from /* webpackChunkName: "foo" */ '../foo'
""", ".ts")
        archivos_tmp.append(c6)
        r6 = extraer_importaciones(c6)
        assert "../foo" in r6, (
            f"CASO 6 (comentario inline): esperaba '../foo', obtuve {r6}"
        )
        print("✓ CASO 6 — import con comentario inline /* ... */")

        # ── CASO 7: Imports relativos Python con subpaquetes ──────────────────
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "pkg").mkdir()
            (td / "pkg" / "__init__.py").write_text("")
            (td / "pkg" / "models.py").write_text("")
            (td / "pkg" / "utils").mkdir()
            (td / "pkg" / "utils" / "__init__.py").write_text("")
            (td / "pkg" / "utils" / "helpers.py").write_text("")
            (td / "pkg" / "sub").mkdir()
            (td / "pkg" / "sub" / "__init__.py").write_text("")

            vista_py = td / "pkg" / "sub" / "vista.py"
            vista_py.write_text(textwrap.dedent("""
from ..utils.helpers import parse_date
from . import models
"""))
            r7 = extraer_importaciones(vista_py)

            helpers_match = any("utils" in s and "helpers" in s for s in r7)
            assert helpers_match, (
                f"CASO 7a (from ..utils.helpers): ningún especificador contiene "
                f"'utils/helpers', obtuve {r7}"
            )
            models_match = any("models" in s for s in r7)
            assert models_match, (
                f"CASO 7b (from . import models): ningún especificador contiene "
                f"'models', obtuve {r7}"
            )
        print("✓ CASO 7 — imports relativos Python con resolución a ruta real")

        # ── EXTRA: deduplicación ──────────────────────────────────────────────
        c_dup = _archivo_tmp("""
import A from './a'
import B from './a'
import C from './b'
""", ".js")
        archivos_tmp.append(c_dup)
        r_dup = extraer_importaciones(c_dup)
        assert r_dup.count("./a") == 1, (
            f"DEDUP: './a' debería aparecer 1 vez, obtuve {r_dup}"
        )
        print("✓ EXTRA  — deduplicación de especificadores")

        print("\n[OK] Todos los tests pasaron.")

    finally:
        for p in archivos_tmp:
            try:
                p.unlink()
            except Exception:
                pass