# 📦 code_context.py

Herramienta CLI en Python para generar **contexto de código** a partir de un proyecto, listo para pasarle a una IA.

Pensado para:

- Pasar tu código a una IA de forma ordenada y eficiente
- Explorar la estructura de un proyecto antes de decidir qué compartir
- Revisar solo los archivos que cambiaron desde el último pull

---

## 🚀 ¿Qué genera?

| Archivo               | Cuándo se genera      | Contenido                                      |
| --------------------- | --------------------- | ---------------------------------------------- |
| `contexto_codigo.txt` | Siempre (modo normal) | Todo el código del proyecto                    |
| `cambios_git.txt`     | Si es repo git        | Solo archivos modificados desde el último pull |
| `mapa_contexto.txt`   | Con `--co`            | Árbol + dependencias + fichas, **sin código**  |

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

Si no tenés los archivos `.bat` o `.sh`, creálos a mano:

#### 🪟 Windows — `contexto.bat`

Creá un archivo llamado `contexto.bat` en la misma carpeta que `code_context.py` con este contenido:

```bat
@echo off
python "%~dp0code_context.py" %*
```

#### 🐧 Linux / Mac — `contexto.sh`

Creá un archivo llamado `contexto.sh`:

```bash
#!/bin/bash
python3 "$(dirname "$0")/code_context.py" "$@"
```

Luego dále permisos de ejecución:

```bash
chmod +x contexto.sh
```

Opcionalmente, renombralo para usarlo sin extensión:

```bash
mv contexto.sh contexto
chmod +x contexto
```

---

### 2. Agregar al PATH (opcional pero recomendado)

Hacerlo te permite escribir `contexto` desde cualquier carpeta.

#### 🪟 Windows

1. Copiá la ruta de la carpeta (ej: `C:\tools\code-context`)
2. Buscá "Editar variables de entorno del sistema"
3. En **Path** → "Editar" → "Nuevo"
4. Pegá la ruta → Aceptar todo

#### 🐧 Linux / Mac

```bash
nano ~/.bashrc   # o ~/.zshrc si usás zsh
```

Agregá:

```bash
export PATH="$PATH:/home/tu-usuario/tools/code-context"
```

Aplicá los cambios:

```bash
source ~/.bashrc
```

#### 🐧 Alternativa: alias

```bash
alias contexto='python3 /ruta/a/code_context.py'
```

#### 🪟 Alternativa: perfil de PowerShell

```powershell
notepad $PROFILE
```

Agregá:

```powershell
function contexto {
    python "C:\ruta\a\code_context.py" $args
}
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
contexto . --init               # genera config de ejemplo
contexto . --solo-cambios       # solo archivos modificados en git
contexto . --sin-minimos        # omite lockfiles y archivos auto-generados
contexto . --limite 300         # omite archivos de más de 300 líneas
contexto . --verbose            # muestra qué archivos se omiten y por qué
```

---

## 📋 Referencia de argumentos

| Argumento        | Descripción                                                    |
| ---------------- | -------------------------------------------------------------- |
| `--init`         | Genera un `.codigo_config.json` de ejemplo con comentarios     |
| `--co`           | Modo "context only": árbol + dependencias + fichas, sin código |
| `--solo-cambios` | Solo genera el archivo de cambios git                          |
| `--limite N`     | Omite archivos con más de N líneas                             |
| `--sin-minimos`  | Omite lockfiles, `.min.js`, y otros auto-generados             |
| `--verbose`      | Muestra detalle de archivos omitidos                           |
| `--ayuda`        | Muestra ayuda                                                  |

---

## 🗺️ Modo `--co` (Context Only)

Este modo está pensado para **explorar antes de compartir**.

Genera un archivo liviano que incluye:

- Árbol de archivos del proyecto
- Ficha por archivo (líneas, extensión, qué importa)
- Grafo de dependencias internas (qué archivos se llaman entre sí)
- Últimos commits de git

**No incluye ninguna línea de código.**

Flujo recomendado:

```
1. Corrés --co y revisás el mapa
2. Decidís qué carpetas o archivos son relevantes para tu tarea
3. Los configurás en "incluir_solo" o usás --solo-cambios
4. Generás el contexto final y lo pasás a la IA
```

```bash
contexto . --co
```

---

## 🧾 Archivo de configuración

Podés personalizar el comportamiento creando `.codigo_config.json` en la raíz de tu proyecto.

La forma más fácil es generarlo con `--init`:

```bash
contexto . --init
```

Esto crea un archivo de ejemplo con todos los campos explicados. Editalo según tu proyecto.

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
  "nombre_salida_co": "mapa_contexto.txt"
}
```

### Opciones explicadas

#### `descripcion`

Una oración que describe tu proyecto. Aparece al inicio del archivo de contexto, antes del código. La IA la lee primero y orienta todo el análisis posterior.

```json
"descripcion": "Backend en Node.js para una app de delivery. Usa Express y PostgreSQL."
```

#### `extensiones`

Extensiones de archivo a incluir.

```json
"extensiones": [".py", ".js", ".ts"]
```

Default: `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.html`, `.css`

#### `ignorar`

Carpetas o archivos a excluir.

```json
"ignorar": ["node_modules", ".git", "dist", "venv"]
```

Default: `node_modules`, `.git`, `__pycache__`, `dist`, `.env`, `venv`, `build`

#### `incluir_solo`

Si se define, solo se analizan estas carpetas raíz. Todo lo demás se ignora.

```json
"incluir_solo": ["src", "api"]
```

#### `limite_lineas`

Archivos con más líneas que este valor se omiten. Útil para reducir tokens.

```json
"limite_lineas": 500
```

Default: sin límite

#### `omitir_autogenerados`

Si es `true`, omite automáticamente:

- Lockfiles: `package-lock.json`, `yarn.lock`, `poetry.lock`, `Pipfile.lock`, `go.sum`, etc.
- Archivos minificados: `*.min.js`, `*.bundle.js`, `*.chunk.js`
- Archivos auto-generados: `*_pb2.py` (protobuf), `*.generated.*`, migraciones auto-numeradas
- Archivos con primera línea mayor a 500 caracteres (heurística de minificado)

```json
"omitir_autogenerados": true
```

#### `carpeta_salida`

Dónde guardar los archivos generados. Acepta rutas absolutas o relativas al proyecto.

```json
"carpeta_salida": "../contextos"
```

Default: carpeta `.codigo_completo/` dentro del proyecto

---

## 🔄 Integración con Git

Si el proyecto es un repositorio git, el script genera automáticamente `cambios_git.txt` con:

- Los archivos que cambiaron entre `ORIG_HEAD` y `HEAD` (después de un pull/merge/rebase)
- Si no existe `ORIG_HEAD`: los cambios staged y unstaged sin commitear
- Los últimos 5 commits incluidos como contexto en el encabezado del archivo

Si la carpeta no es un repo git, simplemente no genera el archivo de cambios.

---

## 📂 Orden de archivos

Los archivos se ordenan para que la IA construya el modelo mental del proyecto de arriba hacia abajo:

1. Primero los archivos en la raíz del proyecto
2. Dentro de cada nivel, los archivos clave van primero: `main`, `index`, `app`, `server`, `__init__`, `config`, `settings`, `manage`, etc.
3. Luego el resto, ordenado alfabéticamente

---

## 💡 Tips

```bash
# Ver el mapa del proyecto y abrirlo directo
contexto . --co && code .codigo_completo/mapa_contexto.txt

# Generar contexto solo de los cambios y abrirlo
contexto . --solo-cambios && code .codigo_completo/cambios_git.txt

# Proyecto grande: omitir auto-generados y limitar tamaño de archivos
contexto . --sin-minimos --limite 400

# Ver exactamente qué se está omitiendo
contexto . --verbose
```

---
