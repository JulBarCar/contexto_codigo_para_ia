"""
modules/output/console.py
Manejo de streams de consola pensado para que la CLI sea consumida por agentes.

Garantías:
- UTF-8 forzado en stdout y stderr (evita crashes con acentos en Windows).
- Modo JSON (--json): los logs humanos van a stderr y el stdout original
  recibe exactamente UNA línea JSON al final (resultado o error).
- Modo --stdout: los logs humanos se descartan y el stdout original
  recibe únicamente el contenido generado.
- Errores: en modo JSON se emiten como {"ok": false, "error": ..., "kind": ...};
  si no, se imprimen como [ERROR] ... y salen con el código indicado.

Códigos de salida:
  0 → éxito
  1 → error general
  2 → error de uso (argumento inválido)
  3 → el contenido supera --max-stdout (usar modo archivo)
"""

import json
import os
import sys

# stdout original, capturado antes de cualquier redirección
SALIDA_REAL = sys.stdout
MODO_JSON = False
_SALIDA_SILENCIADA = False
_DEVNULL = None


def _forzar_utf8(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


_forzar_utf8(sys.stdout)
_forzar_utf8(sys.stderr)


def activar_json() -> None:
    """Los logs humanos van a stderr; el JSON final va al stdout original."""
    global MODO_JSON
    if not MODO_JSON:
        MODO_JSON = True
        sys.stdout = sys.stderr


def silenciar_logs() -> None:
    """Descarta los logs humanos para que --stdout devuelva contenido puro."""
    global _SALIDA_SILENCIADA, _DEVNULL
    if not MODO_JSON and not _SALIDA_SILENCIADA:
        _SALIDA_SILENCIADA = True
        _DEVNULL = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = _DEVNULL


def emitir_json(payload: dict, codigo: int = 0) -> None:
    """Escribe una única línea JSON en el stdout original y termina."""
    SALIDA_REAL.write(json.dumps(payload, ensure_ascii=False) + "\n")
    SALIDA_REAL.flush()
    sys.exit(codigo)


def emitir_contenido(texto: str) -> None:
    """Escribe contenido crudo (--stdout) en el stdout original."""
    SALIDA_REAL.write(texto)
    if not texto.endswith("\n"):
        SALIDA_REAL.write("\n")
    SALIDA_REAL.flush()


def _imprimir_error(linea: str) -> None:
    if _SALIDA_SILENCIADA:
        print(linea, file=sys.stderr)
    else:
        print(linea)


def fallar(mensaje: str, codigo: int = 1, **extra) -> None:
    """Termina la ejecución con un error legible por humanos y por agentes."""
    if MODO_JSON:
        payload = {
            "ok": False,
            "error": mensaje,
            "kind": {1: "error", 2: "usage", 3: "limit"}.get(codigo, "error"),
        }
        payload.update(extra)
        SALIDA_REAL.write(json.dumps(payload, ensure_ascii=False) + "\n")
        SALIDA_REAL.flush()
    else:
        _imprimir_error(f"[ERROR]  {mensaje}")
    sys.exit(codigo)
