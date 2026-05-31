"""
modules/output/log.py
Funciones de logging de resultados en consola.
"""

from pathlib import Path


def _log_ok(label: str, path: Path, n_archivos: int, est: dict | None) -> None:
    if est:
        tokens_fmt = f"{est['tokens']:,}".replace(",", ".")
        partes     = [f"~{tokens_fmt} tokens"]
        if est["costo_usd"] is not None:
            partes.append(f"~${est['costo_usd']:.4f} USD")
        if est["porcentaje_window"] is not None:
            pct    = est["porcentaje_window"]
            estado = "✓" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE")
            partes.append(f"{pct:.0f}% del context window {estado}")
        token_info = "  [" + "  |  ".join(partes) + "]"
    else:
        token_info = ""
    n = n_archivos
    print(f"[OK]     {label}  →  {path.name}  ({n} archivo{'s' if n != 1 else ''}){token_info}")
    if est and est.get("porcentaje_window") is not None and est["porcentaje_window"] > 100:
        pct = est["porcentaje_window"]
        print(f"[AVISO]  El contexto excede el context window del modelo ({pct:.0f}%).")
        print(f"         Considerá usar --limite, --sin-minimos o 'incluir_solo' en el config.")