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
  --modelo NOMBRE           Modelo/agente destino para estimar tokens y costo.
                            Opciones: claude, gpt-4, gpt-4o, gpt-3.5, gemini,
                                      gemini-pro, llama, mistral, deepseek, default
                            Default: "default" (estimación genérica, sin costo)
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
        # Forzar UTF-8 explícito para evitar problemas de encoding en Windows
        encoding="utf-8", errors="replace"
    )
    if r.returncode != 0:
        return []
    lineas = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    # Intentar corregir doble-encoding (Windows con chcp != 65001)
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

# ── Análisis de importaciones ─────────────────────────────────────────────────

def extraer_importaciones(archivo: Path) -> list[str]:
    importaciones = []
    try:
        texto = archivo.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return importaciones
    if archivo.suffix == ".py":
        try:
            tree = ast.parse(texto)
            for nodo in ast.walk(tree):
                if isinstance(nodo, ast.Import):
                    for alias in nodo.names:
                        importaciones.append(alias.name.split(".")[0])
                elif isinstance(nodo, ast.ImportFrom):
                    if nodo.module:
                        importaciones.append(nodo.module.split(".")[0])
        except SyntaxError:
            pass
    elif archivo.suffix in {".js", ".ts", ".jsx", ".tsx"}:
        patron = re.compile(
            r"""(?:import|require)\s*(?:.*?from\s*)?['"](\.{1,2}/[^'"]+|[^'"./][^'"]*)['"']""",
            re.MULTILINE,
        )
        for m in patron.finditer(texto):
            importaciones.append(m.group(1))
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


def recolectar_archivos(raiz: Path, config: dict,
                         omitir_autogenerados: bool = False,
                         limite_lineas: int | None = None,
                         verbose: bool = False) -> list[Path]:
    archivos = []
    for archivo in raiz.rglob("*"):
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
        archivos.append(archivo)
    return ordenar_archivos(archivos)


def filtrar_por_config(archivos: list[Path], raiz: Path, config: dict,
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
        resultado.append(archivo)
    return ordenar_archivos(resultado)


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


def _escribir_y_estimar(salida_path: Path, writer_fn, modelo: str) -> dict | None:
    with open(salida_path, "w", encoding="utf-8") as f:
        writer_fn(f)
    try:
        texto = salida_path.read_text(encoding="utf-8", errors="replace")
        est   = estimar_tokens(texto, modelo)
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
            try:
                contenido = archivo.read_text(encoding="utf-8", errors="replace")
                f.write(contenido)
                if not contenido.endswith("\n"):
                    f.write("\n")
            except Exception as e:
                f.write(f"# [No se pudo leer: {e}]\n")

    return _escribir_y_estimar(salida_path, writer, modelo)


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
        stems      = {a.stem: str(a.relative_to(raiz)) for a in archivos}
        tiene_deps = False
        for archivo in archivos:
            importaciones = extraer_importaciones(archivo)
            deps_internas = []
            for imp in importaciones:
                if imp.startswith("."):
                    base  = (archivo.parent / imp).resolve()
                    clave = base.stem
                else:
                    clave = imp.split("/")[-1].split(".")[0]
                if clave in stems:
                    deps_internas.append(stems[clave])
            if deps_internas:
                tiene_deps = True
                relativo   = archivo.relative_to(raiz)
                f.write(f"  {relativo}\n")
                for d in deps_internas:
                    f.write(f"    └─ {d}\n")
                f.write("\n")
        if not tiene_deps:
            f.write("  (No se detectaron dependencias internas entre los archivos incluidos)\n\n")
        f.write(f"# {sep}\n# INSTRUCCIONES PARA EL USUARIO\n# {sep}\n\n")
        f.write("# Este archivo NO contiene código fuente.\n")
        f.write("# Úsalo para decidir qué archivos pasarle a la IA.\n")
        f.write("# Luego ejecuta el script indicando solo esas carpetas en 'incluir_solo'\n")
        f.write("# o usa --solo-cambios si trabajas con git.\n\n")

    return _escribir_y_estimar(salida_path, writer, modelo)


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

def escribir_mapa_ia(salida_path: Path, archivos: list[Path], raiz: Path,
                      config: dict, commits: list[str] | None = None,
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
        stems      = {a.stem: str(a.relative_to(raiz)) for a in archivos}
        dep_lines  = []
        for archivo in archivos:
            importaciones = extraer_importaciones(archivo)
            deps_internas = []
            for imp in importaciones:
                if imp.startswith("."):
                    base  = (archivo.parent / imp).resolve()
                    clave = base.stem
                else:
                    clave = imp.split("/")[-1].split(".")[0]
                if clave in stems:
                    deps_internas.append(stems[clave])
            if deps_internas:
                rel = archivo.relative_to(raiz).as_posix()
                dep_lines.append((rel, deps_internas))

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

    return _escribir_y_estimar(salida_path, writer, modelo)


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
                         modelo: str = "default") -> dict | None:
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

        # ── Árbol de archivos ────────────────────────────────────────────────
        f.write("<file_tree>\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n</file_tree>\n\n")

        # ── Contenido de archivos ────────────────────────────────────────────
        f.write("<codebase>\n")
        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            f.write(f"\n<file path=\"{relativo.as_posix()}\">\n")
            try:
                contenido = archivo.read_text(encoding="utf-8", errors="replace")
                f.write(contenido)
                if not contenido.endswith("\n"):
                    f.write("\n")
            except Exception as e:
                f.write(f"[READ_ERROR: {e}]\n")
            f.write(f"</file>\n")
        f.write("\n</codebase>\n\n")

        # ── Instrucción de respuesta ─────────────────────────────────────────
        if not es_solicitado:
            f.write("<response_instructions>\n")
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
            f.write("</response_instructions>\n")
        else:
            f.write("<response_instructions>\n")
            f.write("  You are receiving the specific files you requested.\n")
            f.write("  Your task is defined in <task>.\n")
            f.write("  You now have sufficient context. Proceed with your full response.\n")
            f.write("  Do not ask for additional files.\n")
            f.write("</response_instructions>\n")

    return _escribir_y_estimar(salida_path, writer, modelo)


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