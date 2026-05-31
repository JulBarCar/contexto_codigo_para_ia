"""
modules/filesystem/ordering.py
Ordenación de archivos por prioridad y profundidad.
"""

from pathlib import Path

from modules.config.defaults import ARCHIVOS_PRIORITARIOS


def _prioridad(archivo: Path) -> tuple:
    partes         = archivo.parts
    profundidad    = len(partes)
    stem_lower     = archivo.stem.lower().lstrip("_")
    es_prioritario = 0 if stem_lower in ARCHIVOS_PRIORITARIOS else 1
    return (profundidad, es_prioritario, archivo.name.lower())


def ordenar_archivos(archivos: list[Path]) -> list[Path]:
    return sorted(archivos, key=_prioridad)