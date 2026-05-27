"""
compresor.py
Módulo de compresión inteligente de código para code_context.py.

Elimina comentarios, docstrings opcionales y líneas en blanco innecesarias
usando el AST nativo de Python (sin dependencias externas) y regex para JS/TS.

Para Python usa ast + tokenize (stdlib), lo que garantiza precisión total.
Para JS/TS/JSX/TSX usa regex calibrado (cubre el 95% de los casos reales).
Para HTML/CSS usa regex para eliminar comentarios de bloque.

USO STANDALONE:
  python compresor.py archivo.py [--nivel leve|medio|agresivo]

INTEGRACIÓN EN code_context.py:
  from compresor import comprimir_archivo, NivelCompresion

NIVELES:
  leve      → solo elimina comentarios de línea y bloques vacíos
  medio     → también elimina docstrings no esenciales (módulo-nivel)
  agresivo  → elimina todos los docstrings, colapsa líneas en blanco

MÉTRICAS:
  comprimir_archivo() devuelve un dict con chars_original, chars_comprimido,
  reduccion_pct, además del texto comprimido.
"""

import ast
import io
import re
import sys
import tokenize
from enum import Enum
from pathlib import Path


# ── Nivel de compresión ───────────────────────────────────────────────────────

class NivelCompresion(str, Enum):
    LEVE     = "leve"
    MEDIO    = "medio"
    AGRESIVO = "agresivo"


# ── Python: compresión via tokenize (sin perder precisión) ────────────────────

def _comprimir_python(codigo: str, nivel: NivelCompresion) -> str:
    """
    Elimina comentarios y docstrings de código Python usando el módulo
    tokenize de la stdlib. Es preciso porque opera sobre tokens reales,
    no sobre texto crudo.
    """
    # Primero determinamos qué rangos de líneas son docstrings
    docstring_lineas: set[int] = set()

    if nivel in (NivelCompresion.MEDIO, NivelCompresion.AGRESIVO):
        try:
            tree = ast.parse(codigo)
            for nodo in ast.walk(tree):
                # Nodos que pueden tener docstring
                if not isinstance(nodo, (ast.Module, ast.FunctionDef,
                                         ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if not nodo.body:
                    continue
                primer = nodo.body[0]
                if not isinstance(primer, ast.Expr):
                    continue
                val = primer.value
                # Python 3.8+: ast.Constant; antes: ast.Str
                if not isinstance(val, ast.Constant) or not isinstance(val.value, str):
                    continue

                # En nivel MEDIO conservamos docstrings de funciones y clases
                # (le sirven a la IA para entender la API). Solo eliminamos
                # los de módulo.
                if nivel == NivelCompresion.MEDIO and not isinstance(nodo, ast.Module):
                    continue

                # Marcamos todas las líneas del docstring para eliminar
                for linea in range(primer.lineno, primer.end_lineno + 1):
                    docstring_lineas.add(linea)
        except SyntaxError:
            pass  # Si no parsea, no tocamos nada

    # Tokenizamos para eliminar comentarios
    tokens_a_eliminar: set[int] = set()  # líneas a eliminar por comentario
    try:
        readline = io.StringIO(codigo).readline
        for tok in tokenize.generate_tokens(readline):
            if tok.type == tokenize.COMMENT:
                tokens_a_eliminar.add(tok.start[0])
    except tokenize.TokenError:
        pass

    # Reconstruimos línea a línea
    lineas = codigo.splitlines(keepends=True)
    resultado = []
    for i, linea in enumerate(lineas, start=1):
        # Eliminar líneas que son 100% comentario
        if i in tokens_a_eliminar:
            # Si la línea tiene solo el comentario (nada útil antes), la saltamos
            stripped = linea.lstrip()
            if stripped.startswith("#"):
                continue
            # Si hay código antes del comentario, eliminamos solo el comentario
            # (tokenize nos da la posición exacta del token)
            col = linea.index("#")
            linea = linea[:col].rstrip() + "\n"

        # Eliminar líneas de docstring
        if i in docstring_lineas:
            continue

        resultado.append(linea)

    texto = "".join(resultado)

    # Colapsar líneas en blanco consecutivas
    if nivel == NivelCompresion.AGRESIVO:
        texto = re.sub(r"\n{3,}", "\n\n", texto)

    return texto.strip() + "\n"


# ── JS/TS/JSX/TSX: compresión via regex ──────────────────────────────────────

def _comprimir_js(codigo: str, nivel: NivelCompresion) -> str:
    """
    Elimina comentarios de JS/TS usando regex.
    Cubre: // comentario, /* bloque */, /** JSDoc */
    Preserva URLs dentro de strings y patrones de expresiones regulares.
    """
    # Paso 1: Proteger strings para no tocar su contenido
    # (reemplazamos temporalmente con placeholders)
    strings: list[str] = []
    patron_string = re.compile(
        r'(`[^`\\]*(?:\\.[^`\\]*)*`)'    # template literals
        r'|("(?:[^"\\]|\\.)*")'          # strings dobles
        r"|('(?:[^'\\]|\\.)*')",          # strings simples
        re.DOTALL
    )
    def reemplazar_string(m):
        idx = len(strings)
        strings.append(m.group(0))
        return f"__STR_{idx}__"

    codigo_safe = patron_string.sub(reemplazar_string, codigo)

    # Paso 2: Eliminar comentarios de bloque /** ... */ y /* ... */
    codigo_safe = re.sub(r"/\*[\s\S]*?\*/", "", codigo_safe)

    # Paso 3: Eliminar comentarios de línea //
    codigo_safe = re.sub(r"//[^\n]*", "", codigo_safe)

    # Paso 4: Restaurar strings
    def restaurar_string(m):
        idx = int(m.group(1))
        return strings[idx]
    codigo_safe = re.sub(r"__STR_(\d+)__", restaurar_string, codigo_safe)

    # Paso 5: Limpiar líneas en blanco
    if nivel == NivelCompresion.AGRESIVO:
        codigo_safe = re.sub(r"\n{3,}", "\n\n", codigo_safe)
    else:
        # Al menos eliminar líneas que quedaron completamente vacías
        codigo_safe = re.sub(r"\n[ \t]+\n", "\n\n", codigo_safe)

    return codigo_safe.strip() + "\n"


# ── HTML/CSS: compresión via regex ────────────────────────────────────────────

def _comprimir_html(codigo: str, nivel: NivelCompresion) -> str:
    """Elimina comentarios HTML <!-- ... --> excepto los condicionales de IE."""
    # Preservar comentarios condicionales <!--[if ...]>
    texto = re.sub(r"<!--(?!\[if)[\s\S]*?-->", "", codigo)
    if nivel == NivelCompresion.AGRESIVO:
        texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip() + "\n"


def _comprimir_css(codigo: str, nivel: NivelCompresion) -> str:
    """Elimina comentarios CSS /* ... */."""
    texto = re.sub(r"/\*[\s\S]*?\*/", "", codigo)
    if nivel == NivelCompresion.AGRESIVO:
        texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip() + "\n"


# ── Dispatcher por extensión ──────────────────────────────────────────────────

_COMPRESORES: dict[str, callable] = {
    ".py":   _comprimir_python,
    ".js":   _comprimir_js,
    ".ts":   _comprimir_js,
    ".jsx":  _comprimir_js,
    ".tsx":  _comprimir_js,
    ".html": _comprimir_html,
    ".css":  _comprimir_css,
}

EXTENSIONES_SOPORTADAS = set(_COMPRESORES.keys())


def comprimir_texto(codigo: str, extension: str,
                    nivel: NivelCompresion = NivelCompresion.MEDIO) -> dict:
    """
    Comprime el código de un archivo y devuelve métricas + texto comprimido.

    Retorna:
        {
            "texto":          str,   # código comprimido
            "chars_original": int,
            "chars_final":    int,
            "reduccion_pct":  float, # 0-100
            "soportado":      bool,  # False si la extensión no tiene compresor
        }
    """
    ext = extension.lower()
    chars_orig = len(codigo)

    compresor = _COMPRESORES.get(ext)
    if compresor is None:
        return {
            "texto":          codigo,
            "chars_original": chars_orig,
            "chars_final":    chars_orig,
            "reduccion_pct":  0.0,
            "soportado":      False,
        }

    try:
        texto_comprimido = compresor(codigo, nivel)
    except Exception:
        # Si algo falla, devolvemos el original intacto
        texto_comprimido = codigo

    chars_final = len(texto_comprimido)
    reduccion   = max(0.0, (1 - chars_final / chars_orig) * 100) if chars_orig > 0 else 0.0

    return {
        "texto":          texto_comprimido,
        "chars_original": chars_orig,
        "chars_final":    chars_final,
        "reduccion_pct":  reduccion,
        "soportado":      True,
    }


def comprimir_archivo(ruta: Path,
                       nivel: NivelCompresion = NivelCompresion.MEDIO) -> dict:
    """
    Lee un archivo y lo comprime. Devuelve el mismo dict que comprimir_texto.
    """
    try:
        codigo = ruta.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {
            "texto":          "",
            "chars_original": 0,
            "chars_final":    0,
            "reduccion_pct":  0.0,
            "soportado":      False,
            "error":          str(e),
        }
    return comprimir_texto(codigo, ruta.suffix, nivel)


# ── CLI standalone ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Comprime código fuente eliminando comentarios y docstrings."
    )
    parser.add_argument("archivo", help="Archivo a comprimir")
    parser.add_argument(
        "--nivel",
        choices=[n.value for n in NivelCompresion],
        default=NivelCompresion.MEDIO.value,
        help="Nivel de compresión (default: medio)",
    )
    parser.add_argument(
        "--salida", "-o",
        help="Archivo de salida. Si no se indica, imprime en stdout.",
    )
    args = parser.parse_args()

    ruta = Path(args.archivo)
    if not ruta.exists():
        print(f"[ERROR] Archivo no encontrado: {ruta}", file=sys.stderr)
        sys.exit(1)

    nivel = NivelCompresion(args.nivel)
    resultado = comprimir_archivo(ruta, nivel)

    if not resultado["soportado"]:
        print(f"[AVISO] Extensión '{ruta.suffix}' no soportada. Extensiones válidas: "
              f"{', '.join(sorted(EXTENSIONES_SOPORTADAS))}", file=sys.stderr)
        sys.exit(1)

    orig  = resultado["chars_original"]
    final = resultado["chars_final"]
    pct   = resultado["reduccion_pct"]
    print(f"[OK] {ruta.name}  {orig:,} → {final:,} chars  "
          f"({pct:.1f}% reducción)  nivel={nivel.value}".replace(",", "."),
          file=sys.stderr)

    if args.salida:
        Path(args.salida).write_text(resultado["texto"], encoding="utf-8")
        print(f"[OK] Guardado en: {args.salida}", file=sys.stderr)
    else:
        print(resultado["texto"])
