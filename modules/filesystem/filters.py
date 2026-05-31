"""
modules/filesystem/filters.py
Filtrado y recolección de archivos del proyecto.
"""

from pathlib import Path

from modules.config.defaults import ARCHIVOS_AUTOGENERADOS, PATRONES_AUTOGENERADOS
from modules.filesystem.ordering import ordenar_archivos


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