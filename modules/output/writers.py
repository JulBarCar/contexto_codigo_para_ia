"""
modules/output/writers.py
Escritura de todos los archivos de salida del proyecto.

Funciones públicas:
  leer_contenido          — lee y opcionalmente comprime un archivo
  escribir_encabezado     — cabecera estándar de texto plano
  _escribir_y_estimar     — helper: escribe + estima tokens
  escribir_archivo        — modo estándar (contexto completo o cambios)
  escribir_context_only   — modo --co (árbol + fichas + grafo, sin código)
  escribir_mapa_ia        — modo --co + --objetivo (XML para IA sin código)
  escribir_archivo_ia     — modo --objetivo (XML para IA con código)
"""

from datetime import datetime
from pathlib import Path

from modules.ai import estimar_tokens, formatear_estimacion_tokens
from modules.imports.core import _construir_grafo, extraer_importaciones
from modules.output.tree_builder import construir_arbol

try:
    from modules.compresor import comprimir_texto, NivelCompresion, EXTENSIONES_SOPORTADAS
    COMPRESION_DISPONIBLE = True
except ImportError:
    COMPRESION_DISPONIBLE = False


# ── Lectura con compresión opcional ──────────────────────────────────────────

def leer_contenido(archivo: Path, config: dict) -> str:
    """
    Lee el contenido de un archivo, aplicando compresión si está activada.
    Devuelve siempre una string con el contenido listo para escribir.
    """
    try:
        contenido = archivo.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"# [No se pudo leer: {e}]\n"

    nivel_str = config.get("comprimir")
    if not nivel_str or not COMPRESION_DISPONIBLE:
        return contenido

    if archivo.suffix not in EXTENSIONES_SOPORTADAS:
        return contenido

    try:
        resultado = comprimir_texto(contenido, archivo.suffix, NivelCompresion(nivel_str))
        return resultado["texto"]
    except Exception:
        return contenido


# ── Escritura: helpers ────────────────────────────────────────────────────────

def escribir_encabezado(f, config: dict, raiz: Path, titulo: str,
                         n_archivos: int, nota_extra: str = "") -> None:
    sep = "=" * 72
    f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"# {titulo}\n")
    f.write(f"# Carpeta origen: {raiz}\n")
    if config.get("descripcion"):
        f.write(f"\n# DESCRIPCIÓN DEL PROYECTO\n# {config['descripcion']}\n")
    f.write(f"# Extensiones incluidas : {', '.join(sorted(config['extensiones']))}\n")
    f.write(f"# Ignorados             : {', '.join(sorted(config['ignorar']))}\n")
    if config["incluir_solo"]:
        f.write(f"# Carpetas incluidas    : {', '.join(config['incluir_solo'])}\n")
    if nota_extra:
        f.write(f"# {nota_extra}\n")
    f.write(f"# Total de archivos     : {n_archivos}\n")
    f.write(f"\n# {sep}\n\n")


def _escribir_y_estimar(salida_path: Path, writer_fn, modelo: str,
                         incluir_en_archivo: bool = False) -> dict | None:
    with open(salida_path, "w", encoding="utf-8") as f:
        writer_fn(f)
    try:
        texto = salida_path.read_text(encoding="utf-8", errors="replace")
        est   = estimar_tokens(texto, modelo)
        if incluir_en_archivo:
            with open(salida_path, "a", encoding="utf-8") as f:
                f.write(formatear_estimacion_tokens(est))
        return est
    except Exception:
        return None


# ── Escritura: modo estándar ──────────────────────────────────────────────────

def escribir_archivo(salida_path: Path, archivos: list[Path], raiz: Path,
                      config: dict, titulo: str, nota_extra: str = "",
                      modelo: str = "default") -> dict | None:
    sep = "=" * 72

    def writer(f):
        escribir_encabezado(f, config, raiz, titulo, len(archivos), nota_extra)
        f.write(f"# ÁRBOL DE ARCHIVOS\n# {sep}\n\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n\n")
        f.write(f"# {sep}\n# CONTENIDO\n# {sep}\n")
        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            f.write(f"\n\n# --- {relativo} ---\n\n")
            contenido = leer_contenido(archivo, config)
            f.write(contenido)
            if not contenido.endswith("\n"):
                f.write("\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=True)


# ── Escritura: modo --co ──────────────────────────────────────────────────────

def escribir_context_only(salida_path: Path, archivos: list[Path],
                           raiz: Path, config: dict, commits: list[str],
                           modelo: str = "default") -> dict | None:
    sep = "=" * 72

    def writer(f):
        escribir_encabezado(f, config, raiz, "MAPA DE CONTEXTO (sin código)", len(archivos))
        if commits:
            f.write(f"# ÚLTIMOS COMMITS\n# {sep}\n")
            for c in commits:
                f.write(f"#   {c}\n")
            f.write("\n")
        f.write(f"# ÁRBOL DE ARCHIVOS\n# {sep}\n\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n\n")
        f.write(f"# {sep}\n# FICHA POR ARCHIVO\n# {sep}\n\n")
        for archivo in archivos:
            relativo      = archivo.relative_to(raiz)
            importaciones = extraer_importaciones(archivo)
            try:
                lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            except Exception:
                lineas = "?"
            f.write(f"## {relativo}\n")
            f.write(f"   Líneas   : {lineas}\n")
            f.write(f"   Extensión: {archivo.suffix}\n")
            if importaciones:
                f.write(f"   Importa  : {', '.join(importaciones[:15])}")
                if len(importaciones) > 15:
                    f.write(f" ... (+{len(importaciones)-15} más)")
                f.write("\n")
            else:
                f.write("   Importa  : (ninguna detectada)\n")
            f.write("\n")

        f.write(f"# {sep}\n# GRAFO DE DEPENDENCIAS INTERNAS\n# {sep}\n\n")
        f.write("# (Muestra qué archivos del proyecto se importan entre sí)\n\n")

        dep_lines = _construir_grafo(archivos, raiz)
        if dep_lines:
            for rel, deps in dep_lines:
                f.write(f"  {rel}\n")
                for d in deps:
                    f.write(f"    └─ {d}\n")
                f.write("\n")
        else:
            f.write("  (No se detectaron dependencias internas entre los archivos incluidos)\n\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=True)


# ── Escritura: modo --co + --objetivo (mapa XML para IA) ─────────────────────

def escribir_mapa_ia(salida_path: Path, archivos: list[Path],
                      raiz: Path, config: dict, commits: list[str] | None = None,
                      modelo: str = "default") -> dict | None:
    """
    Genera un mapa de contexto (sin código) optimizado para ser leído por una IA.
    Combina la info estructural de --co con el formato XML de --objetivo.
    """
    objetivo    = config.get("objetivo", "")
    descripcion = config.get("descripcion", "")
    ts          = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    modelo_flag = f" --modelo {config.get('modelo', 'default')}" \
                  if config.get("modelo") and config.get("modelo") != "default" else ""
    cmd_followup = (
        f"contexto {raiz} --objetivo \"{objetivo}\"{modelo_flag} --archivos "
        f"[ruta/archivo1] [ruta/archivo2] ..."
    )

    def writer(f):
        f.write("<context_metadata>\n")
        f.write(f"  generated_at: {ts}\n")
        f.write(f"  project_root: {raiz}\n")
        if descripcion:
            f.write(f"  project_description: {descripcion}\n")
        f.write(f"  file_count: {len(archivos)}\n")
        f.write(f"  extensions_included: {', '.join(sorted(config['extensiones']))}\n")
        if config.get("incluir_solo"):
            f.write(f"  root_dirs_included: {', '.join(config['incluir_solo'])}\n")
        f.write(f"  content_type: structure_only (no source code)\n")
        if commits:
            f.write(f"  recent_commits:\n")
            for c in commits[:5]:
                f.write(f"    - {c}\n")
        f.write("</context_metadata>\n\n")

        f.write("<task>\n")
        f.write(f"  {objetivo}\n")
        f.write("</task>\n\n")

        f.write("<file_tree>\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n</file_tree>\n\n")

        f.write("<file_index>\n")
        for archivo in archivos:
            relativo      = archivo.relative_to(raiz)
            importaciones = extraer_importaciones(archivo)
            try:
                n_lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            except Exception:
                n_lineas = "?"
            f.write(f"  <file path=\"{relativo.as_posix()}\"")
            f.write(f" lines=\"{n_lineas}\"")
            f.write(f" ext=\"{archivo.suffix}\"")
            if importaciones:
                deps_str = ", ".join(importaciones[:15])
                if len(importaciones) > 15:
                    deps_str += f" (+{len(importaciones)-15})"
                f.write(f" imports=\"{deps_str}\"")
            f.write(" />\n")
        f.write("</file_index>\n\n")

        dep_lines = _construir_grafo(archivos, raiz)
        f.write("<dependency_graph>\n")
        if dep_lines:
            for rel, deps in dep_lines:
                f.write(f"  <file path=\"{rel}\" depends_on=\"{', '.join(deps)}\" />\n")
        else:
            f.write("  <!-- no internal dependencies detected -->\n")
        f.write("</dependency_graph>\n\n")

        f.write("<response_instructions>\n")
        f.write("  You are receiving the structural map of a codebase (no source code).\n")
        f.write("  Your task is defined in <task>.\n\n")
        f.write("  STEP 1 — Analyze the structure:\n")
        f.write("    Use <file_tree>, <file_index>, and <dependency_graph> to understand\n")
        f.write("    the project layout, module sizes, and how files relate to each other.\n\n")
        f.write("  STEP 2 — Identify relevant files:\n")
        f.write("    Based on the structure and your task, determine which files you need\n")
        f.write("    to read to provide a complete and accurate response.\n\n")
        f.write("  STEP 3 — Output the follow-up command:\n")
        f.write("    Output EXACTLY this block (copy-paste ready, no surrounding text),\n")
        f.write("    replacing the placeholders with the actual file paths you need:\n\n")
        f.write("    <follow_up_command>\n")
        f.write(f"    {cmd_followup}\n")
        f.write("    </follow_up_command>\n\n")
        f.write("    Use forward slashes. Paths are relative to project_root.\n")
        f.write("    Be selective — only request files genuinely needed for the task.\n")
        f.write("</response_instructions>\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=False)


# ── Escritura: modo --objetivo (XML para IA con código) ──────────────────────

def escribir_archivo_ia(salida_path: Path, archivos: list[Path], raiz: Path,
                         config: dict, es_solicitado: bool = False,
                         commits: list[str] | None = None,
                         modelo: str = "default",
                         es_segunda_vuelta: bool = False) -> dict | None:
    """
    Genera un archivo de contexto optimizado para ser leído directamente por una IA.
    Sin decoración visual. Estructura semántica con etiquetas tipo XML.
    """
    objetivo    = config.get("objetivo", "")
    descripcion = config.get("descripcion", "")
    ts          = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    modelo_flag = f" --modelo {config.get('modelo', 'default')}" \
                  if config.get("modelo") and config.get("modelo") != "default" else ""
    cmd_followup = (
        f"contexto {raiz} --objetivo \"{objetivo}\"{modelo_flag} --archivos "
        f"[ruta/archivo1] [ruta/archivo2] ..."
    )

    def writer(f):
        if not es_segunda_vuelta:
            f.write("<context_metadata>\n")
            f.write(f"  generated_at: {ts}\n")
            f.write(f"  project_root: {raiz}\n")
            if descripcion:
                f.write(f"  project_description: {descripcion}\n")
            f.write(f"  file_count: {len(archivos)}\n")
            f.write(f"  extensions_included: {', '.join(sorted(config['extensiones']))}\n")
            if config.get("incluir_solo"):
                f.write(f"  root_dirs_included: {', '.join(config['incluir_solo'])}\n")
            if commits:
                f.write(f"  recent_commits:\n")
                for c in commits[:5]:
                    f.write(f"    - {c}\n")
            f.write("</context_metadata>\n\n")

            f.write("<task>\n")
            f.write(f"  {objetivo}\n")
            f.write("</task>\n\n")

            f.write("<file_index>\n")
            for archivo in archivos:
                relativo      = archivo.relative_to(raiz)
                importaciones = extraer_importaciones(archivo)
                try:
                    n_lineas = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
                except Exception:
                    n_lineas = "?"
                f.write(f"  <file path=\"{relativo.as_posix()}\"")
                f.write(f" lines=\"{n_lineas}\"")
                f.write(f" ext=\"{archivo.suffix}\"")
                if importaciones:
                    deps_str = ", ".join(importaciones[:15])
                    if len(importaciones) > 15:
                        deps_str += f" (+{len(importaciones)-15})"
                    f.write(f" imports=\"{deps_str}\"")
                f.write(" />\n")
            f.write("</file_index>\n\n")

            f.write("<codebase>\n")

        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            if es_segunda_vuelta:
                f.write(f"### Archivo: {relativo.as_posix()} ###\n")
            else:
                f.write(f"\n<file path=\"{relativo.as_posix()}\">\n")
            contenido = leer_contenido(archivo, config)
            f.write(contenido)
            if not contenido.endswith("\n"):
                f.write("\n")
            if not es_segunda_vuelta:
                f.write(f"</file>\n")

        if not es_segunda_vuelta:
            f.write("\n</codebase>\n\n")

            f.write("<response_instructions>\n")
            if not es_solicitado:
                f.write("  You are receiving the full codebase for the project described above.\n")
                f.write("  Your task is defined in <task>.\n\n")
                f.write("  STEP 1 — Identify missing context:\n")
                f.write("    If you need additional files not present in <codebase> to complete\n")
                f.write("    the task, list each one with a one-sentence reason.\n\n")
                f.write("  STEP 2 — Provide a follow-up command:\n")
                f.write("    If additional files are needed, output EXACTLY this block\n")
                f.write("    (copy-paste ready, no surrounding text):\n\n")
                f.write("    <follow_up_command>\n")
                f.write(f"    {cmd_followup}\n")
                f.write("    </follow_up_command>\n\n")
                f.write("    Replace the placeholder paths with real relative paths.\n")
                f.write("    Use forward slashes. Paths are relative to project_root.\n\n")
                f.write("  STEP 3 — If you already have enough context:\n")
                f.write("    State that explicitly, then proceed directly with your response.\n")
                f.write("    Do not output <follow_up_command>.\n")
            else:
                f.write("  You are receiving the specific files you requested.\n")
                f.write("  Your task is defined in <task>.\n")
                f.write("  You now have sufficient context. Proceed with your full response.\n")
                f.write("  Do not ask for additional files.\n")
            f.write("</response_instructions>\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=False)