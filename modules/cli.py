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
  --ignorar-extra f1 f2 ... Agrega carpetas/archivos a ignorar sin tocar el config
  --objetivo "texto"        Define el objetivo de la sesión. Genera un archivo
                            optimizado para IA con nombre ia_[slug]_contexto.txt
  --archivos f1 f2 ...      Incluye solo los archivos indicados (rutas relativas).
                            Con --objetivo genera ia_[slug]_solicitado.txt
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
  --ayuda                   Muestra esta ayuda
"""

import sys

from modules.ai import MODELOS_TOKENS, MODELOS_VALIDOS


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
        "ignorar_extra": [],
        "objetivo":      None,
        "archivos":      None,
        "modelo":        None,
        "continua":      False,
        "comprimir":     None,
    }

    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("--ayuda", "--help", "-h"):
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
        elif tok == "--continua":
            args["continua"] = True
        elif tok == "--limite":
            i += 1
            if i >= len(argv):
                print("[ERROR] --limite requiere un número. Ej: --limite 500")
                sys.exit(1)
            try:
                args["limite"] = int(argv[i])
            except ValueError:
                print(f"[ERROR] --limite necesita un entero, recibió: '{argv[i]}'")
                sys.exit(1)
        elif tok == "--objetivo":
            i += 1
            if i >= len(argv):
                print("[ERROR] --objetivo requiere un texto. Ej: --objetivo \"Agregar JWT\"")
                sys.exit(1)
            args["objetivo"] = argv[i]
        elif tok == "--modelo":
            i += 1
            if i >= len(argv):
                print(f"[ERROR] --modelo requiere un nombre. Opciones: {', '.join(MODELOS_VALIDOS)}")
                sys.exit(1)
            m = argv[i].lower()
            if m not in MODELOS_TOKENS:
                print(f"[ERROR] Modelo '{argv[i]}' no reconocido.")
                print(f"        Opciones: {', '.join(MODELOS_VALIDOS)}")
                sys.exit(1)
            args["modelo"] = m
        elif tok == "--ignorar-extra":
            i += 1
            extras = []
            while i < len(argv) and not argv[i].startswith("--"):
                extras.append(argv[i])
                i += 1
            if not extras:
                print("[ERROR] --ignorar-extra requiere al menos un nombre. Ej: --ignorar-extra tmp logs")
                sys.exit(1)
            args["ignorar_extra"] = extras
            continue
        elif tok == "--archivos":
            i += 1
            archivos_lista = []
            while i < len(argv) and not argv[i].startswith("--"):
                archivos_lista.append(argv[i])
                i += 1
            if not archivos_lista:
                print("[ERROR] --archivos requiere al menos un archivo.")
                sys.exit(1)
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
                print(f"[ERROR] --comprimir acepta: {', '.join(niveles_validos)}")
                sys.exit(1)
            args["comprimir"] = nivel
        elif not tok.startswith("--"):
            args["carpeta"] = tok
        else:
            print(f"[AVISO] Argumento desconocido: '{tok}'. Usa --ayuda para ver opciones.")
        i += 1

    return args 