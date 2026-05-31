"""
code_context.py
Recorre la carpeta del proyecto y unifica todos los archivos de código
en un único archivo de texto, listo para pasar a una IA.

Genera hasta cinco archivos:
  1. contexto_codigo.txt          → todo el proyecto
  2. cambios_git.txt              → solo archivos modificados desde el último pull
  3. mapa_contexto.txt            → con --co: árbol + dependencias, sin código
  4. ia_[objetivo]_contexto.txt   → con --objetivo: contexto optimizado para IA
  5. ia_[objetivo]_solicitado.txt → con --objetivo + --archivos: archivos pedidos por IA

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
    import_analysis/
      core.py                   ← extracción de imports y grafo de dependencias
    output/
      tree_builder.py           ← árbol visual de archivos
      log.py                    ← logging de resultados [OK]
      preview.py                ← modos --preview y --stats
      writers.py                ← escritura de todos los archivos de salida
"""

import sys
from pathlib import Path

from modules.cli import parsear_args
from modules.config.loader import cargar_config, generar_config_ejemplo
from modules.ai import MODELOS_TOKENS, objetivo_a_slug
from modules.git import obtener_archivos_modificados, obtener_ultimos_commits
from modules.filesystem.filters import recolectar_archivos, filtrar_por_config
from modules.filesystem.ordering import ordenar_archivos
from modules.output.writers import (
    escribir_archivo,
    escribir_context_only,
    escribir_mapa_ia,
    escribir_archivo_ia,
)
from modules.output.preview import mostrar_preview, mostrar_stats
from modules.output.log import _log_ok

try:
    from modules.compresor import comprimir_texto  # noqa: F401 — valida disponibilidad
    COMPRESION_DISPONIBLE = True
except ImportError:
    COMPRESION_DISPONIBLE = False


# ── Orquestador principal ─────────────────────────────────────────────────────

def unificar(args: dict) -> None:
    raiz = Path(args["carpeta"]).resolve()

    if not raiz.exists():
        print(f"[ERROR]  La carpeta '{raiz}' no existe.")
        sys.exit(1)

    if args["init"]:
        generar_config_ejemplo(raiz, limpio=args["init_limpio"])
        return

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
        print(f"[ERROR]  No se pudo crear la carpeta de salida '{salida_dir}': {e}")
        sys.exit(1)

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

    # ── Modo --archivos ───────────────────────────────────────────────────────
    if args["archivos"] is not None:
        archivos_resueltos = []
        for ruta_str in args["archivos"]:
            candidato = (raiz / ruta_str).resolve()
            if not candidato.exists():
                print(f"[AVISO]  Archivo no encontrado, se omite: {ruta_str}")
                continue
            if not candidato.is_file():
                print(f"[AVISO]  No es un archivo, se omite: {ruta_str}")
                continue
            archivos_resueltos.append(candidato)

        if not archivos_resueltos:
            print("[ERROR]  Ninguno de los archivos indicados con --archivos existe.")
            sys.exit(1)

        archivos_resueltos = ordenar_archivos(archivos_resueltos)

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
        return

    todos = recolectar_archivos(
        raiz, config,
        omitir_autogenerados=config.get("omitir_autogenerados", False),
        limite_lineas=config.get("limite_lineas"),
        verbose=args["verbose"],
    )

    if not todos:
        print("[AVISO]  No se encontraron archivos con las extensiones configuradas.")
        return

    # ── Modo --preview ────────────────────────────────────────────────────────
    if args["preview"]:
        mostrar_preview(todos, raiz, config, modelo)
        return

    # ── Modo --stats ──────────────────────────────────────────────────────────
    if args["stats"]:
        mostrar_stats(todos, raiz, modelo)
        return

    # ── Modo --co ─────────────────────────────────────────────────────────────
    if args["co"]:
        commits = obtener_ultimos_commits(raiz)
        if con_objetivo:
            nombre_sal = objetivo_a_slug(config["objetivo"], "mapa")
            salida_co  = salida_dir / nombre_sal
            est = escribir_mapa_ia(salida_co, todos, raiz, config, commits, modelo)
            _log_ok("Mapa IA           ", salida_co, len(todos), est)
            print(f"         (estructura sin código, formato IA)")
        else:
            salida_co = salida_dir / config["nombre_salida_co"]
            est = escribir_context_only(salida_co, todos, raiz, config, commits, modelo)
            _log_ok("Mapa de contexto  ", salida_co, len(todos), est)
            print(f"         (sin código fuente)")
            print(f"         Este archivo NO contiene código fuente.")
            print(f"         Úsalo para decidir qué archivos pasarle a la IA.")
            print(f"         Luego ejecuta el script indicando solo esas carpetas en 'incluir_solo'")
            print(f"         o usa --solo-cambios si trabajas con git.")
        return

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
        )
        _log_ok("Contexto IA       ", salida_ia, len(todos), est)
        return

    # ── Contexto completo (modo estándar) ─────────────────────────────────────
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

    # ── Cambios git ───────────────────────────────────────────────────────────
    modificados_raw = obtener_archivos_modificados(raiz)
    if modificados_raw is None:
        return
    if not modificados_raw:
        print("[OK]     Sin cambios en git — no se genera archivo de cambios.")
        return

    modificados = filtrar_por_config(
        modificados_raw, raiz, config,
        omitir_autogenerados=config.get("omitir_autogenerados", False),
        limite_lineas=config.get("limite_lineas"),
        verbose=args["verbose"],
    )
    if not modificados:
        print("[OK]     Los archivos modificados no coinciden con las extensiones/carpetas configuradas.")
        return

    commits       = obtener_ultimos_commits(raiz)
    lista_nombres = ", ".join(str(m.relative_to(raiz)) for m in modificados)
    nota          = f"Archivos modificados: {lista_nombres}"
    if commits:
        nota += f" | Commits recientes: {' / '.join(commits[:3])}"

    salida_cambios = salida_dir / config["nombre_salida_cambios"]
    est = escribir_archivo(
        salida_path=salida_cambios,
        archivos=modificados,
        raiz=raiz,
        config=config,
        titulo="ARCHIVOS MODIFICADOS DESDE EL ÚLTIMO PULL",
        nota_extra=nota,
        modelo=modelo,
    )
    _log_ok("Cambios git       ", salida_cambios, len(modificados), est)


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    args = parsear_args(sys.argv[1:])
    unificar(args)