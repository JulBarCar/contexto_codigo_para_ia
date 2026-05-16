# code_context.py

Script de Python que **unifica todo el código de tu proyecto en un único `.txt`** listo para pasarle a una IA. Sin dependencias externas, solo Python 3.10+.

Hacés `contexto .` en la raíz del proyecto y te genera un archivo con el árbol de archivos + el contenido de cada uno, filtrando automáticamente `node_modules`, `.git`, lockfiles y demás ruido. También detecta cambios de git, genera contextos optimizados por objetivo y estima tokens y costo por modelo.

---

## ⚡ Instalación

Descargá los tres archivos (`code_context.py`, `setup_windows.bat`, `setup_linux.sh`) en cualquier carpeta y ejecutá el instalador de tu sistema. Instala el comando `contexto` globalmente para que funcione desde cualquier carpeta.

**🪟 Windows** — doble clic en `setup_windows.bat`

- Crea `%USERPROFILE%\code-context\` y agrega esa ruta al PATH del usuario
- Cerrá y volvé a abrir la terminal

**🐧 Linux / Mac** — desde la terminal en esa carpeta(deveria de poder instalarse con doble click tambien):

```bash
bash setup_linux.sh
```

- Copia el script a `~/.local/bin/` y agrega esa ruta al PATH en `.bashrc` si no estaba
- Reiniciá la terminal (o ejecutá `source ~/.bashrc`)

**Verificar que quedó instalado:**

```bash
contexto --ayuda
```

---

## 🚀 Uso básico

```bash
contexto .                            # contexto completo del proyecto actual
contexto ../mi-backend                # carpeta específica
contexto . --objetivo "Agregar JWT"   # contexto optimizado para una tarea
contexto . --solo-cambios             # solo archivos modificados en git
contexto . --preview --modelo claude  # ver qué incluiría + estimación de tokens
```

El resultado queda en `.codigo_completo/` dentro del proyecto.

---

## ¿Qué genera?

| Archivo                        | Cuándo                              | Contenido                                           |
| ------------------------------ | ----------------------------------- | --------------------------------------------------- |
| `contexto_codigo.txt`          | Siempre                             | Todo el código del proyecto                         |
| `cambios_git.txt`              | Si es repo git                      | Solo archivos modificados desde el último pull      |
| `mapa_contexto.txt`            | Con `--co`                          | Árbol + dependencias + fichas, sin código           |
| `ia_[objetivo]_contexto.txt`   | Con `--objetivo`                    | Contexto completo optimizado para IA, formato XML   |
| `ia_[objetivo]_mapa.txt`       | Con `--co` + `--objetivo`           | Mapa estructural (sin código) optimizado para IA    |
| `ia_[objetivo]_solicitado.txt` | Con `--objetivo` + `--archivos`     | Archivos específicos pedidos por la IA, formato XML |
| `contexto_solicitado.txt`      | Con `--archivos` (sin `--objetivo`) | Solo los archivos indicados, formato estándar       |

---

## 🧠 Uso

### Sintaxis general

```bash
contexto [carpeta] [opciones]
```

Si no se indica carpeta, usa la carpeta actual (`.`).

### Ejemplos rápidos

```bash
contexto                             # carpeta actual, modo completo
contexto ../mi-backend               # carpeta específica
contexto . --co                      # mapa de contexto sin código
contexto . --init                    # genera config con comentarios
contexto . --init --limpio           # genera config mínimo, sin comentarios
contexto . --solo-cambios            # solo archivos modificados en git
contexto . --sin-minimos             # omite lockfiles y archivos auto-generados
contexto . --limite 300              # omite archivos de más de 300 líneas
contexto . --verbose                 # muestra qué archivos se omiten y por qué
contexto . --preview                 # muestra qué se incluiría, sin generar nada
contexto . --stats --modelo claude   # estimación de tokens en consola
contexto . --ignorar-extra tmp logs  # ignorar carpetas extra sin tocar config
```

---

## 📋 Referencia de argumentos

| Argumento                   | Descripción                                                                             |
| --------------------------- | --------------------------------------------------------------------------------------- |
| `--init`                    | Genera un `.codigo_config.json` de ejemplo con comentarios                              |
| `--init --limpio`           | Genera un `.codigo_config.json` mínimo, solo claves y valores                           |
| `--co`                      | Modo "context only": árbol + dependencias + fichas, sin código                          |
| `--solo-cambios`            | Solo genera el archivo de cambios git                                                   |
| `--limite N`                | Omite archivos con más de N líneas                                                      |
| `--sin-minimos`             | Omite lockfiles, `.min.js`, y otros auto-generados                                      |
| `--verbose`                 | Muestra detalle de archivos omitidos                                                    |
| `--preview`                 | Muestra qué archivos se incluirían, sin escribir nada                                   |
| `--stats`                   | Muestra estimación de tokens en consola, sin generar archivos                           |
| `--ignorar-extra f1 f2 ...` | Agrega carpetas/archivos a ignorar para esta ejecución, sin tocar el config             |
| `--objetivo "texto"`        | Genera `ia_[slug]_contexto.txt` optimizado para IA con estructura XML                   |
| `--archivos f1 f2 ...`      | Incluye solo los archivos indicados. Con `--objetivo` genera `ia_[slug]_solicitado.txt` |
| `--continua`                | Segunda vuelta: omite metadatos ya enviados en `ia_[slug]_solicitado.txt`. Ver abajo.   |
| `--modelo NOMBRE`           | Modelo destino para estimar tokens. Ver opciones abajo.                                 |
| `--ayuda`                   | Muestra ayuda                                                                           |

### Modelos disponibles para `--modelo`

`claude`, `gpt-4`, `gpt-4o`, `gpt-3.5`, `gemini`, `gemini-pro`, `llama`, `mistral`, `deepseek`, `default`

---

## 🎯 Workflow con `--objetivo` y `--archivos`

Este es el workflow principal para trabajar con la IA de forma iterativa y eficiente.

### Paso 1 — Generás el contexto con tu objetivo

```bash
contexto . --objetivo "Agregar autenticación JWT con refresh tokens"
```

Genera `ia_agregar_autenticacion_jwt_con_refresh_tokens_contexto.txt` con:

- Estructura XML optimizada para LLMs
- Tu objetivo en un bloque `<task>`
- Un `<file_index>` compacto con ruta, líneas, extensión e imports de cada archivo
- El código en bloques `<file path="...">` dentro de `<codebase>`
- Instrucciones para que la IA responda con un comando listo para copiar

### Paso 2 — Pasás el archivo a la IA

La IA recibirá el contexto completo y en su respuesta te dará un comando listo:

```
<follow_up_command>
contexto . --objetivo "Agregar autenticación JWT con refresh tokens" --archivos src/auth.py src/models/user.py
</follow_up_command>
```

### Paso 3 — Ejecutás el comando que te dio la IA

```bash
contexto . --objetivo "Agregar autenticación JWT con refresh tokens" --archivos src/auth.py src/models/user.py
```

Genera `ia_agregar_autenticacion_jwt_con_refresh_tokens_solicitado.txt` con exactamente los archivos que pidió.

### Paso 4 — Pasás ese archivo a la IA

Ahora la IA tiene exactamente el contexto que necesita. Sin tokens desperdiciados.

---

## ⏭️ `--continua` — Segunda vuelta sin repetir contexto

Cuando usás el flujo de dos pasos (`--co --objetivo` → `--objetivo --archivos`), el archivo de la segunda vuelta normalmente repetiría `<context_metadata>`, `<file_tree>` y `<file_index>` que la IA ya vio en el primero. Son tokens desperdiciados.

`--continua` le indica al script que omita esos bloques y genere solo lo nuevo:

```bash
# 1er envío: mapa completo (la IA decide qué archivos necesita)
contexto . --co --objetivo "Agregar paginación a la API"

# 2do envío: solo el código pedido, sin repetir metadatos
contexto . --objetivo "Agregar paginación a la API" --archivos src/api.py src/models.py --continua
```

El archivo resultante contiene únicamente `<task>`, `<codebase>` y `<response_instructions>`. La IA ya tiene el resto del contexto de la vuelta anterior.

> Solo tiene efecto combinado con `--objetivo` + `--archivos`. En otros modos se ignora.

---

## 🔍 `--preview` — Ver antes de generar

Muestra qué archivos se incluirían y una estimación de tokens, sin escribir ningún archivo.

```bash
contexto . --preview
contexto . --preview --modelo claude --sin-minimos --limite 400
```

Útil para calibrar la configuración antes de generar el contexto final. Muestra:

- Lista de archivos con su cantidad de líneas
- Resumen por extensión
- Estimación de tokens, costo y porcentaje del context window del modelo

---

## 📊 `--stats` — Solo estimación de tokens

Muestra la estimación de tokens en consola sin generar ningún archivo.

```bash
contexto . --stats --modelo claude
```

Útil para decidir si necesitás filtrar el proyecto antes de generar.

---

## 🚫 `--ignorar-extra` — Ignorar temporalmente sin tocar el config

```bash
contexto . --ignorar-extra tmp logs fixtures
```

Agrega carpetas o archivos a la lista de ignorados solo para esa ejecución. Útil cuando tenés carpetas temporales que no querés commitear al config.

---

## 🗺️ Modo `--co` (Context Only)

Genera un archivo liviano sin código que incluye:

- Árbol de archivos del proyecto
- Ficha por archivo (líneas, extensión, qué importa)
- Grafo de dependencias internas
- Últimos commits de git

Las instrucciones de uso se imprimen en consola, no en el archivo de salida, para mantener `mapa_contexto.txt` limpio.

Modos:

- `--co` solo → `mapa_contexto.txt` (para el humano — explorar antes de decidir)
- `--co --objetivo "..."` → `ia_[slug]_mapa.txt` (para la IA — que ella decida qué archivos necesita)

Flujo recomendado (manual):

```bash
# 1. Ver el mapa vos mismo
contexto . --co

# 2. Decidir qué incluir y configurar en .codigo_config.json

# 3. Generar el contexto final
contexto . --objetivo "mi tarea"
```

Flujo recomendado (delegado a la IA):

```bash
# 1. Generar el mapa para la IA
contexto . --co --objetivo "Agregar paginación a la API"

# 2. Pasar ia_agregar_paginacion_a_la_api_mapa.txt a la IA
# La IA analiza la estructura y devuelve un follow_up_command

# 3. Ejecutar ese comando con --continua (la IA ya vio los metadatos)
contexto . --objetivo "Agregar paginación a la API" --archivos src/api.py --continua
```

---

## 📈 Estimación de tokens

El script estima tokens, costo y porcentaje del context window para cada archivo generado. La estimación siempre aparece en la consola al terminar:

```
[OK]     Contexto completo  →  contexto_codigo.txt  (12 archivos)  [~18.500 tokens  |  ~$0.0555 USD  |  9% del context window ✓]
```

Los archivos destinados al humano (`contexto_codigo.txt`, `mapa_contexto.txt`) también incluyen el bloque de estimación al final del archivo. Los archivos destinados a la IA (`ia_*`) **no** lo incluyen, para mantener el XML limpio.

Si el contexto generado supera el 100% del context window del modelo, se muestra un aviso adicional:

```
[AVISO]  El contexto excede el context window del modelo (143%).
         Considerá usar --limite, --sin-minimos o 'incluir_solo' en el config.
```

---

## 🧾 Archivo de configuración

```bash
contexto . --init          # con comentarios explicativos
contexto . --init --limpio # solo claves y valores
```

### Ejemplo completo

```json
{
  "descripcion": "API REST en FastAPI para gestión de inventario.",
  "extensiones": [".py", ".js", ".ts"],
  "ignorar": ["node_modules", ".git", "dist"],
  "incluir_solo": ["src", "api", "components"],
  "limite_lineas": 500,
  "omitir_autogenerados": true,
  "carpeta_salida": "../contextos",
  "nombre_salida": "contexto_codigo.txt",
  "nombre_salida_cambios": "cambios_git.txt",
  "nombre_salida_co": "mapa_contexto.txt",
  "modelo": "claude"
}
```

### Opciones explicadas

| Clave                   | Descripción                                                                |
| ----------------------- | -------------------------------------------------------------------------- |
| `descripcion`           | Una oración del proyecto. Aparece en los metadatos del archivo generado.   |
| `extensiones`           | Extensiones a incluir. Default: `.py .js .ts .jsx .tsx .html .css`         |
| `ignorar`               | Carpetas/archivos a excluir. Default: `node_modules .git __pycache__` etc. |
| `incluir_solo`          | Si se define, solo se incluyen estas carpetas raíz.                        |
| `limite_lineas`         | Omite archivos con más líneas que este valor. `null` = sin límite.         |
| `omitir_autogenerados`  | Omite lockfiles, minificados, protobuf, migraciones auto-numeradas.        |
| `carpeta_salida`        | Dónde guardar los archivos. Default: `.codigo_completo/`                   |
| `nombre_salida`         | Nombre del archivo de contexto completo.                                   |
| `nombre_salida_cambios` | Nombre del archivo de cambios git.                                         |
| `nombre_salida_co`      | Nombre del archivo de mapa de contexto.                                    |
| `modelo`                | Modelo para estimación de tokens. La CLI tiene prioridad.                  |

---

## 🔄 Integración con Git

Si el proyecto es un repositorio git, el script genera automáticamente `cambios_git.txt` con los archivos que cambiaron. También incluye los últimos commits como contexto en el encabezado.

Los commits se decodifican correctamente incluso en Windows donde git puede devolver texto con encoding incorrecto.

---

## 📂 Orden de archivos

Los archivos se ordenan para que la IA construya el modelo mental del proyecto de arriba hacia abajo:

1. Archivos en la raíz del proyecto primero
2. Dentro de cada nivel, archivos clave van primero: `main`, `index`, `app`, `server`, `__init__`, `config`, `settings`, etc.
3. Luego el resto, ordenado alfabéticamente

---

## 🗂️ Estructura XML de los archivos para IA

Los archivos `ia_*` usan una estructura XML pensada para ser parseada fácilmente por modelos de lenguaje:

```
<context_metadata>        ← metadatos del proyecto (omitido con --continua)
<task>                    ← tu objetivo
<file_index>              ← índice compacto: path, líneas, extensión, imports
                            (omitido con --continua; ausente en --co --objetivo)
<codebase>                ← archivos con su código
  <file path="...">
  </file>
<dependency_graph>        ← solo en modo --co --objetivo
<response_instructions>   ← instrucciones para la IA
```

El `<file_index>` en el modo `--objetivo` reemplaza al árbol de directorios en texto plano: aporta la misma orientación estructural pero con metadatos adicionales (líneas, extensión, imports) y sin redundar con los paths ya presentes en `<codebase>`.

---

## 💡 Tips

```bash
# Ver el mapa y abrirlo directo
contexto . --co && code .codigo_completo/mapa_contexto.txt

# Generar contexto solo de cambios
contexto . --solo-cambios && code .codigo_completo/cambios_git.txt

# Proyecto grande: preview antes de generar
contexto . --preview --sin-minimos --limite 400

# Workflow IA completo de dos pasos (eficiente en tokens)
contexto . --co --objetivo "Agregar paginación a la API" --modelo claude
# → pasás ia_agregar_paginacion_a_la_api_mapa.txt a la IA
# → la IA analiza la estructura y te da el follow_up_command
# → ejecutás con --continua para no repetir metadatos
contexto . --objetivo "Agregar paginación a la API" --archivos src/api.py src/models.py --continua
# → pasás ia_agregar_paginacion_a_la_api_solicitado.txt a la IA
# → la IA tiene exactamente lo que necesita, sin tokens desperdiciados
```
