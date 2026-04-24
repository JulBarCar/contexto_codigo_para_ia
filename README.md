
---

# 📦 code_context.py

Herramienta CLI en Python para generar un **contexto completo de código** a partir de un proyecto.

Pensado para:

* Pasar tu código a una IA
* Revisar cambios recientes
* Tener snapshots del proyecto

---

# 🚀 ¿Qué hace?

Genera automáticamente:

* `contexto_codigo.txt` → todo el código del proyecto
* `cambios_git.txt` → solo archivos modificados desde el último pull (si es repo git)

---

# 📁 Estructura recomendada

Podés tener algo así:

```
code-context/
│
├── code_context.py
├── contexto.bat
├── contexto.sh
```

---

# ⚙️ Instalación y uso básico

## 1. Requisitos

* Python 3.8+

---

## 2. Ejecutar directamente

```bash
python code_context.py
```

O indicando carpeta:

```bash
python code_context.py ruta/a/tu/proyecto
```

---

## #🔹 Usar el comando `contexto` (forma recomendada)

Este repositorio ya incluye:

* `contexto.bat` → Windows
* `contexto.sh` → Linux / Git Bash

No necesitás editar rutas ni modificar nada 👍

---

### 🧩 Paso 1: ubicar los archivos

Ejemplo:

```id="k8r2f1"
C:\tools\code-context\
├── code_context.py
├── contexto.bat
```

o en Linux:

```id="z9p4x2"
~/tools/code-context/
├── code_context.py
├── contexto.sh
```

---

### ⚙️ Paso 2: agregar al PATH

---

#### 🪟 Windows (PATH)

1. Copiá la ruta de la carpeta (ej: `C:\tools\code-context`)

2. Abrí:

   * “Editar variables de entorno del sistema”

3. En **Path** → “Editar” → “Nuevo”

4. Pegá la ruta

5. Aceptar todo

---

#### 🐧 Linux / Mac / Git Bash

Editar tu config:

```bash
nano ~/.bashrc
```

Agregar:

```bash
export PATH="$PATH:/home/tu-usuario/tools/code-context"
```

Aplicar:

```bash
source ~/.bashrc
```

---

## ⚠️ Nota importante (Linux)

Para usar `contexto` sin `.sh`, podés:

### Opción A (simple)

Usar:

```bash
contexto.sh
```

---

### Opción B (mejor)

Renombrar:

```bash
mv contexto.sh contexto
chmod +x contexto
```

Ahora podés usar:

```bash
contexto
```

---


## 🔹 Opción 2: perfil de PowerShell

Abrí tu perfil:

```powershell
notepad $PROFILE
```

Agregá:

```powershell
function contexto {
    python "C:\ruta\a\code_context.py" $args
}
```

Reiniciás la terminal y listo.

---

## 🔹 Opción 3: alias en Bash

```bash
nano ~/.bashrc
```

Agregá:

```bash
alias contexto='python /ruta/a/code_context.py'
```

Aplicar cambios:

```bash
source ~/.bashrc
```

# 🧠 Uso del comando

## ✔️ Sin argumentos

```bash
contexto
```

* Usa la carpeta actual (`.`)
* Genera los archivos según configuración

---

## ✔️ Con argumento

```bash
contexto ruta/al/proyecto
```

Ejemplo:

```bash
contexto ../mi-backend
```

---

# 🧾 Archivo de configuración

Podés personalizar el comportamiento creando:

```
.codigo_config.json
```

---

## 📍 Ubicación

Debe estar en la raíz del proyecto:

```
/mi-proyecto/.codigo_config.json
```

---

## 🧩 Ejemplo completo

```json
{
  "nombre_salida": "mi_contexto.txt",
  "nombre_salida_cambios": "mis_cambios.txt",
  "extensiones": [".ts", ".tsx", ".js"],
  "ignorar": ["node_modules", ".git"],
  "incluir_solo": ["src", "components"],
  "carpeta_salida": "../contextos"
}
```

---

# ⚙️ Opciones explicadas

## 📝 `nombre_salida`

Nombre del archivo con TODO el código.

```json
"nombre_salida": "mi_contexto.txt"
```

---

## 🔄 `nombre_salida_cambios`

Archivo con SOLO cambios de git.

```json
"nombre_salida_cambios": "mis_cambios.txt"
```

---

## 📂 `extensiones`

Extensiones a incluir.

```json
"extensiones": [".py", ".js", ".ts"]
```

👉 Default:

* `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.html`, `.css`

---

## 🚫 `ignorar`

Archivos/carpetas a excluir.

```json
"ignorar": ["node_modules", ".git", "dist"]
```

👉 Default:

* node_modules, .git, **pycache**, dist, .env

---

## 🎯 `incluir_solo`

Limita el análisis a carpetas específicas.

```json
"incluir_solo": ["src", "components"]
```

👉 Si se usa:

* Ignora todo lo demás fuera de esas carpetas

---

## 📦 `carpeta_salida`

Dónde se guardan los archivos generados.

### Ruta absoluta

```json
"carpeta_salida": "C:/contextos"
```

### Ruta relativa

```json
"carpeta_salida": "../contextos"
```

### Default

Si no se define:

```
.codigo_completo/
```

---

# 🧠 Cómo funciona internamente

* Recorre todo el proyecto
* Filtra por:

  * extensiones
  * carpetas ignoradas
  * carpetas incluidas
* Genera:

  * árbol de archivos
  * contenido completo concatenado

---

## 🔄 Integración con Git

Si el proyecto es un repo:

* Usa `ORIG_HEAD → HEAD` (último pull)
* Si no existe:

  * usa cambios no commiteados

Si no es repo:

* simplemente no genera `cambios_git.txt`

---

# 💡 Ejemplos reales

```bash
contexto
```

```bash
contexto .
```

```bash
contexto ../api
```

---

# 🧪 Tip útil

Podés hacer:

```bash
contexto && code .codigo_completo/contexto_codigo.txt
```

o subir directamente ese archivo a una IA.

---