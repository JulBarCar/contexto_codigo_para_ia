"""
modules/output/preview.py
Modos --preview y --stats: muestran información sin generar archivos.
"""

from pathlib import Path

from modules.ai import estimar_tokens


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