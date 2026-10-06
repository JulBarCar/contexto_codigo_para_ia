# contexto

`contexto` es una CLI Python para empaquetar un proyecto en contexto útil para IAs y agentes. Genera mapas estructurales baratos, contextos XML optimizados, salidas JSON para herramientas, estimaciones de tokens y selecciones puntuales de archivos.

Funciona sin dependencias externas: solo Python 3.10+.

## Para Qué Sirve

- Entender un repo sin abrir archivo por archivo.
- Darle a una IA un mapa del proyecto antes de pedir código completo.
- Ahorrar tokens usando un flujo de dos pasos: mapa primero, archivos puntuales después.
- Integrarse con opencode mediante la skill incluida en `skills/contexto/SKILL.md`.
- Instalar el comando global `contexto` para que cualquier agente pueda usarlo desde cualquier repo.

## Instalación Rápida

Cloná o descargá este repo y ejecutá el instalador de tu sistema desde la raíz del proyecto.

Windows:

```bat
setup_windows.bat
```

Linux/macOS:

```bash
bash setup_linux.sh
```

Los instaladores hacen tres cosas:

- Instalan la CLI como comando global `contexto`.
- Copian `code_context.py` y `modules/` al directorio de instalación.
- Instalan la skill de opencode en `~/.config/opencode/skills/contexto/SKILL.md`.

Verificación:

```bash
contexto --ayuda
```

En Windows, si acabás de instalar por primera vez y el comando no aparece, cerrá y abrí la terminal para recargar el PATH.

## Uso Básico

```bash
contexto .
contexto . --co
contexto . --objetivo "Agregar autenticación JWT"
contexto . --solo-cambios
contexto . --preview --modelo claude
```

Por defecto las salidas se guardan en `.codigo_completo/` dentro del proyecto analizado.

## Flujo Recomendado Para Opencode

Después de instalar, opencode puede cargar la skill `contexto`. La skill enseña a los agentes a usar la CLI de forma económica.

Primer paso: mapa estructural sin código, barato y apto para agentes.

```bash
contexto . --json --stdout --max-stdout 100000 \
  --co --objetivo "<tarea>" --sin-instrucciones
```

El agente lee el campo JSON `content`, que contiene:

- `<file_tree>` con la estructura del repo.
- `<file_index>` con ruta, líneas, extensión, tokens estimados, símbolos e imports.
- `depends_on` cuando se pudieron resolver dependencias internas.
- `<dependency_graph>` con relaciones internas entre archivos.

Segundo paso: pedir solo los archivos necesarios.

```bash
contexto . --json --stdout --max-stdout 100000 \
  --objetivo "<tarea>" --archivos src/app.py src/auth.py --sin-instrucciones
```

Si el agente ya recibió el mapa en una vuelta anterior, puede usar `--continua` para no repetir metadatos.

```bash
contexto . --json --stdout --max-stdout 100000 \
  --objetivo "<tarea>" --archivos src/app.py src/auth.py --continua --sin-instrucciones
```

Más detalles para agentes y configuración de opencode: `docs/OPENCODE.md`.

## Archivos Generados

| Archivo | Cuándo | Contenido |
| --- | --- | --- |
| `contexto_codigo.txt` | `contexto .` | Todo el código incluido por configuración |
| `cambios_git.txt` | repo git con cambios | Archivos modificados filtrados |
| `mapa_contexto.txt` | `--co` | Árbol, fichas por archivo y grafo, sin código |
| `ia_[objetivo]_contexto.txt` | `--objetivo` | Contexto XML con código |
| `ia_[objetivo]_mapa.txt` | `--co --objetivo` | Mapa XML para IA, sin código |
| `ia_[objetivo]_solicitado.txt` | `--objetivo --archivos` | Solo archivos pedidos |
| `contexto_solicitado.txt` | `--archivos` sin objetivo | Selección puntual en formato estándar |

## Referencia De Comandos

| Flag | Descripción |
| --- | --- |
| `--co` | Genera mapa estructural sin código |
| `--objetivo "texto"` | Activa formato IA XML y nombra la salida según la tarea |
| `--archivos f1 dir2` | Incluye solo archivos o directorios indicados |
| `--continua` | Omite metadatos repetidos en segunda vuelta con `--objetivo --archivos` |
| `--json` | Devuelve una línea JSON apta para herramientas |
| `--stdout` | Devuelve contenido por stdout; con `--json`, va en `content` |
| `--max-stdout N` | Límite de tokens para stdout; default `15000`, `0` sin límite |
| `--sin-instrucciones` | Omite `<response_instructions>` en salidas `ia_*` |
| `--presupuesto N` | Recorta la lista de archivos para entrar en ~N tokens |
| `--preview` | Muestra qué se incluiría sin generar archivos |
| `--stats` | Solo estima tokens |
| `--modelo NOMBRE` | Modelo para estimación: `claude`, `gpt-4o`, `gemini`, `default`, etc. |
| `--init` | Genera `.codigo_config.json` de ejemplo |
| `--init --limpio` | Genera config mínima |
| `--solo-cambios` | Genera solo contexto de cambios git |
| `--limite N` | Omite archivos con más de N líneas |
| `--sin-minimos` | Omite minificados, lockfiles y otros generados |
| `--comprimir [leve|medio|agresivo]` | Elimina comentarios/docstrings en lenguajes soportados |

## Configuración Por Proyecto

Generar config:

```bash
contexto . --init
```

Ejemplo mínimo:

```json
{
  "descripcion": "API REST en FastAPI para inventario.",
  "extensiones": [".py", ".js", ".ts"],
  "ignorar": ["node_modules", ".git", "dist"],
  "incluir_solo": ["src", "tests"],
  "limite_lineas": 500,
  "omitir_autogenerados": true,
  "carpeta_salida": ".codigo_completo",
  "modelo": "default"
}
```

La configuración por defecto incluye extensiones Web y Python. Para Go, Rust, C#, Java u otros lenguajes soportados, agregá las extensiones correspondientes en `.codigo_config.json`.

## Lenguajes Soportados

Extracción de imports y grafo:

- Python, JavaScript, TypeScript, JSX, TSX, Vue, Svelte.
- Go, C/C++, C#, Java, Kotlin, Scala, Rust, PHP, Ruby, Swift, Dart, R y Shell.

Compresión de código:

- Python.
- JavaScript, TypeScript, JSX, TSX.
- HTML y CSS.

Para extensiones sin strategy dedicada, la herramienta intenta un fallback best-effort fusionando estrategias conocidas.

## Estructura Del Repo

```text
code_context.py              # entrypoint y orquestador principal
modules/                     # implementación modular de la CLI
modules/cli.py               # parser de argumentos
modules/config/              # defaults y loader de .codigo_config.json
modules/filesystem/          # filtros, recolección y orden de archivos
modules/imports/             # extracción de imports y grafo interno
modules/output/              # writers, JSON/stdout, preview, markdown, latex
skills/contexto/SKILL.md     # skill instalable para opencode
docs/OPENCODE.md             # guía de integración con opencode
setup_windows.bat            # instalador Windows
setup_linux.sh               # instalador Linux/macOS
AGENTS.md                    # guía rápida para agentes trabajando en este repo
```

## Desarrollo Y Verificación

Compilar archivos principales:

```bash
python -m py_compile code_context.py modules/aliases/resolver.py modules/imports/core.py modules/output/writers.py
```

Probar el mapa para agentes:

```bash
python code_context.py . --json --stdout --max-stdout 100000 \
  --co --objetivo "verificar mapa" --sin-instrucciones
```

Instalar localmente después de cambios:

```bat
setup_windows.bat --no-pause
```

```bash
bash setup_linux.sh
```

## Notas Para Agentes

- Preferir `--json --stdout` cuando la salida va a ser consumida por una herramienta.
- Empezar con `--co --objetivo` antes de pedir código completo.
- Usar `--archivos` con rutas específicas para evitar gastar tokens innecesarios.
- Evitar presupuestos demasiado chicos en el primer mapa porque pueden eliminar archivos que hacen falta para resolver el grafo.
- Si `contexto` no está en PATH, usar `python code_context.py` desde la raíz de este repo o reinstalar con el setup correspondiente.
