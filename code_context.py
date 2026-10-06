"""
code_context.py
Recorre la carpeta del proyecto y unifica todos los archivos de código
en un único archivo de texto, listo para pasar a una IA.

Genera hasta siete archivos:
  1. contexto_codigo.txt          → todo el proyecto
  2. cambios_git.txt              → solo archivos modificados desde el último pull
  3. mapa_contexto.txt            → con --co: árbol + dependencias, sin código
  4. ia_[objetivo]_contexto.txt   → con --objetivo: contexto optimizado para IA
  5. ia_[objetivo]_solicitado.txt → con --objetivo + --archivos: archivos pedidos por IA
  6. mapa_contexto.md             → con --md: documento Markdown amigable para humanos
  7. mapa_contexto.tex / .pdf     → con --latex: documento LaTeX (compila a PDF si hay pdflatex)

Modos máquina (para agentes):
  --json        → una sola línea JSON en stdout con el resultado estructurado
  --stdout      → el contenido generado va directo a stdout, sin escribir archivo
  --sin-instrucciones → omite <response_instructions> en los archivos ia_*

Configuración opcional: crea '.codigo_config.json' en la raíz del proyecto.
Si no existe, funciona con los valores por defecto.
Usa `--init` para generar un archivo de configuración de ejemplo.

Estructura del proyecto:
  code_context.py               ← este archivo (orquestador)
  modules/
    ai.py                       ← estimación de tokens, modelos, slugs
    cli.py                      ← parseo de argumentos CLI
    git.py                      ← integración con git
    compresor.py                ← compresión de código fuente
    config/
      defaults.py               ← constantes y valores por defecto
      loader.py                 ← carga de .codigo_config.json
    filesystem/
      ordering.py               ← ordenación de archivos por prioridad
      filters.py                ← filtrado y recolección de archivos
    aliases/
      loaders.py                ← lectura de aliases (tsconfig, vite, webpack...)
      resolver.py               ← resolución de imports a rutas reales
    imports/
      core.py                   ← extracción de imports y grafo de dependencias
    output/
      console.py                ← streams de consola, modo JSON, errores
      tree_builder.py           ← árbol visual de archivos
      log.py                    ← logging de resultados [OK]
      preview.py                ← modos --preview y --stats
      writers.py                ← escritura de todos los archivos de salida
      human_writers.py          ← escritura Markdown y LaTeX para humanos
"""

import sys
import shutil
from pathlib import Path

from modules.cli import parsear_args
from modules.config.loader import cargar_config, generar_config_ejemplo
from modules.config.defaults import NOMBRE_CONFIG
from modules.ai import MODELOS_TOKENS, estimar_tokens, objetivo_a_slug
from modules.git import obtener_archivos_modificados, obtener_ultimos_commits
from modules.filesystem.filters import recolectar_archivos, filtrar_por_config
from modules.filesystem.ordering import ordenar_archivos
from modules.output import console
from modules.output.writers import (
    escribir_archivo,
    escribir_context_only,
    escribir_mapa_ia,
    escribir_archivo_ia,
    _rol_archivo,
)
from modules.imports.core import _construir_grafo, extraer_importaciones
from modules.analysis.symbols import extraer_simbolos
from modules.output.preview import mostrar_preview, mostrar_stats
from modules.output.log import _log_ok
from modules.output.human_writers import escribir_markdown, escribir_latex, compilar_latex

try:
    from modules.compresor import comprimir_texto  # noqa: F401 — valida disponibilidad
    COMPRESION_DISPONIBLE = True
except ImportError:
    COMPRESION_DISPONIBLE = False


VERSION = "0.3.0"


# ── Helpers de salida máquina ─────────────────────────────────────────────────

MAX_INCLUDED = 50
MAX_DROPPED = 50

# Presupuesto: estimación de la parte fija del XML (metadatos, task, árbol,
# grafo e instrucciones) y del coste por archivo (línea de file_index + tags).
_BASE_PRESUPUESTO = 400
_COSTO_ARCHIVO_FIJO = 70


def _advertencias(est: dict | None) -> list[str]:
    if not est or est.get("porcentaje_window") is None:
        return []
    pct = est["porcentaje_window"]
    if pct > 100:
        return ["window_exceeded"]
    if pct > 85:
        return ["window_near_limit"]
    return []


def _ruta_posix(archivo: Path, raiz: Path) -> str:
    try:
        return archivo.relative_to(raiz).as_posix()
    except ValueError:
        return str(archivo)


def _campos_presupuesto(omitidos: list[Path] | None, raiz: Path,
                        presupuesto: int | None) -> dict:
    omitidos = omitidos or []
    return {
        "dropped": [_ruta_posix(p, raiz) for p in omitidos[:MAX_DROPPED]],
        "dropped_count": len(omitidos),
        "presupuesto": presupuesto,
    }


def _aplicar_presupuesto(archivos: list[Path], modelo: str,
                         presupuesto: int) -> tuple[list[Path], list[Path]]:
    """
    Devuelve (incluidos, omitidos). Corta en el primer archivo que no cabe,
    preservando el orden de prioridad. Siempre incluye al menos un archivo,
    aunque exceda el tope. No lee archivos: estima por tamaño en disco.
    """
    cpt = MODELOS_TOKENS.get(modelo, MODELOS_TOKENS["default"])["chars_por_token"]
    usados = _BASE_PRESUPUESTO
    incluidos: list[Path] = []
    omitidos: list[Path] = []

    for i, archivo in enumerate(archivos):
        try:
            costo = int(archivo.stat().st_size / cpt) + _COSTO_ARCHIVO_FIJO
        except OSError:
            costo = _COSTO_ARCHIVO_FIJO
        if incluidos and usados + costo > presupuesto:
            omitidos = archivos[i:]
            break
        incluidos.append(archivo)
        usados += costo

    return incluidos, omitidos


def _resumen_base(mode: str, salida_path: Path | None, archivos: list[Path],
                  est: dict | None, raiz: Path,
                  omitidos: list[Path] | None = None,
                  presupuesto: int | None = None) -> dict:
    incluidos = [_ruta_posix(a, raiz) for a in archivos]
    return {
        "ok": True,
        "mode": mode,
        "version": VERSION,
        "output_path": str(salida_path) if salida_path else None,
        "files": len(archivos),
        "included": incluidos[:MAX_INCLUDED],
        "included_omitted": max(0, len(incluidos) - MAX_INCLUDED),
        "tokens": est["tokens"] if est else None,
        "bytes": est["chars"] if est else None,
        "model": est["modelo_key"] if est else None,
        "window_pct": round(est["porcentaje_window"], 1)
                      if est and est.get("porcentaje_window") is not None else None,
        "cost_usd": round(est["costo_usd"], 4)
                    if est and est.get("costo_usd") is not None else None,
        "warnings": _advertencias(est),
        **_campos_presupuesto(omitidos, raiz, presupuesto),
    }


def _entregar_salida(salida_path: Path, mode: str, archivos: list[Path],
                     est: dict | None, args: dict, modelo: str,
                     raiz: Path, omitidos: list[Path] | None = None) -> dict:
    """
    Construye el resumen del resultado. Con --stdout: lee el archivo generado,
    lo borra y lo devuelve por stdout (crudo o dentro del JSON).
    """
    resumen = _resumen_base(mode, salida_path, archivos, est, raiz,
                            omitidos, args.get("presupuesto"))
    resumen["stdout"] = bool(args.get("stdout"))
    if mode == "mapa_ia":
        total_tokens = _estimar_tokens_fuente(archivos, modelo)
        resumen["estimated_full_context_tokens"] = total_tokens

    if not args.get("stdout"):
        return resumen

    try:
        texto = salida_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        console.fallar(f"No se pudo leer el archivo generado '{salida_path}': {e}", 1)

    est_contenido = estimar_tokens(texto, modelo)
    tope = args.get("max_stdout") or 0
    if tope and est_contenido["tokens"] > tope:
        # Se conserva el archivo: el agente puede leerlo sin regenerar.
        console.fallar(
            f"El contenido tiene ~{est_contenido['tokens']} tokens y supera "
            f"--max-stdout {tope}. Archivo generado en: {salida_path} "
            f"— leelo por partes (sin --stdout).",
            3,
            tokens=est_contenido["tokens"],
            max_stdout=tope,
            mode=mode,
            output_path=str(salida_path),
        )

    salida_path.unlink(missing_ok=True)

    resumen["tokens"] = est_contenido["tokens"]
    resumen["bytes"] = est_contenido["chars"]
    resumen["output_path"] = None
    if resumen.get("estimated_full_context_tokens") and est_contenido["tokens"]:
        total = resumen["estimated_full_context_tokens"]
        resumen["estimated_savings_pct"] = round(
            max(0, 1 - (est_contenido["tokens"] / total)) * 100, 1)

    if args.get("json"):
        resumen["content"] = texto
    else:
        console.emitir_contenido(texto)

    return resumen


def _sin_salida(mode: str, nota: str, presupuesto: int | None = None) -> dict:
    return {"ok": True, "mode": mode, "output_path": None, "files": 0,
            "version": VERSION,
            "dropped": [], "dropped_count": 0, "presupuesto": presupuesto,
            "notes": [nota]}


def _estimar_tokens_fuente(archivos: list[Path], modelo: str) -> int:
    cpt = MODELOS_TOKENS.get(modelo, MODELOS_TOKENS["default"])["chars_por_token"]
    total_chars = 0
    for archivo in archivos:
        try:
            total_chars += archivo.stat().st_size
        except OSError:
            continue
    return int(total_chars / cpt)


def _version_payload() -> dict:
    return {"ok": True, "mode": "version", "version": VERSION}


def _doctor(args: dict) -> dict:
    raiz = Path(args["carpeta"]).resolve()
    install_dir = Path.home() / "code-context"
    skill_path = Path.home() / ".config" / "opencode" / "skills" / "contexto" / "SKILL.md"
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("python", True, sys.executable)

    contexto_cmd = shutil.which("contexto")
    add("contexto_on_path", contexto_cmd is not None,
        contexto_cmd or "contexto no encontrado en PATH")

    if install_dir.exists():
        add("windows_install_dir", True, str(install_dir))
    else:
        add("windows_install_dir", False, f"no existe: {install_dir}")

    add("opencode_skill", skill_path.exists(), str(skill_path))

    salida_dir = raiz / ".codigo_completo"
    try:
        salida_dir.mkdir(parents=True, exist_ok=True)
        probe = salida_dir / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        add("output_writable", True, str(salida_dir))
    except OSError as e:
        add("output_writable", False, f"{salida_dir}: {e}")

    config_path = raiz / NOMBRE_CONFIG
    if config_path.exists():
        try:
            cargar_config(raiz)
            add("config", True, str(config_path))
        except Exception as e:
            add("config", False, f"{config_path}: {type(e).__name__}: {e}")
    else:
        add("config", True, "sin .codigo_config.json, se usaran defaults")

    ok = all(c["ok"] for c in checks)
    return {"ok": ok, "mode": "doctor", "version": VERSION, "root": str(raiz),
            "checks": checks}


def _impacto_archivo(args: dict, archivos: list[Path], raiz: Path,
                     modelo: str) -> dict:
    objetivo = args.get("impact")
    candidato = (raiz / objetivo).resolve()
    rel_obj = _ruta_posix(candidato, raiz)
    incluidos = {a.resolve(): a for a in archivos}
    por_rel = {_ruta_posix(a, raiz): a for a in archivos}

    if candidato not in incluidos:
        existe = candidato.exists()
        return {
            "ok": False,
            "mode": "impact",
            "version": VERSION,
            "file": rel_obj,
            "included": False,
            "exists": existe,
            "reason": "file_not_included_by_current_config" if existe else "file_not_found",
        }

    dep_lookup = dict(_construir_grafo(archivos, raiz))
    usados_por: dict[str, list[str]] = {}
    for origen, deps in dep_lookup.items():
        for dep in deps:
            usados_por.setdefault(dep, []).append(origen)

    archivo = incluidos[candidato]
    texto = archivo.read_text(encoding="utf-8", errors="replace")
    importaciones = extraer_importaciones(archivo)
    simbolos = ", ".join(extraer_simbolos(archivo)[:12])
    tokens = estimar_tokens(texto, modelo)["tokens"]
    depends_on = dep_lookup.get(rel_obj, [])
    used_by = usados_por.get(rel_obj, [])
    contexto_recomendado = list(dict.fromkeys([rel_obj, *depends_on, *used_by]))
    return {
        "ok": True,
        "mode": "impact",
        "version": VERSION,
        "file": rel_obj,
        "included": True,
        "exists": True,
        "role": _rol_archivo(rel_obj, simbolos, importaciones),
        "tokens": tokens,
        "imports": importaciones,
        "depends_on": depends_on,
        "used_by": used_by,
        "recommended_context": contexto_recomendado[:20],
        "recommended_files_existing": [p for p in contexto_recomendado[:20] if p in por_rel],
    }


# ── Orquestador principal ─────────────────────────────────────────────────────

def unificar(args: dict) -> dict | None:
    if args.get("version"):
        payload = _version_payload()
        if not args.get("json"):
            print(VERSION)
        return payload

    if args.get("doctor"):
        resumen = _doctor(args)
        if not args.get("json"):
            estado = "OK" if resumen["ok"] else "ERROR"
            print(f"contexto doctor {estado} (version {VERSION})")
            for check in resumen["checks"]:
                marca = "OK" if check["ok"] else "ERROR"
                print(f"[{marca}] {check['name']}: {check['detail']}")
        return resumen

    raiz = Path(args["carpeta"]).resolve()

    if not raiz.exists():
        console.fallar(f"La carpeta '{raiz}' no existe.", 1)

    if args["init"]:
        generar_config_ejemplo(raiz, limpio=args["init_limpio"])
        return {"ok": True, "mode": "init", "output_path": str(raiz / NOMBRE_CONFIG)}

    config     = cargar_config(raiz)
    salida_dir = config["carpeta_salida"]

    # CLI tiene prioridad sobre el config file
    if args["limite"] is not None:
        config["limite_lineas"] = args["limite"]
    if args["sin_minimos"]:
        config["omitir_autogenerados"] = True
    if args["objetivo"]:
        config["objetivo"] = args["objetivo"]
    if args["modelo"] is not None:
        config["modelo"] = args["modelo"]
    if args.get("comprimir"):
        config["comprimir"] = args["comprimir"]
    if args["ignorar_extra"]:
        config["ignorar"] = config["ignorar"] | set(args["ignorar_extra"])

    modelo = config.get("modelo", "default")

    try:
        salida_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        console.fallar(f"No se pudo crear la carpeta de salida '{salida_dir}': {e}", 1)

    print(f"[CONFIG] Salida en: {salida_dir}")
    if modelo != "default":
        print(f"[CONFIG] Modelo    : {MODELOS_TOKENS[modelo]['nombre_display']}")
    if config.get("comprimir"):
        if COMPRESION_DISPONIBLE:
            print(f"[CONFIG] Compresión  : activada  (nivel={config['comprimir']})")
        else:
            print("[AVISO]  --comprimir requiere modules/compresor.py.")
    if args["ignorar_extra"]:
        print(f"[CONFIG] Ignorando extra: {', '.join(args['ignorar_extra'])}")

    con_objetivo = bool(config.get("objetivo"))
    instrucciones = not args["sin_instrucciones"]

    if args["stdout"]:
        permitido = args["co"] or con_objetivo or args["archivos"] is not None \
                    or args["solo_cambios"]
        if not permitido:
            console.fallar(
                "--stdout solo aplica con --co, --objetivo, --archivos o "
                "--solo-cambios. Para el contexto completo usá --json "
                "(recibís output_path, tokens y window_pct).", 2)

    # ── Modo --archivos ───────────────────────────────────────────────────────
    if args["archivos"] is not None:
        archivos_resueltos = []
        for ruta_str in args["archivos"]:
            candidato = (raiz / ruta_str).resolve()
            if not candidato.exists():
                print(f"[AVISO]  No existe, se omite: {ruta_str}")
                continue
            if candidato.is_dir():
                interior = filtrar_por_config(
                    [p for p in candidato.rglob("*")],
                    raiz, config,
                    omitir_autogenerados=config.get("omitir_autogenerados", False),
                    limite_lineas=config.get("limite_lineas"),
                    verbose=args["verbose"],
                )
                if not interior:
                    print(f"[AVISO]  El directorio no contiene archivos incluibles: {ruta_str}")
                    continue
                archivos_resueltos.extend(interior)
                continue
            if not candidato.is_file():
                print(f"[AVISO]  No es un archivo ni un directorio, se omite: {ruta_str}")
                continue
            archivos_resueltos.append(candidato)

        if not archivos_resueltos:
            console.fallar("Ninguna de las rutas indicadas con --archivos existe "
                           "o contiene archivos incluibles.", 1)

        archivos_resueltos = ordenar_archivos(list(dict.fromkeys(archivos_resueltos)))

        omitidos_seleccion: list[Path] = []
        if args.get("presupuesto"):
            archivos_resueltos, omitidos_seleccion = _aplicar_presupuesto(
                archivos_resueltos, modelo, args["presupuesto"])
            if omitidos_seleccion:
                print(f"[AVISO]  Presupuesto ~{args['presupuesto']} tokens: "
                      f"{len(omitidos_seleccion)} archivo(s) fuera de presupuesto.")

        if con_objetivo:
            nombre_salida = objetivo_a_slug(config["objetivo"], "solicitado")
            salida_path   = salida_dir / nombre_salida
            est = escribir_archivo_ia(
                salida_path=salida_path,
                archivos=archivos_resueltos,
                raiz=raiz,
                config=config,
                es_solicitado=True,
                modelo=modelo,
                es_segunda_vuelta=args["continua"],
                incluir_instrucciones=instrucciones,
            )
            _log_ok("Contexto IA solicitado", salida_path, len(archivos_resueltos), est)
        else:
            salida_path = salida_dir / "contexto_solicitado.txt"
            est = escribir_archivo(
                salida_path=salida_path,
                archivos=archivos_resueltos,
                raiz=raiz,
                config=config,
                titulo="CONTEXTO SOLICITADO  |  Objetivo: no especificado",
                modelo=modelo,
            )
            _log_ok("Contexto solicitado", salida_path, len(archivos_resueltos), est)

        modo = "solicitado_ia" if con_objetivo else "solicitado"
        return _entregar_salida(salida_path, modo, archivos_resueltos, est,
                                args, modelo, raiz, omitidos_seleccion)

    todos = recolectar_archivos(
        raiz, config,
        omitir_autogenerados=config.get("omitir_autogenerados", False),
        limite_lineas=config.get("limite_lineas"),
        verbose=args["verbose"],
    )

    if not todos:
        print("[AVISO]  No se encontraron archivos con las extensiones configuradas.")
        return _sin_salida("vacio", "sin_archivos", args.get("presupuesto"))

    if args.get("impact"):
        resumen = _impacto_archivo(args, todos, raiz, modelo)
        if not args.get("json"):
            print(f"Impacto: {resumen['file']}")
            print(f"Incluido: {resumen['included']}")
            if resumen.get("included"):
                print(f"Rol: {resumen['role']}")
                print(f"Tokens: ~{resumen['tokens']}")
                print(f"Depende de: {', '.join(resumen['depends_on']) or '(ninguno)'}")
                print(f"Usado por: {', '.join(resumen['used_by']) or '(ninguno)'}")
                print(f"Contexto recomendado: {', '.join(resumen['recommended_context'])}")
            else:
                print(f"Motivo: {resumen['reason']}")
        return resumen

    # ── Presupuesto de tokens ──────────────────────────────────────────────────
    omitidos: list[Path] = []
    # En --solo-cambios puro la salida son los archivos modificados de git,
    # no la colección completa: el presupuesto no aplica.
    usa_todos = args["co"] or con_objetivo or args["preview"] or args["stats"] \
                or not args["solo_cambios"]
    if args.get("presupuesto") and usa_todos:
        todos, omitidos = _aplicar_presupuesto(todos, modelo, args["presupuesto"])
        if omitidos:
            print(f"[AVISO]  Presupuesto ~{args['presupuesto']} tokens: "
                  f"{len(omitidos)} archivo(s) fuera de presupuesto.")

    # ── Modo --preview ────────────────────────────────────────────────────────
    if args["preview"]:
        info = mostrar_preview(todos, raiz, config, modelo)
        return {"ok": True, "mode": "preview", "output_path": None,
                **_campos_presupuesto(omitidos, raiz, args.get("presupuesto")),
                **info}

    # ── Modo --stats ──────────────────────────────────────────────────────────
    if args["stats"]:
        info = mostrar_stats(todos, raiz, modelo)
        return {"ok": True, "mode": "stats", "output_path": None,
                **_campos_presupuesto(omitidos, raiz, args.get("presupuesto")),
                **info}

    # ── Modo --co ─────────────────────────────────────────────────────────────
    if args["co"]:
        commits = obtener_ultimos_commits(raiz)
        if con_objetivo:
            nombre_sal = objetivo_a_slug(config["objetivo"], "mapa")
            salida_co  = salida_dir / nombre_sal
            est = escribir_mapa_ia(salida_co, todos, raiz, config, commits, modelo,
                                   incluir_instrucciones=instrucciones)
            _log_ok("Mapa IA           ", salida_co, len(todos), est)
            print(f"         (estructura sin código, formato IA)")
            return _entregar_salida(salida_co, "mapa_ia", todos, est, args,
                                    modelo, raiz, omitidos)

        salida_co = salida_dir / config["nombre_salida_co"]
        est = escribir_context_only(salida_co, todos, raiz, config, commits, modelo)
        _log_ok("Mapa de contexto  ", salida_co, len(todos), est)
        print(f"         (sin código fuente)")
        print(f"         Este archivo NO contiene código fuente.")
        print(f"         Úsalo para decidir qué archivos pasarle a la IA.")
        print(f"         Luego ejecuta el script indicando solo esas carpetas en 'incluir_solo'")
        print(f"         o usa --solo-cambios si trabajas con git.")
        return _entregar_salida(salida_co, "mapa", todos, est, args, modelo, raiz,
                                omitidos)

    # ── Modo --md / --latex ────────────────────────────────────────────────────
    if args["md"] or args["latex"]:
        commits = obtener_ultimos_commits(raiz)
        salidas: list[Path] = []
        est_primer: dict | None = None

        if args["md"]:
            if con_objetivo:
                nombre_md = objetivo_a_slug(config["objetivo"], "mapa").replace(".txt", ".md")
            else:
                nombre_md = "mapa_contexto.md"
            salida_md = salida_dir / nombre_md
            est = escribir_markdown(salida_md, todos, raiz, config, commits, modelo)
            _log_ok("Mapa Markdown     ", salida_md, len(todos), est)
            print(f"         (sin código fuente, apto para leer en GitHub/Obsidian)")
            salidas.append(salida_md)
            est_primer = est_primer or est

        if args["latex"]:
            if con_objetivo:
                nombre_tex = objetivo_a_slug(config["objetivo"], "mapa").replace(".txt", ".tex")
            else:
                nombre_tex = "mapa_contexto.tex"
            salida_tex = salida_dir / nombre_tex
            est = escribir_latex(salida_tex, todos, raiz, config, commits, modelo)
            _log_ok("Mapa LaTeX        ", salida_tex, len(todos), est)
            compilar_latex(salida_tex)
            salidas.append(salida_tex)
            est_primer = est_primer or est

        if args["md"] and args["latex"]:
            modo = "markdown+latex"
        elif args["md"]:
            modo = "markdown"
        else:
            modo = "latex"
        resumen = _resumen_base(modo, salidas[0], todos, est_primer, raiz,
                                omitidos, args.get("presupuesto"))
        resumen["outputs"] = [str(p) for p in salidas]
        return resumen

    # ── Modo --objetivo: contexto completo optimizado para IA ─────────────────
    if con_objetivo:
        commits    = obtener_ultimos_commits(raiz)
        nombre_sal = objetivo_a_slug(config["objetivo"], "contexto")
        salida_ia  = salida_dir / nombre_sal
        est = escribir_archivo_ia(
            salida_path=salida_ia,
            archivos=todos,
            raiz=raiz,
            config=config,
            es_solicitado=False,
            commits=commits,
            modelo=modelo,
            incluir_instrucciones=instrucciones,
        )
        _log_ok("Contexto IA       ", salida_ia, len(todos), est)
        return _entregar_salida(salida_ia, "contexto_ia", todos, est, args,
                                modelo, raiz, omitidos)

    # ── Contexto completo (modo estándar) ─────────────────────────────────────
    resumen_principal: dict | None = None
    if not args["solo_cambios"]:
        salida_completa = salida_dir / config["nombre_salida"]
        est = escribir_archivo(
            salida_path=salida_completa,
            archivos=todos,
            raiz=raiz,
            config=config,
            titulo="CONTEXTO COMPLETO DEL PROYECTO",
            modelo=modelo,
        )
        _log_ok("Contexto completo ", salida_completa, len(todos), est)
        resumen_principal = _entregar_salida(salida_completa, "contexto", todos,
                                             est, args, modelo, raiz, omitidos)

    # ── Cambios git ───────────────────────────────────────────────────────────
    modificados_raw = obtener_archivos_modificados(raiz)
    if modificados_raw is None:
        return resumen_principal or _sin_salida("cambios", "no_git_repo", args.get("presupuesto"))
    if not modificados_raw:
        print("[OK]     Sin cambios en git — no se genera archivo de cambios.")
        return resumen_principal or _sin_salida("cambios", "sin_cambios", args.get("presupuesto"))

    modificados = filtrar_por_config(
        modificados_raw, raiz, config,
        omitir_autogenerados=config.get("omitir_autogenerados", False),
        limite_lineas=config.get("limite_lineas"),
        verbose=args["verbose"],
    )
    if not modificados:
        print("[OK]     Los archivos modificados no coinciden con las extensiones/carpetas configuradas.")
        return resumen_principal or _sin_salida("cambios", "cambios_filtrados", args.get("presupuesto"))

    commits       = obtener_ultimos_commits(raiz)
    lista_nombres = ", ".join(str(m.relative_to(raiz)) for m in modificados)
    nota          = f"Archivos modificados: {lista_nombres}"
    if commits:
        nota += f" | Commits recientes: {' / '.join(commits[:3])}"

    salida_cambios = salida_dir / config["nombre_salida_cambios"]
    est_cambios = escribir_archivo(
        salida_path=salida_cambios,
        archivos=modificados,
        raiz=raiz,
        config=config,
        titulo="ARCHIVOS MODIFICADOS DESDE EL ÚLTIMO PULL",
        nota_extra=nota,
        modelo=modelo,
    )
    _log_ok("Cambios git       ", salida_cambios, len(modificados), est_cambios)

    if resumen_principal is not None:
        resumen_principal.setdefault("secondary_outputs", []).append({
            "path": str(salida_cambios),
            "mode": "cambios",
            "files": len(modificados),
            "tokens": est_cambios["tokens"] if est_cambios else None,
        })
        return resumen_principal

    return _entregar_salida(salida_cambios, "cambios", modificados, est_cambios,
                            args, modelo, raiz)


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    argv = sys.argv[1:]

    if "--json" in argv or "--agent-map" in argv or "--agent-files" in argv:
        console.activar_json()
    elif "--stdout" in argv:
        console.silenciar_logs()

    args = parsear_args(argv)

    try:
        resumen = unificar(args)
    except SystemExit:
        raise
    except Exception as e:
        if console.MODO_JSON:
            console.fallar(f"{type(e).__name__}: {e}", 1)
        raise

    if console.MODO_JSON:
        console.emitir_json(resumen if resumen is not None else {"ok": True})
