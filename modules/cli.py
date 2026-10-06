"""
modules/cli.py
Parseo de argumentos de línea de comandos.

USO:
  python code_context.py [carpeta] [opciones]

OPCIONES CLI:
  --init                    Genera .codigo_config.json de ejemplo con comentarios
  --init --limpio           Genera .codigo_config.json mínimo, sin comentarios
  --co                      Solo contexto: árbol + dependencias + fichas, sin código
                            (formato texto plano, optimizado para IAs)
  --md                      Genera un archivo Markdown amigable para humanos.
                            Incluye árbol, fichas, dependencias, commits y tokens.
                            Sin código fuente. Ideal para GitHub, Obsidian o Notion.
  --latex                   Genera un archivo LaTeX amigable para humanos.
                            Portada automática, cajas tcolorbox, tablas booktabs.
                            Sin código fuente. Intenta compilar a PDF automáticamente
                            con pdflatex. Si no está disponible, guarda el .tex y
                            muestra instrucciones de instalación en la terminal.
  --solo-cambios            Solo genera el archivo de cambios git
  --limite N                Omite archivos con más de N líneas (default: sin límite)
  --sin-minimos             Omite lockfiles, *.min.js, migraciones auto-numeradas, etc.
  --verbose                 Muestra qué archivos se omiten y por qué
  --preview                 Muestra qué archivos se incluirían, sin generar nada
  --stats                   Muestra estimación de tokens sin generar archivos
  --agent-map "texto"       Alias para agentes: JSON + stdout + --co + objetivo
  --agent-files "texto" f... Alias para agentes: JSON + stdout + objetivo + archivos
  --impact archivo          Muestra dependencias e impacto de un archivo
  doctor, --doctor          Diagnostica instalación, PATH, skill y escritura
  --version                 Muestra la versión instalada
  --ignorar-extra f1 f2 ... Agrega carpetas/archivos a ignorar sin tocar el config
  --objetivo "texto"        Define el objetivo de la sesión. Genera un archivo
                            optimizado para IA con nombre ia_[slug]_contexto.txt
  --archivos f1 f2 ...      Incluye solo los archivos indicados (rutas relativas).
                            Acepta directorios: se expanden a sus archivos
                            incluibles según la configuración.
                            Con --objetivo genera ia_[slug]_solicitado.txt
  --presupuesto N           Recorta la lista (ya ordenada por prioridad) para que
                            el contexto generado quepa en ~N tokens. Los archivos
                            fuera de presupuesto aparecen en dropped del JSON.
                            Aplica a --co, --objetivo y modo estándar.
  --continua                Segunda vuelta: omite <context_metadata>, <file_tree> e
                            <file_index> en ia_[slug]_solicitado.txt (la IA ya los vio).
                            Solo válido con --objetivo + --archivos.
  --modelo NOMBRE           Modelo/agente destino para estimar tokens y costo.
                            Opciones: claude, gpt-4, gpt-4o, gpt-3.5, gemini,
                                      gemini-pro, llama, mistral, deepseek, default
                            Default: "default" (estimación genérica, sin costo)
  --comprimir [leve|medio|agresivo]
                            Elimina comentarios y docstrings antes de escribir los archivos.
                            Sin argumento usa nivel "medio". Niveles:
                              leve      → solo elimina comentarios de línea/bloque
                              medio     → también docstrings de módulo (default)
                              agresivo  → todos los docstrings + colapsa líneas vacías
                            Soporta .py .js .ts .jsx .tsx .html .css
                            Requiere modules/compresor.py.
  --json                    Modo máquina. Los logs van a stderr y el stdout recibe
                            UNA sola línea JSON con el resultado:
                            {ok, mode, output_path, files, included, tokens, bytes,
                             model, window_pct, cost_usd, warnings, ...}
                            Errores: {"ok": false, "error": ..., "kind": ...}.
                            kind: error (exit 1) | usage (exit 2) | limit (exit 3).
  --stdout                  Devuelve el contenido generado directamente por stdout
                            (sin escribir archivo) y descarta los logs humanos.
                            Si supera --max-stdout sale con código 3.
                            Combinado con --json, el contenido va en el campo "content".
                            Solo aplica con --co, --objetivo, --archivos o --solo-cambios.
  --max-stdout N            Tope de tokens para --stdout (default: 15000, 0 = sin límite).
  --sin-instrucciones       Omite el bloque <response_instructions> de los archivos ia_*.
                            Pensado para agentes que ya conocen el protocolo (skill).
  --ayuda                   Muestra esta ayuda
"""

import sys

from modules.ai import MODELOS_TOKENS, MODELOS_VALIDOS
from modules.output import console


def parsear_args(argv: list[str]) -> dict:
    args = {
        "carpeta":       ".",
        "init":          False,
        "init_limpio":   False,
        "co":            False,
        "md":            False,
        "latex":         False,
        "solo_cambios":  False,
        "limite":        None,
        "sin_minimos":   False,
        "verbose":       False,
        "preview":       False,
        "stats":         False,
        "agent_map":     False,
        "agent_files":   False,
        "impact":        None,
        "doctor":        False,
        "version":       False,
        "ignorar_extra": [],
        "objetivo":      None,
        "archivos":      None,
        "modelo":        None,
        "continua":      False,
        "comprimir":     None,
        "presupuesto":   None,
        "json":          False,
        "stdout":        False,
        "sin_instrucciones": False,
        "max_stdout":    15000,
    }

    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("--ayuda", "--help", "-h"):
            if console.MODO_JSON:
                console.emitir_json({"ok": True, "mode": "ayuda", "help": __doc__})
            print(__doc__)
            sys.exit(0)
        elif tok == "--init":
            args["init"] = True
        elif tok == "--limpio":
            args["init_limpio"] = True
        elif tok == "--co":
            args["co"] = True
        elif tok == "--md":
            args["md"] = True
        elif tok == "--latex":
            args["latex"] = True
        elif tok == "--solo-cambios":
            args["solo_cambios"] = True
        elif tok == "--sin-minimos":
            args["sin_minimos"] = True
        elif tok == "--verbose":
            args["verbose"] = True
        elif tok == "--preview":
            args["preview"] = True
        elif tok == "--stats":
            args["stats"] = True
        elif tok in ("doctor", "--doctor"):
            args["doctor"] = True
        elif tok == "--version":
            args["version"] = True
        elif tok == "--agent-map":
            args["agent_map"] = True
            args["co"] = True
            args["json"] = True
            args["stdout"] = True
            args["sin_instrucciones"] = True
            args["max_stdout"] = max(args["max_stdout"], 100000)
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                i += 1
                args["objetivo"] = argv[i]
        elif tok == "--agent-files":
            args["agent_files"] = True
            args["json"] = True
            args["stdout"] = True
            args["sin_instrucciones"] = True
            args["max_stdout"] = max(args["max_stdout"], 100000)
            i += 1
            if i >= len(argv) or argv[i].startswith("--"):
                console.fallar('--agent-files requiere un objetivo. Ej: --agent-files "tarea" src/app.py', 2)
            args["objetivo"] = argv[i]
            i += 1
            archivos_lista = []
            while i < len(argv) and not argv[i].startswith("--"):
                archivos_lista.append(argv[i])
                i += 1
            if not archivos_lista:
                console.fallar("--agent-files requiere al menos un archivo o directorio.", 2)
            args["archivos"] = archivos_lista
            continue
        elif tok == "--impact":
            i += 1
            if i >= len(argv) or argv[i].startswith("--"):
                console.fallar("--impact requiere una ruta de archivo.", 2)
            args["impact"] = argv[i]
        elif tok == "--continua":
            args["continua"] = True
        elif tok == "--json":
            args["json"] = True
        elif tok == "--stdout":
            args["stdout"] = True
        elif tok == "--sin-instrucciones":
            args["sin_instrucciones"] = True
        elif tok == "--max-stdout":
            i += 1
            if i >= len(argv):
                console.fallar("--max-stdout requiere un número. Ej: --max-stdout 15000 (0 = sin límite)", 2)
            try:
                tope = int(argv[i])
            except ValueError:
                console.fallar(f"--max-stdout necesita un entero, recibió: '{argv[i]}'", 2)
            if tope < 0:
                console.fallar("--max-stdout no puede ser negativo.", 2)
            args["max_stdout"] = tope
        elif tok == "--limite":
            i += 1
            if i >= len(argv):
                console.fallar("--limite requiere un número. Ej: --limite 500", 2)
            try:
                args["limite"] = int(argv[i])
            except ValueError:
                console.fallar(f"--limite necesita un entero, recibió: '{argv[i]}'", 2)
        elif tok == "--presupuesto":
            i += 1
            if i >= len(argv):
                console.fallar("--presupuesto requiere un número de tokens. Ej: --presupuesto 30000", 2)
            try:
                pres = int(argv[i])
            except ValueError:
                console.fallar(f"--presupuesto necesita un entero, recibió: '{argv[i]}'", 2)
            if pres <= 0:
                console.fallar("--presupuesto debe ser mayor a 0.", 2)
            args["presupuesto"] = pres
        elif tok == "--objetivo":
            i += 1
            if i >= len(argv):
                console.fallar('--objetivo requiere un texto. Ej: --objetivo "Agregar JWT"', 2)
            args["objetivo"] = argv[i]
        elif tok == "--modelo":
            i += 1
            if i >= len(argv):
                console.fallar(f"--modelo requiere un nombre. Opciones: {', '.join(MODELOS_VALIDOS)}", 2)
            m = argv[i].lower()
            if m not in MODELOS_TOKENS:
                console.fallar(f"Modelo '{argv[i]}' no reconocido. Opciones: {', '.join(MODELOS_VALIDOS)}", 2)
            args["modelo"] = m
        elif tok == "--ignorar-extra":
            i += 1
            extras = []
            while i < len(argv) and not argv[i].startswith("--"):
                extras.append(argv[i])
                i += 1
            if not extras:
                console.fallar("--ignorar-extra requiere al menos un nombre. Ej: --ignorar-extra tmp logs", 2)
            args["ignorar_extra"] = extras
            continue
        elif tok == "--archivos":
            i += 1
            archivos_lista = []
            while i < len(argv) and not argv[i].startswith("--"):
                archivos_lista.append(argv[i])
                i += 1
            if not archivos_lista:
                console.fallar("--archivos requiere al menos un archivo.", 2)
            args["archivos"] = archivos_lista
            continue
        elif tok == "--comprimir":
            i += 1
            niveles_validos = ["leve", "medio", "agresivo"]
            if i >= len(argv) or argv[i].startswith("--"):
                args["comprimir"] = "medio"
                continue
            nivel = argv[i].lower()
            if nivel not in niveles_validos:
                console.fallar(f"--comprimir acepta: {', '.join(niveles_validos)}", 2)
            args["comprimir"] = nivel
        elif not tok.startswith("--"):
            args["carpeta"] = tok
        else:
            print(f"[AVISO] Argumento desconocido: '{tok}'. Usa --ayuda para ver opciones.")
        i += 1

    if args["agent_map"] and not args["objetivo"]:
        console.fallar('--agent-map requiere un objetivo. Ej: --agent-map "entender este repo"', 2)

    return args
