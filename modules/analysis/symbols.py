"""
modules/analysis/symbols.py
Extracción de símbolos (funciones, clases, exports) por archivo.

Alimenta el atributo `symbols` del <file_index> de los archivos ia_*:
permite a un agente elegir qué archivos leer sin abrirlos, ahorrando
rondas de exploración.

Estrategia:
  .py         → AST (preciso: ignora comentarios y strings)
  .css / .html→ sin símbolos (no aportan a la selección)
  resto       → regex ancladas al inicio de línea (best-effort)

Salida: "fn1, Clase.met2, export3 (+3)" — lista plana, saneada para
usarse como valor de atributo XML.
"""

import ast
import re
from pathlib import Path

MAX_SIMBOLOS = 12
MAX_POR_CLASE = 3

# Palabras clave que pueden encabezar una declaración
_KW = (r"(?:function|func|fn|def|fun|class|struct|enum|trait|impl|"
       r"interface|record|type)")
# Modificadores admisibles antes de la palabra clave (máx. 2 por línea)
_MOD = (r"(?:export|default|public|private|protected|static|final|abstract|"
        r"open|sealed|data|internal|pub|async|override|virtual|module|"
        r"declarative)")

_NO_ES_METODO = {
    "if", "for", "while", "switch", "catch", "do", "else", "try", "with",
    "function", "return", "new", "super", "typeof", "await", "yield",
    "match", "loop", "when", "elif", "unless", "until", "foreach", "defer",
    "go", "select", "case", "lock", "synchronized", "get", "set",
    "static", "async", "computed",
}

_PATRONES: list[re.Pattern] = [
    # declaración con palabra clave: function/func/fn/def/class/struct/type...
    re.compile(rf"^\s*(?:{_MOD}\s+)?(?:{_MOD}\s+)?{_KW}\s+([A-Za-z_$][\w$]*)", re.M),
    # JS/TS: const/let/var = function | arrow
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
               r"\s*=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*=>"
               r"|[A-Za-z_$][\w$]*\s*=>)", re.M),
    # Ruby: def sin paréntesis
    re.compile(r"^\s*def\s+([A-Za-z_][\w.?!]+)", re.M),
    # R: nombre <- function
    re.compile(r"^\s*([A-Za-z_][\w.]*)\s*<-\s*function\b", re.M),
    # shell: nombre() {
    re.compile(r"^\s*([A-Za-z_][\w-]*)\s*\(\)\s*\{", re.M),
    # métodos (indentados, seguidos de paréntesis y llave)
    re.compile(r"^\s{2,}(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?"
               r"([A-Za-z_$][\w$]*)\s*\([^;]*\)\s*\{", re.M),
]

_SIN_SIMBOLOS = {".css", ".html", ".htm", ".scss", ".less", ".md", ".json",
                 ".txt", ".yml", ".yaml", ".xml", ".svg", ".lock"}


def _simbolos_python(texto: str) -> list[str]:
    try:
        arbol = ast.parse(texto)
    except SyntaxError:
        return []
    nombres: list[str] = []
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nombres.append(nodo.name)
        elif isinstance(nodo, ast.ClassDef):
            nombres.append(nodo.name)
            metodos = [n.name for n in nodo.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            nombres.extend(f"{nodo.name}.{m}" for m in metodos[:MAX_POR_CLASE])
        elif isinstance(nodo, ast.Assign):
            for objetivo in nodo.targets:
                if isinstance(objetivo, ast.Name) and isinstance(nodo.value, ast.Lambda):
                    nombres.append(objetivo.id)
    return nombres


def _simbolos_regex(texto: str) -> list[str]:
    encontrados: list[tuple[int, str]] = []
    for patron in _PATRONES:
        es_metodo = patron.pattern.startswith(r"^\s{2,}")
        for m in patron.finditer(texto):
            nombre = m.group(1)
            if not nombre:
                continue
            if es_metodo and nombre.lower() in _NO_ES_METODO:
                continue
            encontrados.append((m.start(1), nombre))
    encontrados.sort(key=lambda t: t[0])
    return [nombre for _, nombre in encontrados]


def extraer_simbolos_de_texto(texto: str, ext: str,
                              max_simbolos: int = MAX_SIMBOLOS) -> str:
    """Devuelve la cadena de símbolos para el atributo `symbols` (o '' si no hay)."""
    if not texto or ext.lower() in _SIN_SIMBOLOS:
        return ""
    if ext.lower() == ".py":
        nombres = _simbolos_python(texto) or _simbolos_regex(texto)
    else:
        nombres = _simbolos_regex(texto)
    if not nombres:
        return ""
    únicos = list(dict.fromkeys(nombres))
    mostrar = únicos[:max_simbolos]
    salida = ", ".join(mostrar).replace('"', "'")
    resto = len(únicos) - len(mostrar)
    if resto > 0:
        salida += f" (+{resto})"
    return salida


def extraer_simbolos(archivo: Path, max_simbolos: int = MAX_SIMBOLOS) -> str:
    """Lee el archivo y devuelve sus símbolos (usar la versión de texto si ya se leyó)."""
    try:
        texto = archivo.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return extraer_simbolos_de_texto(texto, archivo.suffix, max_simbolos)
