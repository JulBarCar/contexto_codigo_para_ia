"""
modules/output/preview.py
Modos --preview y --stats: muestran información sin generar archivos.
Devuelven un dict con los datos estructurados para que --json pueda emitirlo.
"""

from pathlib import Path

from modules.ai import estimar_tokens


def _estimar_corpus(archivos: list[Path], modelo: str) -> dict | None:
    try:
        texto_total = "".join(
            a.read_text(encoding="utf-8", errors="replace") for a in archivos
        )
        return estimar_tokens(texto_total, modelo)
    except Exception:
        return None


def mostrar_preview(archivos: list[Path], raiz: Path, config: dict,
                     modelo: str) -> dict:
    """Muestra qué archivos se incluirían sin generar nada."""
    print(f"\n[PREVIEW] {len(archivos)} archivo(s) que se incluirían:\n")

    ext_count: dict[str, int] = {}
    total_lineas = 0
    detalle: list[dict] = []

    for archivo in archivos:
        relativo = archivo.relative_to(raiz).as_posix()
        try:
            n_lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
        except Exception:
            n_lineas = 0
        total_lineas += n_lineas
        ext = archivo.suffix
        ext_count[ext] = ext_count.get(ext, 0) + 1
        detalle.append({"path": relativo, "lines": n_lineas})
        print(f"  {relativo:<60}  {n_lineas:>5} líneas")

    print(f"\n[PREVIEW] Resumen:")
    print(f"  Archivos    : {len(archivos)}")
    print(f"  Líneas total: {total_lineas:,}".replace(",", "."))
    for ext, n in sorted(ext_count.items()):
        print(f"  {ext:<8}: {n} archivo(s)")

    info: dict = {
        "files": len(archivos),
        "lineas": total_lineas,
        "por_extension": ext_count,
        "files_detail": detalle,
    }

    est = _estimar_corpus(archivos, modelo)
    if est:
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
        info.update(_datos_estimacion(est))
    print()

    return info


def mostrar_stats(archivos: list[Path], raiz: Path, modelo: str) -> dict:
    """Estimación de tokens en consola, sin generar archivos."""
    print(f"\n[STATS] Analizando {len(archivos)} archivo(s)...\n")
    info: dict = {"files": len(archivos)}
    est = _estimar_corpus(archivos, modelo)
    if not est:
        print("[ERROR] No se pudo calcular la estimación.\n")
        return info
    try:
        model_info = est["info_modelo"]
        tokens_fmt = f"{est['tokens']:,}".replace(",", ".")
        chars_fmt  = f"{est['chars']:,}".replace(",", ".")
        print(f"  Modelo           : {model_info['nombre_display']}")
        print(f"  Caracteres       : {chars_fmt}")
        print(f"  Tokens estimados : ~{tokens_fmt}")
        if est["costo_usd"] is not None:
            print(f"  Costo estimado   : ~${est['costo_usd']:.4f} USD  (solo tokens de entrada)")
        else:
            print(f"  Costo estimado   : no disponible (varía según proveedor)")
        if est["porcentaje_window"] is not None:
            pct    = est["porcentaje_window"]
            estado = "✓ entra" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE")
            cw_fmt = f"{model_info['context_window']:,}".replace(",", ".")
            print(f"  Context window   : {pct:.1f}% de {cw_fmt} tokens  [{estado}]")
        print()
    except Exception as e:
        print(f"[ERROR] No se pudo calcular la estimación: {e}\n")

    info.update(_datos_estimacion(est))
    return info


def _datos_estimacion(est: dict) -> dict:
    """Normaliza una estimación a campos planos para el JSON de salida."""
    pct = est.get("porcentaje_window")
    return {
        "tokens": est["tokens"],
        "bytes": est["chars"],
        "model": est.get("modelo_key"),
        "window_pct": round(pct, 1) if pct is not None else None,
        "cost_usd": round(est["costo_usd"], 4) if est.get("costo_usd") is not None else None,
    }
