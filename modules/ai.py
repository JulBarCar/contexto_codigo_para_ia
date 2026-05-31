"""
modules/ai.py
Estimación de tokens, costos y slugs para nombres de archivo.
Sin dependencias internas: puede importarse desde cualquier módulo.
"""

import re

# ── Tabla de modelos ──────────────────────────────────────────────────────────

MODELOS_TOKENS: dict[str, dict] = {
    "claude": {
        "nombre_display":  "Claude Sonnet (Anthropic)",
        "chars_por_token": 3.8,
        "precio_input":    3.00,
        "context_window":  200_000,
    },
    "gpt-4": {
        "nombre_display":  "GPT-4 Turbo (OpenAI)",
        "chars_por_token": 4.0,
        "precio_input":    30.00,
        "context_window":  128_000,
    },
    "gpt-4o": {
        "nombre_display":  "GPT-4o (OpenAI)",
        "chars_por_token": 4.0,
        "precio_input":    5.00,
        "context_window":  128_000,
    },
    "gpt-3.5": {
        "nombre_display":  "GPT-3.5 Turbo (OpenAI)",
        "chars_por_token": 4.0,
        "precio_input":    0.50,
        "context_window":  16_385,
    },
    "gemini": {
        "nombre_display":  "Gemini 1.5 Flash (Google)",
        "chars_por_token": 4.2,
        "precio_input":    0.075,
        "context_window":  1_000_000,
    },
    "gemini-pro": {
        "nombre_display":  "Gemini 1.5 Pro (Google)",
        "chars_por_token": 4.2,
        "precio_input":    1.25,
        "context_window":  2_000_000,
    },
    "llama": {
        "nombre_display":  "LLaMA (Meta)",
        "chars_por_token": 3.9,
        "precio_input":    None,
        "context_window":  128_000,
    },
    "mistral": {
        "nombre_display":  "Mistral Large",
        "chars_por_token": 3.9,
        "precio_input":    4.00,
        "context_window":  128_000,
    },
    "deepseek": {
        "nombre_display":  "DeepSeek V3",
        "chars_por_token": 3.8,
        "precio_input":    0.27,
        "context_window":  64_000,
    },
    "default": {
        "nombre_display":  "Genérico (sin modelo específico)",
        "chars_por_token": 4.0,
        "precio_input":    None,
        "context_window":  None,
    },
}

MODELOS_VALIDOS = list(MODELOS_TOKENS.keys())


# ── Funciones ─────────────────────────────────────────────────────────────────

def estimar_tokens(texto: str, modelo: str = "default") -> dict:
    info   = MODELOS_TOKENS.get(modelo, MODELOS_TOKENS["default"])
    chars  = len(texto)
    tokens = int(chars / info["chars_por_token"])
    costo_usd = (tokens / 1_000_000) * info["precio_input"] \
                if info["precio_input"] is not None else None
    porcentaje_window = (tokens / info["context_window"]) * 100 \
                        if info["context_window"] is not None else None
    return {
        "chars": chars, "tokens": tokens, "costo_usd": costo_usd,
        "porcentaje_window": porcentaje_window,
        "info_modelo": info, "modelo_key": modelo,
    }


def formatear_estimacion_tokens(est: dict) -> str:
    sep  = "=" * 72
    info = est["info_modelo"]
    lines = [
        f"\n# {sep}",
        f"# ESTIMACIÓN DE TOKENS",
        f"# {sep}",
        f"#",
        f"#  Modelo           : {info['nombre_display']}",
        f"#  Caracteres       : {est['chars']:,}".replace(",", "."),
        f"#  Tokens estimados : ~{est['tokens']:,}".replace(",", "."),
    ]
    if est["costo_usd"] is not None:
        lines.append(f"#  Costo estimado   : ~${est['costo_usd']:.4f} USD  (solo tokens de entrada)")
    else:
        lines.append(f"#  Costo estimado   : no disponible (varía según proveedor)")
    if est["porcentaje_window"] is not None:
        cw_fmt = f"{info['context_window']:,}".replace(",", ".")
        pct    = est["porcentaje_window"]
        estado = "✓ entra" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE EL LÍMITE")
        lines.append(f"#  Context window   : {cw_fmt} tokens  →  {pct:.1f}% usado  [{estado}]")
    else:
        lines.append(f"#  Context window   : no especificado para este modelo")
    lines += [
        f"#",
        f"#  Nota: los precios y límites pueden haber cambiado. Verificá en",
        f"#  la documentación oficial del modelo antes de tomar decisiones de costo.",
        f"# {sep}",
    ]
    return "\n".join(lines) + "\n"


def objetivo_a_slug(objetivo: str, sufijo: str) -> str:
    """
    Convierte el texto del objetivo en un slug limpio para el nombre del archivo.
    Ej: "Agregar autenticación JWT" → "ia_agregar_autenticacion_jwt_contexto.txt"
    """
    slug = objetivo.lower()
    for src, dst in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),
                     ("ñ","n"),("ü","u"),("à","a"),("è","e"),("ì","i"),
                     ("ò","o"),("ù","u")]:
        slug = slug.replace(src, dst)
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    slug = re.sub(r"_+", "_", slug)
    slug = slug[:40].rstrip("_")
    return f"ia_{slug}_{sufijo}.txt"