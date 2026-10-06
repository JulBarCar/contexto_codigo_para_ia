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
import re

from modules.ai import estimar_tokens, formatear_estimacion_tokens
from modules.analysis.symbols import extraer_simbolos_de_texto
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

def _rol_archivo(rel_path: str, simbolos: str, importaciones: list[str]) -> str:
    texto = f"{rel_path} {simbolos} {' '.join(importaciones)}".lower()
    nombre = Path(rel_path).name.lower()
    partes = {p.lower() for p in Path(rel_path).parts}
    if nombre in {"main.py", "app.py", "server.py", "index.py", "code_context.py"}:
        return "entrypoint"
    if "tests" in partes or "test" in partes or nombre.startswith("test_") \
            or nombre.endswith("_test.py") or nombre.endswith(".spec.py"):
        return "test"
    if "cli" in texto or "argparse" in texto or "command" in texto:
        return "cli"
    if "config" in texto or "settings" in texto or "defaults" in texto:
        return "config"
    if "writer" in texto or "output" in texto or "render" in texto:
        return "output"
    if "strategy" in texto or "strategies" in texto:
        return "strategy"
    if "route" in texto or "controller" in texto or "/api" in texto:
        return "api"
    if "model" in texto or "schema" in texto or "entity" in texto:
        return "data_model"
    return "source"


def _invertir_grafo(dependencias: dict[str, list[str]]) -> dict[str, list[str]]:
    usados_por: dict[str, list[str]] = {}
    for origen, deps in dependencias.items():
        for dep in deps:
            usados_por.setdefault(dep, []).append(origen)
    return usados_por


def _recomendar_archivos(archivos: list[Path], raiz: Path,
                         dependencias: dict[str, list[str]],
                         roles: dict[str, str], objetivo: str = "",
                         limite: int = 10) -> list[tuple[str, str]]:
    objetivo_l = objetivo.lower()
    pesos_objetivo = {
        "cli": {"cli", "arg", "command", "flag", "comando", "argumento"},
        "config": {"config", "settings", "default", "perfil", "ignore", "ignorar"},
        "output": {"json", "stdout", "output", "writer", "markdown", "latex", "salida"},
        "strategy": {"import", "dependency", "dependencia", "grafo", "strategy", "estrategia"},
        "test": {"test", "testing", "prueba", "unittest"},
        "api": {"api", "route", "endpoint", "controller"},
    }
    candidatos: list[tuple[int, str, str]] = []
    for archivo in archivos:
        rel = archivo.relative_to(raiz).as_posix()
        nombre = archivo.name.lower()
        rol = roles.get(rel, "source")
        score = 0
        razones: list[str] = []
        if rol == "entrypoint":
            score += 100
            razones.append("main entrypoint")
        elif rol in {"cli", "config", "api", "output"}:
            score += 60
            razones.append(f"{rol} role")
        elif rol == "strategy":
            score += 25
            razones.append("strategy implementation")
        for rol_obj, palabras in pesos_objetivo.items():
            if rol == rol_obj and any(p in objetivo_l for p in palabras):
                score += 45
                razones.append("matches task keywords")
        rel_l = rel.lower()
        for palabra in re.findall(r"[a-z0-9_]+", objetivo_l):
            if len(palabra) >= 4 and palabra in rel_l:
                score += 20
                razones.append(f"path matches '{palabra}'")
                break
        if dependencias.get(rel):
            score += min(30, len(dependencias[rel]) * 5)
            razones.append("has internal dependencies")
        if nombre in {"readme.md", "package.json", "pyproject.toml"}:
            score += 40
            razones.append("project metadata")
        if score:
            candidatos.append((score, rel, "; ".join(razones)))

    candidatos.sort(key=lambda item: (-item[0], item[1]))
    return [(rel, reason) for _, rel, reason in candidatos[:limite]]


def _resumen_proyecto(archivos: list[Path], raiz: Path,
                      roles: dict[str, str], dependencias: dict[str, list[str]]) -> list[str]:
    entrypoints = [p for p, r in roles.items() if r == "entrypoint"][:3]
    roles_presentes = sorted(set(roles.values()) - {"source"})
    total_deps = sum(len(v) for v in dependencias.values())
    lineas = [
        f"Detected {len(archivos)} included files under {raiz.name}.",
    ]
    if entrypoints:
        lineas.append(f"Likely entrypoint(s): {', '.join(entrypoints)}.")
    if roles_presentes:
        lineas.append(f"Detected roles: {', '.join(roles_presentes)}.")
    if total_deps:
        lineas.append(f"Resolved {total_deps} internal dependency edge(s).")
    lineas.append("Recommended agent flow: read this map, then request only needed files with --agent-files or --archivos.")
    return lineas

def _escribir_file_index(f, archivos: list[Path], raiz: Path,
                         modelo: str = "default",
                         dependencias: dict[str, list[str]] | None = None,
                         usados_por: dict[str, list[str]] | None = None,
                         roles: dict[str, str] | None = None) -> None:
    """
    Índice compacto por archivo: path, líneas, extensión, tokens y símbolos.
    `symbols` y `tokens` permiten elegir archivos sin tener que abrirlos.
    """
    f.write("<file_index>\n")
    for archivo in archivos:
        relativo      = archivo.relative_to(raiz)
        importaciones = extraer_importaciones(archivo)
        texto         = None
        try:
            texto = archivo.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

        if texto is not None:
            n_lineas = texto.count("\n") + (1 if texto and not texto.endswith("\n") else 0)
            n_tokens = estimar_tokens(texto, modelo)["tokens"]
            simbolos = extraer_simbolos_de_texto(texto, archivo.suffix)
        else:
            n_lineas = "?"
            n_tokens = None
            simbolos = ""

        rel_posix = relativo.as_posix()
        rol = _rol_archivo(rel_posix, simbolos, importaciones)
        if roles is not None:
            roles[rel_posix] = rol

        f.write(f"  <file path=\"{rel_posix}\"")
        f.write(f" lines=\"{n_lineas}\"")
        f.write(f" ext=\"{archivo.suffix}\"")
        f.write(f" role=\"{rol}\"")
        if n_tokens is not None:
            f.write(f" tokens=\"~{n_tokens}\"")
        if simbolos:
            f.write(f" symbols=\"{simbolos}\"")
        if importaciones:
            deps_str = ", ".join(importaciones[:15])
            if len(importaciones) > 15:
                deps_str += f" (+{len(importaciones)-15})"
            f.write(f" imports=\"{deps_str}\"")
        deps_resueltas = dependencias.get(rel_posix) if dependencias else None
        if deps_resueltas:
            f.write(f" depends_on=\"{', '.join(deps_resueltas)}\"")
        refs = usados_por.get(rel_posix) if usados_por else None
        if refs:
            f.write(f" used_by=\"{', '.join(refs)}\"")
        f.write(" />\n")
    f.write("</file_index>\n\n")


def escribir_mapa_ia(salida_path: Path, archivos: list[Path],
                      raiz: Path, config: dict, commits: list[str] | None = None,
                      modelo: str = "default",
                      incluir_instrucciones: bool = True) -> dict | None:
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

        dep_lines = _construir_grafo(archivos, raiz)
        dep_lookup = dict(dep_lines)
        used_by = _invertir_grafo(dep_lookup)
        roles: dict[str, str] = {}

        _escribir_file_index(f, archivos, raiz, modelo, dep_lookup, used_by, roles)

        f.write("<project_summary>\n")
        for linea in _resumen_proyecto(archivos, raiz, roles, dep_lookup):
            f.write(f"  {linea}\n")
        f.write("</project_summary>\n\n")

        recomendados = _recomendar_archivos(archivos, raiz, dep_lookup, roles, objetivo)
        if recomendados:
            f.write("<recommended_files>\n")
            for rel, reason in recomendados:
                f.write(f"  <file path=\"{rel}\" reason=\"{reason}\" />\n")
            f.write("</recommended_files>\n\n")

        f.write("<dependency_graph>\n")
        if dep_lines:
            for rel, deps in dep_lines:
                f.write(f"  <file path=\"{rel}\" depends_on=\"{', '.join(deps)}\" />\n")
        else:
            f.write("  <!-- no internal dependencies detected -->\n")
        f.write("</dependency_graph>\n\n")

        if incluir_instrucciones:
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
                         es_segunda_vuelta: bool = False,
                         incluir_instrucciones: bool = True) -> dict | None:
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

            dep_lookup = dict(_construir_grafo(archivos, raiz))
            used_by = _invertir_grafo(dep_lookup)
            _escribir_file_index(f, archivos, raiz, modelo, dep_lookup, used_by)

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
            f.write("\n</codebase>")

            if incluir_instrucciones:
                f.write("\n\n<response_instructions>\n")
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
                f.write("</response_instructions>")
            f.write("\n")

    return _escribir_y_estimar(salida_path, writer, modelo, incluir_en_archivo=False)
