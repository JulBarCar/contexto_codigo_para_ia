# 📦 code_context.py

Herramienta CLI en Python para generar **contexto de código** a partir de un proyecto, listo para pasarle a una IA.

Pensado para:

- Pasar tu código a una IA de forma ordenada y eficiente
- Explorar la estructura de un proyecto antes de decidir qué compartir
- Revisar solo los archivos que cambiaron desde el último pull
- Generar contexto optimizado para IA con un objetivo específico

---

## 🚀 ¿Qué genera?

| Archivo                        | Cuándo se genera                    | Contenido                                           |
| ------------------------------ | ----------------------------------- | --------------------------------------------------- |
| `contexto_codigo.txt`          | Siempre (modo normal)               | Todo el código del proyecto                         |
| `cambios_git.txt`              | Si es repo git                      | Solo archivos modificados desde el último pull      |
| `mapa_contexto.txt`            | Con `--co`                          | Árbol + dependencias + fichas, **sin código**       |
| `ia_[objetivo]_contexto.txt`   | Con `--objetivo`                    | Contexto completo optimizado para IA, formato XML   |
| `ia_[objetivo]_mapa.txt`       | Con `--co` + `--objetivo`           | Mapa estructural (sin código) optimizado para IA    |
| `ia_[objetivo]_solicitado.txt` | Con `--objetivo` + `--archivos`     | Archivos específicos pedidos por la IA, formato XML |
| `contexto_solicitado.txt`      | Con `--archivos` (sin `--objetivo`) | Solo los archivos indicados, formato estándar       |

---

## ⚙️ Requisitos

- Python 3.10+

No requiere dependencias externas.

---

## 📁 Estructura recomendada

```
code-context/
├── code_context.py
├── contexto.bat     ← Windows
└── contexto.sh      ← Linux / Mac
```

---

## 🔧 Instalación

### 1. Crear los scripts de atajo

#### 🪟 Windows — `contexto.bat`

```bat
@echo off
python "%~dp0code_context.py" %*
```

#### 🐧 Linux / Mac — `contexto.sh`

```bash
#!/bin/bash
python3 "$(dirname "$0")/code_context.py" "$@"
```

```bash
chmod +x contexto.sh
```

---

### 2. Agregar al PATH (opcional pero recomendado)

#### 🪟 Windows

1. Copiá la ruta de la carpeta (ej: `C:\tools\code-context`)
2. Buscá "Editar variables de entorno del sistema"
3. En **Path** → "Editar" → "Nuevo"
4. Pegá la ruta → Aceptar todo

#### 🐧 Linux / Mac

```bash
nano ~/.bashrc   # o ~/.zshrc si usás zsh
export PATH="$PATH:/home/tu-usuario/tools/code-context"
source ~/.bashrc
```

---

## 🧠 Uso

### Sintaxis general

```bash
contexto [carpeta] [opciones]
```

Si no se indica carpeta, usa la carpeta actual (`.`).

### Ejemplos rápidos

```bash
contexto                        # carpeta actual, modo completo
contexto ../mi-backend          # carpeta específica
contexto . --co                 # mapa de contexto sin código
contexto . --init               # genera config con comentarios
contexto . --init --limpio      # genera config mínimo, sin comentarios
contexto . --solo-cambios       # solo archivos modificados en git
contexto . --sin-minimos        # omite lockfiles y archivos auto-generados
contexto . --limite 300         # omite archivos de más de 300 líneas
contexto . --verbose            # muestra qué archivos se omiten y por qué
contexto . --preview            # muestra qué se incluiría, sin generar nada
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

## 🔍 `--preview` — Ver antes de generar

Muestra qué archivos se incluirían y una estimación de tokens, sin escribir ningún archivo.

```bash
contexto . --preview
contexto . --preview --modelo claude --sin-minimos --limite 400
```

Útil para calibrar la configuración antes de generar el contexto final.

---

## 📊 `--stats` — Solo estimación de tokens

Muestra la estimación de tokens en consola sin generar ningún archivo.

```bash
contexto . --stats --modelo claude
```

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

# 3. Ejecutar ese comando → la IA recibe exactamente lo que necesita
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
| `modelo`                | Modelo para estimación de tokens. CLI tiene prioridad.                     |

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

## 💡 Tips

```bash
# Ver el mapa y abrirlo directo
contexto . --co && code .codigo_completo/mapa_contexto.txt

# Generar contexto solo de cambios
contexto . --solo-cambios && code .codigo_completo/cambios_git.txt

# Proyecto grande: preview antes de generar
contexto . --preview --sin-minimos --limite 400

# Workflow IA completo
contexto . --objetivo "Agregar paginación a la API" --modelo claude
# → pasás ia_agregar_paginacion_a_la_api_contexto.txt a la IA
# → la IA te da el follow_up_command
# → ejecutás ese comando
# → pasás ia_agregar_paginacion_a_la_api_solicitado.txt a la IA
```
