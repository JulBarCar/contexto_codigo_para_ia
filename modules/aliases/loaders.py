"""
modules/aliases/loaders.py
Lectura de aliases de módulos desde archivos de configuración del proyecto.

Soporta:
  JavaScript / TypeScript
  ├── tsconfig.json / tsconfig.base.json   compilerOptions.paths + baseUrl
  ├── jsconfig.json                         ídem (proyectos JS sin TS)
  ├── vite.config.js / .ts                  resolve.alias
  ├── webpack.config.js / .ts               resolve.alias
  ├── babel.config.js / .json               plugin module-resolver → alias
  ├── .babelrc / .babelrc.js                ídem
  ├── nuxt.config.js / .ts                  alias: { ... }
  └── jest.config.js / .ts                  moduleNameMapper
"""

import json
import re
from pathlib import Path


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
        r"""['"](@[\w/.-]*|~[\w/.-]*|[\w][\w/.-]*)['"]?\s*:\s*"""
        r"""(?:"""
        r"""(?:path\.resolve|path\.join)\s*\([^,)]*,\s*['"]([^'"]+)['"]"""
        r"""|fileURLToPath\s*\(new\s+URL\s*\(\s*['"]([^'"]+)['"]"""
        r"""|['"]([^'"]+)['"]) """,
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
        r"""|['"]([^'"]+)['"]) """,
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
        r"""['"]?([@~][\w/.-]*|[\w][\w/.-]*)['"]?\s*:\s*['"]([^'"]+)['"]"""
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
        r"""['"]\^?([@~][\w/.-]*?)(?:/\(|\\/)[^'"]*['"]\s*:\s*['"]<rootDir>/([^'"$]*)"""
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
        r"""['"]?([@~][\w/.-]*)['"]?\s*:\s*['"]([^'"]+)['"]"""
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