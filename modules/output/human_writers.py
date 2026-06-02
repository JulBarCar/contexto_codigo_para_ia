"""
modules/output/human_writers.py
Generación de archivos amigables para humanos en formato Markdown y LaTeX.

Activado con --md y/o --latex desde la CLI.
Por defecto incluye:
  - Árbol de archivos
  - Ficha por archivo (líneas, extensión, imports)
  - Grafo de dependencias internas
  - Commits recientes de git
  - Estimación de tokens

NO incluye código fuente (equivalente a --co implícito).
Estos archivos están pensados para ser leídos por personas,
no por IAs, así que el peso no importa.

Markdown:
  - Tabla de contenidos clickeable
  - Árbol con bloques de código
  - Tablas de fichas y dependencias
  - Badges de estado visual

LaTeX:
  - Portada automática con metadata del proyecto
  - Syntax highlighting real con minted
  - Cajas tcolorbox para secciones
  - Índice de contenidos automático
  - Tabla de dependencias con booktabs

Compilación LaTeX (compilar_latex):
  - Detecta pdflatex en el PATH (Windows y Linux/macOS)
  - Si no está disponible, muestra instrucciones de instalación detalladas
  - Ejecuta dos pasadas (necesario para \\tableofcontents)
  - Limpia archivos auxiliares tras la compilación exitosa
  - Maneja timeouts y errores con mensajes amigables
"""

import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from modules.ai import estimar_tokens
from modules.imports.core import _construir_grafo, extraer_importaciones
from modules.output.tree_builder import construir_arbol


# ── Helpers compartidos ───────────────────────────────────────────────────────

def _badge_tokens(est: dict) -> str:
    """Devuelve un badge Markdown según el porcentaje del context window."""
    pct = est.get("porcentaje_window")
    tokens = f"{est['tokens']:,}".replace(",", ".")
    if pct is None:
        return f"![tokens](https://img.shields.io/badge/tokens-{tokens.replace('.', '_')}-blue)"
    if pct <= 85:
        color = "brightgreen"
        label = f"{pct:.0f}%_del_window_✓"
    elif pct <= 100:
        color = "orange"
        label = f"{pct:.0f}%_del_window_⚠"
    else:
        color = "red"
        label = f"{pct:.0f}%_EXCEDE_✗"
    return (
        f"![tokens](https://img.shields.io/badge/tokens-{tokens.replace('.', '_')}-blue) "
        f"![window](https://img.shields.io/badge/context_window-{label.replace(' ', '_')}-{color})"
    )


def _ext_to_lang(extension: str) -> str:
    """Mapea extensión de archivo a nombre de lenguaje para syntax highlighting."""
    return {
        ".py":     "python",
        ".js":     "javascript",
        ".ts":     "typescript",
        ".jsx":    "jsx",
        ".tsx":    "tsx",
        ".html":   "html",
        ".css":    "css",
        ".go":     "go",
        ".rs":     "rust",
        ".java":   "java",
        ".cs":     "csharp",
        ".cpp":    "cpp",
        ".c":      "c",
        ".rb":     "ruby",
        ".php":    "php",
        ".kt":     "kotlin",
        ".swift":  "swift",
        ".scala":  "scala",
        ".sh":     "bash",
        ".bash":   "bash",
        ".r":      "r",
        ".R":      "r",
        ".vue":    "vue",
        ".svelte": "svelte",
        ".dart":   "dart",
    }.get(extension.lower(), "text")


def _ext_to_latex_lang(extension: str) -> str:
    """Mapea extensión a lenguaje para minted en LaTeX."""
    return {
        ".py":     "python3",
        ".js":     "javascript",
        ".ts":     "typescript",
        ".jsx":    "jsx",
        ".tsx":    "tsx",
        ".html":   "html",
        ".css":    "css",
        ".go":     "go",
        ".rs":     "rust",
        ".java":   "java",
        ".cs":     "csharp",
        ".cpp":    "cpp",
        ".c":      "c",
        ".rb":     "ruby",
        ".php":    "php",
        ".kt":     "kotlin",
        ".swift":  "swift",
        ".scala":  "scala",
        ".sh":     "bash",
        ".bash":   "bash",
        ".r":      "r",
        ".R":      "r",
        ".vue":    "html",
        ".svelte": "html",
        ".dart":   "dart",
    }.get(extension.lower(), "text")


def _escapar_latex(texto: str) -> str:
    """Escapa caracteres especiales de LaTeX."""
    replacements = [
        ("\\", "\\textbackslash{}"),
        ("&",  "\\&"),
        ("%",  "\\%"),
        ("$",  "\\$"),
        ("#",  "\\#"),
        ("_",  "\\_"),
        ("{",  "\\{"),
        ("}",  "\\}"),
        ("~",  "\\textasciitilde{}"),
        ("^",  "\\textasciicircum{}"),
    ]
    for src, dst in replacements:
        texto = texto.replace(src, dst)
    return texto


def _resumen_extension(archivos: list) -> dict:
    """Cuenta archivos por extensión."""
    conteo: dict[str, int] = {}
    for archivo in archivos:
        ext = archivo.suffix or "(sin extensión)"
        conteo[ext] = conteo.get(ext, 0) + 1
    return dict(sorted(conteo.items()))


# ── Writer de Markdown ────────────────────────────────────────────────────────

def escribir_markdown(
    salida_path: Path,
    archivos: list,
    raiz: Path,
    config: dict,
    commits: list,
    modelo: str = "default",
) -> dict | None:
    """
    Genera un archivo Markdown amigable para humanos con:
      - Encabezado con metadata y badges
      - Tabla de contenidos
      - Árbol de archivos
      - Resumen de extensiones (tabla)
      - Ficha detallada por archivo
      - Grafo de dependencias internas (tabla)
      - Últimos commits
      - Estimación de tokens al final
    """
    ts  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "---"

    with open(salida_path, "w", encoding="utf-8") as f:

        # ── Encabezado ────────────────────────────────────────────────────────
        nombre_proyecto = raiz.resolve().name
        f.write(f"# 📦 {nombre_proyecto}\n\n")

        if config.get("descripcion"):
            f.write(f"> {config['descripcion']}\n\n")

        f.write(f"**Generado:** {ts}  \n")
        f.write(f"**Raíz del proyecto:** `{raiz}`  \n")
        f.write(f"**Total de archivos:** {len(archivos)}  \n")
        ext_list = ", ".join(sorted(config["extensiones"]))
        f.write(f"**Extensiones:** `{ext_list}`  \n")
        if config.get("incluir_solo"):
            carpetas = ", ".join(f"`{c}`" for c in config["incluir_solo"])
            f.write(f"**Carpetas incluidas:** {carpetas}  \n")
        f.write("\n")
        f.write(sep + "\n\n")

        # ── Tabla de contenidos ───────────────────────────────────────────────
        f.write("## 📋 Tabla de Contenidos\n\n")
        f.write("1. [Árbol de Archivos](#-árbol-de-archivos)\n")
        f.write("2. [Resumen por Extensión](#-resumen-por-extensión)\n")
        f.write("3. [Ficha por Archivo](#-ficha-por-archivo)\n")
        f.write("4. [Grafo de Dependencias](#-grafo-de-dependencias-internas)\n")
        if commits:
            f.write("5. [Historial de Commits](#-historial-de-commits)\n")
            f.write("6. [Estimación de Tokens](#-estimación-de-tokens)\n")
        else:
            f.write("5. [Estimación de Tokens](#-estimación-de-tokens)\n")
        f.write("\n")
        f.write(sep + "\n\n")

        # ── Árbol de archivos ─────────────────────────────────────────────────
        f.write("## 🗂 Árbol de Archivos\n\n")
        f.write("```\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n```\n\n")
        f.write(sep + "\n\n")

        # ── Resumen por extensión ─────────────────────────────────────────────
        f.write("## 📊 Resumen por Extensión\n\n")
        conteo_ext = _resumen_extension(archivos)
        total_lineas_global = 0
        lineas_por_archivo: dict[Path, int] = {}
        for archivo in archivos:
            try:
                n = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            except Exception:
                n = 0
            lineas_por_archivo[archivo] = n
            total_lineas_global += n

        f.write("| Extensión | Archivos | Lenguaje |\n")
        f.write("|-----------|:--------:|---------|\n")
        for ext, cantidad in conteo_ext.items():
            lang = _ext_to_lang(ext)
            f.write(f"| `{ext}` | {cantidad} | {lang} |\n")
        f.write(f"\n**Total de líneas:** {total_lineas_global:,}".replace(",", ".") + "\n\n")
        f.write(sep + "\n\n")

        # ── Ficha por archivo ─────────────────────────────────────────────────
        f.write("## 📄 Ficha por Archivo\n\n")

        carpeta_actual = None
        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            carpeta  = str(relativo.parent) if str(relativo.parent) != "." else "📁 Raíz"

            if carpeta != carpeta_actual:
                carpeta_actual = carpeta
                f.write(f"### 📁 `{carpeta}`\n\n")

            n_lineas      = lineas_por_archivo.get(archivo, 0)
            importaciones = extraer_importaciones(archivo)
            lang          = _ext_to_lang(archivo.suffix)

            f.write(f"#### `{archivo.name}`\n\n")
            f.write(f"| Campo | Valor |\n")
            f.write(f"|-------|-------|\n")
            f.write(f"| **Ruta** | `{relativo.as_posix()}` |\n")
            f.write(f"| **Extensión** | `{archivo.suffix}` |\n")
            f.write(f"| **Lenguaje** | {lang} |\n")
            f.write(f"| **Líneas** | {n_lineas:,}".replace(",", ".") + " |\n")

            if importaciones:
                # Mostrar máximo 20 imports, el resto como "+N más"
                mostrar = importaciones[:20]
                extras  = len(importaciones) - len(mostrar)
                imports_str = ", ".join(f"`{i}`" for i in mostrar)
                if extras > 0:
                    imports_str += f" *(+{extras} más)*"
                f.write(f"| **Importa** | {imports_str} |\n")
            else:
                f.write(f"| **Importa** | *(ninguna detectada)* |\n")

            f.write("\n")

        f.write(sep + "\n\n")

        # ── Grafo de dependencias ─────────────────────────────────────────────
        f.write("## 🔗 Grafo de Dependencias Internas\n\n")
        f.write("> Muestra qué archivos del proyecto se importan entre sí.\n\n")

        dep_lines = _construir_grafo(archivos, raiz)

        if dep_lines:
            f.write("| Archivo | Depende de |\n")
            f.write("|---------|------------|\n")
            for rel, deps in dep_lines:
                deps_fmt = "<br>".join(f"`{d}`" for d in deps)
                f.write(f"| `{rel}` | {deps_fmt} |\n")
            f.write("\n")

            # También en formato árbol para mejor legibilidad
            f.write("<details>\n<summary>Ver en formato árbol</summary>\n\n```\n")
            for rel, deps in dep_lines:
                f.write(f"{rel}\n")
                for i, d in enumerate(deps):
                    conector = "└─" if i == len(deps) - 1 else "├─"
                    f.write(f"  {conector} {d}\n")
            f.write("```\n</details>\n\n")
        else:
            f.write("> *(No se detectaron dependencias internas entre los archivos incluidos)*\n\n")

        f.write(sep + "\n\n")

        # ── Commits ───────────────────────────────────────────────────────────
        if commits:
            f.write("## 📝 Historial de Commits\n\n")
            f.write("| # | Commit |\n")
            f.write("|---|--------|\n")
            for i, commit in enumerate(commits, 1):
                # Separar hash del mensaje si tiene el formato "abc1234 mensaje"
                partes = commit.split(" ", 1)
                if len(partes) == 2:
                    hash_str, mensaje = partes
                    f.write(f"| {i} | `{hash_str}` {_escapar_markdown(mensaje)} |\n")
                else:
                    f.write(f"| {i} | `{commit}` |\n")
            f.write("\n")
            f.write(sep + "\n\n")

        # ── Estimación de tokens ──────────────────────────────────────────────
        f.write("## 🔢 Estimación de Tokens\n\n")
        try:
            texto_total = salida_path.read_text(encoding="utf-8", errors="replace")
            est  = estimar_tokens(texto_total, modelo)
            info = est["info_modelo"]

            if est.get("porcentaje_window") is not None:
                f.write(_badge_tokens(est) + "\n\n")

            f.write("| Campo | Valor |\n")
            f.write("|-------|-------|\n")
            f.write(f"| **Modelo** | {info['nombre_display']} |\n")
            f.write(f"| **Caracteres** | {est['chars']:,}".replace(",", ".") + " |\n")
            f.write(f"| **Tokens estimados** | ~{est['tokens']:,}".replace(",", ".") + " |\n")
            if est["costo_usd"] is not None:
                f.write(f"| **Costo estimado** | ~${est['costo_usd']:.4f} USD *(solo entrada)* |\n")
            else:
                f.write(f"| **Costo estimado** | *no disponible* |\n")
            if est["porcentaje_window"] is not None:
                pct    = est["porcentaje_window"]
                cw_fmt = f"{info['context_window']:,}".replace(",", ".")
                estado = "✓ entra" if pct <= 85 else ("⚠ cerca del límite" if pct <= 100 else "✗ EXCEDE")
                f.write(f"| **Context window** | {pct:.1f}% de {cw_fmt} tokens — {estado} |\n")

            f.write("\n")
            f.write("> *Los precios y límites pueden haber cambiado. "
                    "Verificá en la documentación oficial del modelo.*\n\n")
            f.write(sep + "\n\n")
            f.write(f"*Generado por [code_context](https://github.com) — {ts}*\n")

            return est
        except Exception:
            f.write("*(No se pudo calcular la estimación de tokens)*\n\n")
            return None


def _escapar_markdown(texto: str) -> str:
    """Escapa caracteres problemáticos en tablas Markdown."""
    return texto.replace("|", "\\|").replace("\n", " ")


# ── Writer de LaTeX ───────────────────────────────────────────────────────────

def escribir_latex(
    salida_path: Path,
    archivos: list,
    raiz: Path,
    config: dict,
    commits: list,
    modelo: str = "default",
) -> dict | None:
    """
    Genera un archivo LaTeX amigable para humanos con:
      - Portada automática con metadata
      - Índice de contenidos
      - Árbol de archivos en entorno verbatim elegante
      - Tabla de extensiones
      - Ficha por archivo con tabla booktabs
      - Grafo de dependencias en tabla
      - Historial de commits
      - Estimación de tokens
    """
    ts              = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nombre_proyecto = raiz.resolve().name
    descripcion_tex = _escapar_latex(config.get("descripcion") or "")
    raiz_tex        = _escapar_latex(str(raiz))

    with open(salida_path, "w", encoding="utf-8") as f:

        # ── Preámbulo ─────────────────────────────────────────────────────────
        f.write(r"""\documentclass[12pt, a4paper]{report}

% ── Codificación y fuentes ────────────────────────────────────────────────────
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{microtype}

% ── Idioma ────────────────────────────────────────────────────────────────────
\usepackage[spanish]{babel}

% ── Geometría de página ───────────────────────────────────────────────────────
\usepackage[
  top=2.5cm, bottom=2.5cm,
  left=3cm,  right=2.5cm,
  headheight=14pt
]{geometry}

% ── Colores ───────────────────────────────────────────────────────────────────
\usepackage[dvipsnames, table]{xcolor}

% Paleta de colores del tema
\definecolor{primary}{HTML}{1a1a2e}
\definecolor{accent}{HTML}{e94560}
\definecolor{secondary}{HTML}{16213e}
\definecolor{light}{HTML}{f5f5f5}
\definecolor{codebg}{HTML}{1e1e2e}
\definecolor{codefg}{HTML}{cdd6f4}
\definecolor{tablehead}{HTML}{0f3460}
\definecolor{tablerow}{HTML}{eef2ff}
\definecolor{success}{HTML}{40bf77}
\definecolor{warning}{HTML}{f5a623}
\definecolor{danger}{HTML}{e94560}
\definecolor{muted}{HTML}{6b7280}
\definecolor{border}{HTML}{d1d5db}

% ── Tipografía ────────────────────────────────────────────────────────────────
\usepackage{fontawesome5}
\usepackage{setspace}
\setstretch{1.15}

% ── Tablas ───────────────────────────────────────────────────────────────────
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage{tabularx}
\usepackage{multirow}
\usepackage{makecell}

% ── Cajas y marcos ───────────────────────────────────────────────────────────
\usepackage[most]{tcolorbox}
\tcbuselibrary{listings, breakable, skins}

% Caja de código estilo terminal oscura
\newtcolorbox{terminalbox}[1][]{
  enhanced,
  breakable,
  colback=codebg,
  colframe=accent,
  coltitle=white,
  fonttitle=\bfseries\small,
  title={#1},
  arc=4pt,
  boxrule=0.8pt,
  left=6pt, right=6pt, top=4pt, bottom=4pt,
  attach boxed title to top left={yshift=-2.5mm, xshift=6mm},
  boxed title style={
    colback=accent, arc=3pt, boxrule=0pt,
    left=4pt, right=4pt, top=1pt, bottom=1pt
  },
}

% Caja informativa para fichas de archivo
\newtcolorbox{fichabox}[1][]{
  enhanced,
  breakable,
  colback=light,
  colframe=primary,
  coltitle=white,
  fonttitle=\bfseries\ttfamily\small,
  title={#1},
  arc=3pt,
  boxrule=0.6pt,
  left=8pt, right=8pt, top=4pt, bottom=4pt,
  attach boxed title to top left={yshift=-2.5mm, xshift=6mm},
  boxed title style={
    colback=primary, arc=2pt, boxrule=0pt,
    left=5pt, right=5pt, top=1.5pt, bottom=1.5pt
  },
}

% Caja de sección destacada
\newtcolorbox{sectionbox}[1][]{
  enhanced,
  colback=secondary!8,
  colframe=secondary,
  fonttitle=\bfseries,
  title={#1},
  arc=2pt,
  boxrule=0.5pt,
  left=6pt, right=6pt,
}

% ── Código fuente ────────────────────────────────────────────────────────────
\usepackage{fancyvrb}
\usepackage{listings}

% Configuración de listings para el árbol de archivos
\lstset{
  basicstyle=\ttfamily\small,
  backgroundcolor=\color{codebg},
  frame=none,
  breaklines=true,
  postbreak=\mbox{\textcolor{accent}{$\hookrightarrow$}\space},
}

% ── Encabezados y pies de página ─────────────────────────────────────────────
\usepackage{fancyhdr}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small\textcolor{muted}{\faIcon{folder-open}\ """ + _escapar_latex(nombre_proyecto) + r"""}}
\fancyhead[R]{\small\textcolor{muted}{\leftmark}}
\fancyfoot[C]{\small\textcolor{muted}{\thepage}}
\renewcommand{\headrulewidth}{0.3pt}
\renewcommand{\footrulewidth}{0pt}
\renewcommand{\headrule}{\color{border}\hrule width\headwidth height\headrulewidth}

% ── Títulos de sección ────────────────────────────────────────────────────────
\usepackage{titlesec}
\titleformat{\chapter}[display]
  {\normalfont\huge\bfseries\color{primary}}
  {\textcolor{accent}{\chaptertitlename\ \thechapter}}
  {16pt}
  {\Huge}
\titleformat{\section}
  {\normalfont\Large\bfseries\color{secondary}}
  {\textcolor{accent}{\thesection}}
  {1em}{}
\titleformat{\subsection}
  {\normalfont\large\bfseries\color{primary!80}}
  {\thesubsection}
  {0.8em}{}

% ── Hiperlinks ────────────────────────────────────────────────────────────────
\usepackage[
  colorlinks=true,
  linkcolor=accent,
  urlcolor=accent,
  citecolor=secondary
]{hyperref}

% ── Misceláneos ───────────────────────────────────────────────────────────────
\usepackage{parskip}
\usepackage{enumitem}
\setlist{noitemsep, topsep=4pt}

% ── Metadatos PDF ─────────────────────────────────────────────────────────────
\hypersetup{
  pdftitle={Documentación: """ + _escapar_latex(nombre_proyecto) + r"""},
  pdfauthor={code\_context},
  pdfsubject={Contexto del proyecto},
}

\begin{document}

""")

        # ── Portada ───────────────────────────────────────────────────────────
        f.write(r"""\begin{titlepage}
  \pagecolor{primary}
  \color{white}
  \centering
  \vspace*{3cm}

  % Ícono grande
  {\fontsize{72}{72}\selectfont\textcolor{accent}{\faIcon{folder-open}}}

  \vspace{1.5cm}

  % Nombre del proyecto
  {\fontsize{36}{40}\selectfont\bfseries """ + _escapar_latex(nombre_proyecto) + r"""}

  \vspace{0.5cm}
  \textcolor{accent}{\rule{8cm}{1.5pt}}
  \vspace{0.5cm}

""")
        if descripcion_tex:
            f.write(f"  {{\\large\\itshape {descripcion_tex}}}\n\n  \\vspace{{0.8cm}}\n")

        f.write(r"""  % Metadata
  \begin{tcolorbox}[
    enhanced,
    colback=white!10,
    colframe=white!30,
    arc=4pt,
    boxrule=0.5pt,
    width=10cm,
    halign=center,
  ]
    \small
    \faIcon{calendar-alt}\ \textbf{Generado:} """ + _escapar_latex(ts) + r""" \\[4pt]
    \faIcon{code}\ \textbf{Archivos:} """ + str(len(archivos)) + r""" \\[4pt]
    \faIcon{folder}\ \textbf{Raíz:} \texttt{""" + raiz_tex + r"""}
  \end{tcolorbox}

  \vfill
  \textcolor{white!60}{\small Generado con \texttt{code\_context}}
\end{titlepage}
\nopagecolor

""")

        # ── Índice de contenidos ──────────────────────────────────────────────
        f.write(r"""\tableofcontents
\clearpage

""")

        # ── Árbol de archivos ─────────────────────────────────────────────────
        f.write(r"""\chapter{Árbol de Archivos}

""")
        arbol_str = construir_arbol(archivos, raiz)
        f.write("\\begin{terminalbox}[\\faIcon{sitemap}\\ Estructura del proyecto]\n")
        f.write("\\begin{Verbatim}[fontsize=\\small, commandchars=\\\\\\{\\}]\n")
        f.write(_escapar_verbatim(arbol_str))
        f.write("\n\\end{Verbatim}\n")
        f.write("\\end{terminalbox}\n\n")

        # ── Resumen por extensión ─────────────────────────────────────────────
        f.write(r"""\section{Resumen por Extensión}

""")
        conteo_ext  = _resumen_extension(archivos)
        total_lineas_global = 0
        lineas_por_archivo: dict[Path, int] = {}
        for archivo in archivos:
            try:
                n = sum(1 for _ in archivo.open(encoding="utf-8", errors="replace"))
            except Exception:
                n = 0
            lineas_por_archivo[archivo] = n
            total_lineas_global += n

        f.write("\\begin{center}\n")
        f.write("\\rowcolors{2}{tablerow}{white}\n")
        f.write("\\begin{tabular}{lrl}\n")
        f.write("  \\toprule\n")
        f.write("  \\rowcolor{tablehead}\\textcolor{white}{\\textbf{Extensión}} & "
                "\\textcolor{white}{\\textbf{Archivos}} & "
                "\\textcolor{white}{\\textbf{Lenguaje}} \\\\\n")
        f.write("  \\midrule\n")
        for ext, cantidad in conteo_ext.items():
            lang = _ext_to_lang(ext)
            f.write(f"  \\texttt{{{_escapar_latex(ext)}}} & {cantidad} & {_escapar_latex(lang)} \\\\\n")
        f.write("  \\bottomrule\n")
        f.write("\\end{tabular}\n")
        f.write("\\end{center}\n\n")

        total_fmt = f"{total_lineas_global:,}".replace(",", ".")
        f.write(f"\\medskip\n\\textbf{{Total de líneas:}} {total_fmt}\n\n")

        # ── Ficha por archivo ─────────────────────────────────────────────────
        f.write(r"""\chapter{Ficha por Archivo}

""")
        carpeta_actual = None
        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            carpeta  = str(relativo.parent)

            if carpeta != carpeta_actual:
                carpeta_actual = carpeta
                carpeta_display = carpeta if carpeta != "." else "Raíz del proyecto"
                f.write(f"\\section{{\\faIcon{{folder}}\\ \\texttt{{{_escapar_latex(carpeta_display)}}}}}\n\n")

            n_lineas      = lineas_por_archivo.get(archivo, 0)
            importaciones = extraer_importaciones(archivo)
            lang          = _ext_to_lang(archivo.suffix)
            n_lineas_fmt  = f"{n_lineas:,}".replace(",", ".")

            f.write(f"\\begin{{fichabox}}[\\faIcon{{file-code}}\\ {_escapar_latex(archivo.name)}]\n")
            f.write("\\small\n")
            f.write("\\begin{tabular}{@{}ll@{}}\n")
            f.write(f"  \\textbf{{Ruta}} & \\texttt{{{_escapar_latex(relativo.as_posix())}}} \\\\\n")
            f.write(f"  \\textbf{{Extensión}} & \\texttt{{{_escapar_latex(archivo.suffix)}}} \\\\\n")
            f.write(f"  \\textbf{{Lenguaje}} & {_escapar_latex(lang)} \\\\\n")
            f.write(f"  \\textbf{{Líneas}} & {n_lineas_fmt} \\\\\n")

            if importaciones:
                mostrar    = importaciones[:15]
                extras     = len(importaciones) - len(mostrar)
                imp_partes = ", ".join(f"\\texttt{{{_escapar_latex(i)}}}" for i in mostrar)
                if extras > 0:
                    imp_partes += f" \\textcolor{{muted}}{{(+{extras} más)}}"
                f.write(f"  \\textbf{{Importa}} & \\parbox[t]{{10cm}}{{{imp_partes}}} \\\\\n")
            else:
                f.write(f"  \\textbf{{Importa}} & \\textcolor{{muted}}{{(ninguna detectada)}} \\\\\n")

            f.write("\\end{tabular}\n")
            f.write("\\end{fichabox}\n\n")
            f.write("\\medskip\n\n")

        # ── Grafo de dependencias ─────────────────────────────────────────────
        f.write(r"""\chapter{Grafo de Dependencias Internas}

\begin{sectionbox}[\faIcon{info-circle}\ Descripción]
Muestra qué archivos del proyecto se importan entre sí.
Solo se incluyen archivos cuyas dependencias se resolvieron estáticamente.
\end{sectionbox}

\medskip

""")
        dep_lines = _construir_grafo(archivos, raiz)

        if dep_lines:
            f.write("\\begin{longtable}{p{5.5cm}p{8.5cm}}\n")
            f.write("  \\toprule\n")
            f.write("  \\rowcolor{tablehead}\\textcolor{white}{\\textbf{Archivo}} & "
                    "\\textcolor{white}{\\textbf{Depende de}} \\\\\n")
            f.write("  \\midrule\n")
            f.write("  \\endfirsthead\n")
            f.write("  \\toprule\n")
            f.write("  \\rowcolor{tablehead}\\textcolor{white}{\\textbf{Archivo (cont.)}} & "
                    "\\textcolor{white}{\\textbf{Depende de}} \\\\\n")
            f.write("  \\midrule\n")
            f.write("  \\endhead\n")
            f.write("  \\bottomrule\n")
            f.write("  \\endlastfoot\n")

            for i, (rel, deps) in enumerate(dep_lines):
                bg = "\\rowcolor{tablerow}" if i % 2 == 0 else ""
                deps_str = r" \newline ".join(
                    f"\\texttt{{{_escapar_latex(d)}}}" for d in deps
                )
                f.write(f"  {bg}\\texttt{{{_escapar_latex(rel)}}} & {deps_str} \\\\\n")

            f.write("\\end{longtable}\n\n")

            # También árbol de dependencias
            f.write("\\section{Vista en Árbol}\n\n")
            f.write("\\begin{terminalbox}[\\faIcon{project-diagram}\\ Árbol de dependencias]\n")
            f.write("\\begin{Verbatim}[fontsize=\\footnotesize, commandchars=\\\\\\{\\}]\n")
            for rel, deps in dep_lines:
                f.write(f"{_escapar_verbatim(rel)}\n")
                for i, d in enumerate(deps):
                    conector = "└─" if i == len(deps) - 1 else "├─"
                    f.write(f"  {conector} {_escapar_verbatim(d)}\n")
            f.write("\\end{Verbatim}\n")
            f.write("\\end{terminalbox}\n\n")
        else:
            f.write("\\begin{sectionbox}\n")
            f.write("No se detectaron dependencias internas entre los archivos incluidos.\n")
            f.write("\\end{sectionbox}\n\n")

        # ── Commits ───────────────────────────────────────────────────────────
        if commits:
            f.write(r"""\chapter{Historial de Commits}

""")
            f.write("\\begin{center}\n")
            f.write("\\rowcolors{2}{tablerow}{white}\n")
            f.write("\\begin{tabular}{clp{9cm}}\n")
            f.write("  \\toprule\n")
            f.write("  \\rowcolor{tablehead}\\textcolor{white}{\\textbf{\\#}} & "
                    "\\textcolor{white}{\\textbf{Hash}} & "
                    "\\textcolor{white}{\\textbf{Mensaje}} \\\\\n")
            f.write("  \\midrule\n")
            for i, commit in enumerate(commits, 1):
                partes = commit.split(" ", 1)
                if len(partes) == 2:
                    hash_str, mensaje = partes
                    f.write(f"  {i} & \\texttt{{{_escapar_latex(hash_str)}}} & "
                            f"{_escapar_latex(mensaje)} \\\\\n")
                else:
                    f.write(f"  {i} & \\multicolumn{{2}}{{l}}{{\\texttt{{{_escapar_latex(commit)}}}}} \\\\\n")
            f.write("  \\bottomrule\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{center}\n\n")

        # ── Estimación de tokens ──────────────────────────────────────────────
        f.write(r"""\chapter{Estimación de Tokens}

""")
        try:
            texto_total = salida_path.read_text(encoding="utf-8", errors="replace")
            est  = estimar_tokens(texto_total, modelo)
            info = est["info_modelo"]

            f.write("\\begin{center}\n")
            f.write("\\rowcolors{2}{tablerow}{white}\n")
            f.write("\\begin{tabular}{ll}\n")
            f.write("  \\toprule\n")
            f.write("  \\rowcolor{tablehead}\\textcolor{white}{\\textbf{Campo}} & "
                    "\\textcolor{white}{\\textbf{Valor}} \\\\\n")
            f.write("  \\midrule\n")
            f.write(f"  Modelo & {_escapar_latex(info['nombre_display'])} \\\\\n")
            chars_fmt  = f"{est['chars']:,}".replace(",", ".")
            tokens_fmt = f"{est['tokens']:,}".replace(",", ".")
            f.write(f"  Caracteres & {chars_fmt} \\\\\n")
            f.write(f"  Tokens estimados & $\\sim${tokens_fmt} \\\\\n")
            if est["costo_usd"] is not None:
                f.write(f"  Costo estimado & $\\sim$\\${est['costo_usd']:.4f} USD *(solo entrada)* \\\\\n")
            else:
                f.write(f"  Costo estimado & \\textit{{no disponible}} \\\\\n")
            if est["porcentaje_window"] is not None:
                pct    = est["porcentaje_window"]
                cw_fmt = f"{info['context_window']:,}".replace(",", ".")
                if pct <= 85:
                    estado = f"\\textcolor{{success}}{{{pct:.1f}\\% de {cw_fmt} — ✓ entra}}"
                elif pct <= 100:
                    estado = f"\\textcolor{{warning}}{{{pct:.1f}\\% de {cw_fmt} — ⚠ cerca del límite}}"
                else:
                    estado = f"\\textcolor{{danger}}{{{pct:.1f}\\% de {cw_fmt} — ✗ EXCEDE}}"
                f.write(f"  Context window & {estado} \\\\\n")
            f.write("  \\bottomrule\n")
            f.write("\\end{tabular}\n")
            f.write("\\end{center}\n\n")

            f.write("\\begin{sectionbox}[\\faIcon{exclamation-triangle}\\ Nota]\n")
            f.write("Los precios y límites pueden haber cambiado. "
                    "Verificá en la documentación oficial del modelo antes de tomar decisiones de costo.\n")
            f.write("\\end{sectionbox}\n\n")

        except Exception:
            f.write("\\textit{No se pudo calcular la estimación de tokens.}\n\n")
            est = None

        # ── Cierre ────────────────────────────────────────────────────────────
        f.write(r"""
\vfill
\begin{center}
  \textcolor{muted}{\small Generado con \texttt{code\_context} --- """ + _escapar_latex(ts) + r"""}
\end{center}

\end{document}
""")

    return est


def _escapar_verbatim(texto: str) -> str:
    """
    Escapa caracteres que rompen el entorno Verbatim de LaTeX
    cuando se usa commandchars=\\\\\\{\\}.
    """
    # En Verbatim con commandchars, solo \, { y } son especiales
    return (
        texto
        .replace("\\", "\\textbackslash{}")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


# ── Compilación LaTeX ─────────────────────────────────────────────────────────

def compilar_latex(tex_path: Path) -> bool:
    """
    Intenta compilar el archivo .tex a PDF usando pdflatex.

    Comportamiento:
      - Detecta pdflatex en el PATH (Windows, Linux y macOS).
      - Si no está disponible, muestra instrucciones de instalación
        específicas para el sistema operativo y retorna False.
      - Si está disponible, ejecuta dos pasadas (necesario para
        \\tableofcontents y referencias cruzadas).
      - Oculta la ventana de consola de pdflatex en Windows.
      - Aplica un timeout de 120 segundos por pasada para evitar cuelgues.
      - Limpia archivos auxiliares (.aux, .log, .toc, etc.) si la
        compilación fue exitosa y el PDF existe.
      - Retorna True si el PDF fue generado correctamente, False en
        cualquier otro caso.
    """
    pdflatex = shutil.which("pdflatex")

    if pdflatex is None:
        _avisar_latex_no_disponible(tex_path)
        return False

    directorio = tex_path.parent
    nombre_tex = tex_path.name
    pdf_path   = tex_path.with_suffix(".pdf")

    cmd = [
        pdflatex,
        "-shell-escape",
        "-interaction=nonstopmode",
        "-halt-on-error",
        nombre_tex,
    ]

    # Argumentos comunes para subprocess.run
    kwargs: dict = dict(
        cwd=str(directorio),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    # En Windows ocultamos la ventana de consola emergente de pdflatex
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        print("[LaTeX]  Compilando (pasada 1/2 — cuerpo del documento)...")
        r1 = subprocess.run(cmd, **kwargs)
        if r1.returncode != 0:
            print("[ERROR]  La compilación LaTeX falló en la pasada 1.")
            _mostrar_error_latex(r1.stdout)
            print(f"         El archivo .tex está disponible en: {tex_path}")
            return False

        print("[LaTeX]  Compilando (pasada 2/2 — índice de contenidos)...")
        r2 = subprocess.run(cmd, **kwargs)
        if r2.returncode != 0:
            print("[ERROR]  La compilación LaTeX falló en la pasada 2.")
            _mostrar_error_latex(r2.stdout)
            print(f"         El archivo .tex está disponible en: {tex_path}")
            return False

        if not pdf_path.exists():
            print("[ERROR]  pdflatex terminó sin errores pero no se encontró el PDF.")
            print(f"         Revisá el log en: {tex_path.with_suffix('.log')}")
            return False

        _limpiar_auxiliares_latex(tex_path)
        print(f"[OK]     PDF generado: {pdf_path}")
        return True

    except subprocess.TimeoutExpired:
        print("[ERROR]  pdflatex superó el tiempo límite (120 s). Proceso cancelado.")
        print("         Esto puede pasar si falta algún paquete y la instalación")
        print("         automática de MiKTeX quedó esperando interacción.")
        print(f"         El archivo .tex está disponible en: {tex_path}")
        return False
    except FileNotFoundError:
        # Puede ocurrir en una condición de carrera si el binario desaparece
        _avisar_latex_no_disponible(tex_path)
        return False
    except Exception as e:
        print(f"[ERROR]  Error inesperado al compilar LaTeX: {e}")
        print(f"         El archivo .tex está disponible en: {tex_path}")
        return False


def _avisar_latex_no_disponible(tex_path: Path) -> None:
    """
    Muestra un aviso amigable y multiplataforma cuando pdflatex
    no está instalado o no se encuentra en el PATH.
    """
    sistema = platform.system()

    print("")
    print("┌─────────────────────────────────────────────────────────────────┐")
    print("│  ⚠   pdflatex no encontrado — no se puede generar el PDF       │")
    print("└─────────────────────────────────────────────────────────────────┘")
    print("")
    print("  Para compilar el .tex a PDF instalá una distribución LaTeX:")
    print("")

    if sistema == "Windows":
        print("  ┌─ Windows ──────────────────────────────────────────────────────┐")
        print("  │                                                                │")
        print("  │  Opción 1 — MiKTeX  (instala paquetes automáticamente)        │")
        print("  │    https://miktex.org/download                                │")
        print("  │    → Elegí «Install for all users» para evitar problemas      │")
        print("  │      de PATH. Marcá «Install missing packages on-the-fly».    │")
        print("  │                                                                │")
        print("  │  Opción 2 — TeX Live (distribución más completa)              │")
        print("  │    https://tug.org/texlive/windows.html                       │")
        print("  │                                                                │")
        print("  │  Tras instalar, cerrá y volvé a abrir la terminal             │")
        print("  │  para que el PATH se actualice, y ejecutá el script de nuevo. │")
        print("  └────────────────────────────────────────────────────────────────┘")

    elif sistema == "Darwin":
        print("  ┌─ macOS ─────────────────────────────────────────────────────────┐")
        print("  │                                                                 │")
        print("  │  Opción 1 — MacTeX  (instalación completa recomendada)         │")
        print("  │    https://tug.org/mactex/                                     │")
        print("  │                                                                 │")
        print("  │  Opción 2 — Con Homebrew (sin interfaz gráfica):               │")
        print("  │    brew install --cask mactex-no-gui                           │")
        print("  │                                                                 │")
        print("  └─────────────────────────────────────────────────────────────────┘")

    else:  # Linux y otros Unix
        print("  ┌─ Linux ─────────────────────────────────────────────────────────┐")
        print("  │                                                                 │")
        print("  │  Debian / Ubuntu / Mint:                                       │")
        print("  │    sudo apt install texlive-full                               │")
        print("  │                                                                 │")
        print("  │  Fedora / RHEL / Rocky:                                        │")
        print("  │    sudo dnf install texlive-scheme-full                        │")
        print("  │                                                                 │")
        print("  │  Arch / Manjaro:                                               │")
        print("  │    sudo pacman -S texlive-most                                 │")
        print("  │                                                                 │")
        print("  │  (texlive-full / texlive-most incluyen fontawesome5,           │")
        print("  │   tcolorbox y booktabs, requeridos por este documento.)        │")
        print("  └─────────────────────────────────────────────────────────────────┘")

    print("")
    print(f"  El archivo .tex fue guardado correctamente en:")
    print(f"    {tex_path}")
    print("")
    print("  Podés compilarlo manualmente (dos pasadas para el índice):")
    print(f"    pdflatex -shell-escape \"{tex_path.name}\"")
    print(f"    pdflatex -shell-escape \"{tex_path.name}\"")
    print("")


def _mostrar_error_latex(stdout: str) -> None:
    """
    Extrae y muestra las líneas de error del log de pdflatex.
    Los errores de LaTeX comienzan con '!' en el log.
    Si no hay líneas '!', muestra las últimas líneas del log.
    """
    lineas = (stdout or "").splitlines()
    errores = [l for l in lineas if l.startswith("!")]

    if errores:
        print("         Errores detectados en el log:")
        for linea in errores[:6]:
            print(f"           {linea}")
    else:
        # Sin errores explícitos: mostrar las últimas líneas no vacías
        ultimas = [l for l in lineas if l.strip()][-8:]
        if ultimas:
            print("         Últimas líneas del log:")
            for linea in ultimas:
                print(f"           {linea}")


def _limpiar_auxiliares_latex(tex_path: Path) -> None:
    """
    Elimina archivos auxiliares generados por pdflatex tras
    una compilación exitosa. El .tex y el .pdf se conservan.
    """
    stem      = tex_path.stem
    directorio = tex_path.parent
    auxiliares = [
        ".aux", ".log", ".toc", ".out",
        ".fls", ".fdb_latexmk", ".synctex.gz",
        ".nav", ".snm", ".vrb",
    ]
    eliminados = []
    for ext in auxiliares:
        aux = directorio / (stem + ext)
        if aux.exists():
            try:
                aux.unlink()
                eliminados.append(ext)
            except OSError:
                pass  # No crítico: pueden estar bloqueados en Windows
    if eliminados:
        print(f"[LaTeX]  Auxiliares eliminados: {', '.join(eliminados)}")