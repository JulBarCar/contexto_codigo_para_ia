# 📦 contexto_codigo_para_ia

**Generado:** 2026-06-01 16:30:52  
**Raíz del proyecto:** `C:\Users\julia\OneDrive\Documentos\contexto_codigo_para_ia`  
**Total de archivos:** 37  
**Extensiones:** `.css, .html, .js, .jsx, .py, .ts, .tsx`  

---

## 📋 Tabla de Contenidos

1. [Árbol de Archivos](#-árbol-de-archivos)
2. [Resumen por Extensión](#-resumen-por-extensión)
3. [Ficha por Archivo](#-ficha-por-archivo)
4. [Grafo de Dependencias](#-grafo-de-dependencias-internas)
5. [Historial de Commits](#-historial-de-commits)
6. [Estimación de Tokens](#-estimación-de-tokens)

---

## 🗂 Árbol de Archivos

```
contexto_codigo_para_ia/
  code_context.py
  modules/
    __init__.py
    ai.py
    cli.py
    compresor.py
    git.py
    imports/
      core.py
    config/
      defaults.py
    filesystem/
      filters.py
    output/
      human_writers.py
      loader.py
    aliases/
      loaders.py
      log.py
      ordering.py
      preview.py
      resolver.py
      tree_builder.py
      writers.py
      strategies/
        __init__.py
        base.py
        c_strategy.py
        csharp_strategy.py
        dart_strategy.py
        go_strategy.py
        java_strategy.py
        js_strategy.py
        kotlin_strategy.py
        php_strategy.py
        python_strategy.py
        r_strategy.py
        ruby_strategy.py
        rust_strategy.py
        scala_strategy.py
        shell_strategy.py
        svelte_strategy.py
        swift_strategy.py
        vue_strategy.py
```

---

## 📊 Resumen por Extensión

| Extensión | Archivos | Lenguaje |
|-----------|:--------:|---------|
| `.py` | 37 | python |

**Total de líneas:** 6.481

---

## 📄 Ficha por Archivo

### 📁 `📁 Raíz`

#### `code_context.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `code_context.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 305 |
| **Importa** | `sys`, `pathlib`, `modules` |

### 📁 `modules`

#### `__init__.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/__init__.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 0 |
| **Importa** | *(ninguna detectada)* |

#### `ai.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/ai.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 140 |
| **Importa** | `re` |

#### `cli.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/cli.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 171 |
| **Importa** | `sys`, `modules` |

#### `compresor.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/compresor.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 315 |
| **Importa** | `ast`, `io`, `re`, `sys`, `tokenize`, `enum`, `pathlib`, `argparse` |

#### `git.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/git.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 62 |
| **Importa** | `subprocess`, `pathlib` |

### 📁 `modules\imports`

#### `core.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/core.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 296 |
| **Importa** | `pathlib`, `modules`, `strategies` |

### 📁 `modules\config`

#### `defaults.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/config/defaults.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 51 |
| **Importa** | `re` |

### 📁 `modules\filesystem`

#### `filters.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/filesystem/filters.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 100 |
| **Importa** | `pathlib`, `modules` |

### 📁 `modules\output`

#### `human_writers.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/output/human_writers.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 1.061 |
| **Importa** | `platform`, `shutil`, `subprocess`, `datetime`, `pathlib`, `modules` |

### 📁 `modules\config`

#### `loader.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/config/loader.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 168 |
| **Importa** | `json`, `pathlib`, `modules` |

### 📁 `modules\aliases`

#### `loaders.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/aliases/loaders.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 223 |
| **Importa** | `json`, `re`, `pathlib` |

### 📁 `modules\output`

#### `log.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/output/log.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 27 |
| **Importa** | `pathlib` |

### 📁 `modules\filesystem`

#### `ordering.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/filesystem/ordering.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 20 |
| **Importa** | `pathlib`, `modules` |

### 📁 `modules\output`

#### `preview.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/output/preview.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 82 |
| **Importa** | `pathlib`, `modules` |

### 📁 `modules\aliases`

#### `resolver.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/aliases/resolver.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 67 |
| **Importa** | `pathlib` |

### 📁 `modules\output`

#### `tree_builder.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/output/tree_builder.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 21 |
| **Importa** | `pathlib` |

#### `writers.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/output/writers.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 367 |
| **Importa** | `datetime`, `pathlib`, `modules` |

### 📁 `modules\imports\strategies`

#### `__init__.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/__init__.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 88 |
| **Importa** | `base.py`, `js_strategy.py`, `python_strategy.py`, `svelte_strategy.py`, `vue_strategy.py`, `java_strategy.py`, `csharp_strategy.py`, `go_strategy.py`, `rust_strategy.py`, `php_strategy.py`, `ruby_strategy.py`, `kotlin_strategy.py`, `swift_strategy.py`, `c_strategy.py`, `scala_strategy.py`, `dart_strategy.py`, `r_strategy.py`, `shell_strategy.py` |

#### `base.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/base.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 37 |
| **Importa** | `abc`, `pathlib` |

#### `c_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/c_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 345 |
| **Importa** | `re`, `functools`, `pathlib`, `base.py` |

#### `csharp_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/csharp_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 156 |
| **Importa** | `re`, `pathlib`, `base.py` |

#### `dart_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/dart_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 85 |
| **Importa** | `re`, `pathlib`, `base.py` |

#### `go_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/go_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 141 |
| **Importa** | `re`, `functools`, `pathlib`, `base.py` |

#### `java_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/java_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 146 |
| **Importa** | `re`, `functools`, `pathlib`, `base.py` |

#### `js_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/js_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 153 |
| **Importa** | `re`, `pathlib`, `base.py` |

#### `kotlin_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/kotlin_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 127 |
| **Importa** | `re`, `functools`, `pathlib`, `base.py` |

#### `php_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/php_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 186 |
| **Importa** | `json`, `re`, `functools`, `pathlib`, `base.py` |

#### `python_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/python_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 123 |
| **Importa** | `ast`, `pathlib`, `base.py` |

#### `r_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/r_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 169 |
| **Importa** | `json`, `re`, `functools`, `pathlib`, `base.py` |

#### `ruby_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/ruby_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 168 |
| **Importa** | `re`, `functools`, `pathlib`, `base.py` |

#### `rust_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/rust_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 161 |
| **Importa** | `re`, `pathlib`, `base.py` |

#### `scala_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/scala_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 155 |
| **Importa** | `re`, `pathlib`, `base.py` |

#### `shell_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/shell_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 131 |
| **Importa** | `re`, `pathlib`, `base.py` |

#### `svelte_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/svelte_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 192 |
| **Importa** | `re`, `functools`, `pathlib`, `js_strategy.py` |

#### `swift_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/swift_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 212 |
| **Importa** | `re`, `functools`, `pathlib`, `base.py` |

#### `vue_strategy.py`

| Campo | Valor |
|-------|-------|
| **Ruta** | `modules/imports/strategies/vue_strategy.py` |
| **Extensión** | `.py` |
| **Lenguaje** | python |
| **Líneas** | 230 |
| **Importa** | `re`, `functools`, `pathlib`, `js_strategy.py` |

---

## 🔗 Grafo de Dependencias Internas

> Muestra qué archivos del proyecto se importan entre sí.

> *(No se detectaron dependencias internas entre los archivos incluidos)*

---

## 📝 Historial de Commits

| # | Commit |
|---|--------|
| 1 | `ec62322` modularizacion estable dle proyecto, y implementación de strategie es para mapa de imports |
| 2 | `677c7f1` modularizacion estable dle proyecto, y implementación de strategie es para mapa de imports |
| 3 | `089aff9` Merge branch 'main' of https://github.com/JulBarCar/contexto_codigo_para_ia unificar trabajo desde ambos puntos |
| 4 | `ed00489` prijmer paso hacia estructura modular |
| 5 | `81e3179` acutalizacion de la generacion del imports tree |

---

## 🔢 Estimación de Tokens

| Campo | Valor |
|-------|-------|
| **Modelo** | Genérico (sin modelo específico) |
| **Caracteres** | 0 |
| **Tokens estimados** | ~0 |
| **Costo estimado** | *no disponible* |

> *Los precios y límites pueden haber cambiado. Verificá en la documentación oficial del modelo.*

---

*Generado por [code_context](https://github.com) — 2026-06-01 16:30:52*
