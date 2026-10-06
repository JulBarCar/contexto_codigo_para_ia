"""
modules/output/tree_builder.py
Construcción del árbol visual de archivos del proyecto.
"""

from pathlib import Path


def construir_arbol(archivos: list[Path], raiz: Path) -> str:
    lineas = [f"{raiz.resolve().name}/"]
    arbol: dict[str, dict] = {}

    for archivo in archivos:
        relativo = archivo.relative_to(raiz)
        nodo = arbol
        for parte in relativo.parts:
            nodo = nodo.setdefault(parte, {})

    def escribir(nodo: dict[str, dict], nivel: int) -> None:
        dirs = sorted(k for k, v in nodo.items() if v)
        files = sorted(k for k, v in nodo.items() if not v)
        for nombre in dirs:
            lineas.append(f"{'  ' * nivel}{nombre}/")
            escribir(nodo[nombre], nivel + 1)
        for nombre in files:
            lineas.append(f"{'  ' * nivel}{nombre}")

    escribir(arbol, 1)
    return "\n".join(lineas)
