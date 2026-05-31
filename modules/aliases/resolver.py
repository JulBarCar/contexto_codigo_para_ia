"""
modules/aliases/resolver.py
Resolución de strings de importación a rutas de archivo reales.
"""

from pathlib import Path

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
        ruta_candidata = (archivo.parent / imp).resolve()
    else:
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
        return None

    if ruta_candidata in indice_archivos:
        return indice_archivos[ruta_candidata]

    for ext in _EXTENSIONES_RESOLVE:
        candidato = Path(str(ruta_candidata) + ext)
        if candidato in indice_archivos:
            return indice_archivos[candidato]

    for ext in _EXTENSIONES_RESOLVE:
        candidato = ruta_candidata / f"index{ext}"
        if candidato in indice_archivos:
            return indice_archivos[candidato]

    return None