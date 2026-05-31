"""
modules/output/tree_builder.py
Construcción del árbol visual de archivos del proyecto.
"""

from pathlib import Path


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