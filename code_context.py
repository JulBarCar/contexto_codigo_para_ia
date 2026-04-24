"""
unificar_codigo.py
Recorre la carpeta del proyecto y unifica todos los archivos de código
en un único archivo de texto, listo para pasar a una IA.

Genera dos archivos:
  1. contexto_codigo.txt  → todo el proyecto (igual que antes)
  2. cambios_git.txt      → solo los archivos modificados desde el último pull

Configuración opcional: crea un archivo '.codigo_config.json' en la raíz
del proyecto para personalizar el comportamiento. Si no existe, funciona
con los valores por defecto.

Ejemplo de .codigo_config.json:
{
    "nombre_salida": "mi_contexto.txt",
    "nombre_salida_cambios": "mis_cambios.txt",
    "extensiones": [".ts", ".tsx", ".js", ".jsx"],
    "ignorar": ["node_modules", ".git", "dist"],
    "incluir_solo": ["src", "hooks", "components"],
    "carpeta_salida": "/ruta/absoluta/a/mi/carpeta_contextos"
}

El campo "carpeta_salida" es opcional. Acepta:
  - Ruta absoluta:  "/home/usuario/contextos"
  - Ruta relativa al proyecto:  "../contextos"
  - Si se omite, se usa la carpeta ".codigo_completo" dentro del proyecto.

Todos los campos son opcionales.
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# ── Valores por defecto ───────────────────────────────────────────────────────

DEFAULT_EXTENSIONES       = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css"}
DEFAULT_IGNORAR           = {"node_modules", ".git", "__pycache__", "dist", ".env"}
DEFAULT_NOMBRE_SALIDA     = "contexto_codigo.txt"
DEFAULT_NOMBRE_CAMBIOS    = "cambios_git.txt"
CARPETA_SALIDA_DEFAULT    = ".codigo_completo"
NOMBRE_CONFIG             = ".codigo_config.json"

# ── Cargar configuración ──────────────────────────────────────────────────────

def cargar_config(raiz: Path) -> dict:
    """
    Busca .codigo_config.json en la raíz del proyecto.
    Devuelve un dict con los valores finales (defaults + overrides del archivo).
    """
    config_path = raiz / NOMBRE_CONFIG
    overrides = {}

    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                overrides = json.load(f)
            print(f"[CONFIG] Usando configuración desde: {config_path.name}")
        except json.JSONDecodeError as e:
            print(f"[AVISO] No se pudo leer {NOMBRE_CONFIG} (JSON inválido: {e}). Usando defaults.")
    else:
        print(f"[CONFIG] No se encontró {NOMBRE_CONFIG}. Usando configuración por defecto.")

    # ── Resolver carpeta de salida ────────────────────────────────────────────
    carpeta_salida_raw = overrides.get("carpeta_salida", None)
    if carpeta_salida_raw:
        carpeta_salida = Path(carpeta_salida_raw)
        # Si es relativa, se resuelve desde la raíz del proyecto
        if not carpeta_salida.is_absolute():
            carpeta_salida = (raiz / carpeta_salida).resolve()
        else:
            carpeta_salida = carpeta_salida.resolve()
    else:
        carpeta_salida = raiz / CARPETA_SALIDA_DEFAULT

    return {
        "extensiones":           set(overrides.get("extensiones",           DEFAULT_EXTENSIONES)),
        "ignorar":               set(overrides.get("ignorar",               DEFAULT_IGNORAR)),
        "nombre_salida":         overrides.get("nombre_salida",             DEFAULT_NOMBRE_SALIDA),
        "nombre_salida_cambios": overrides.get("nombre_salida_cambios",     DEFAULT_NOMBRE_CAMBIOS),
        "incluir_solo":          overrides.get("incluir_solo",              None),
        "carpeta_salida":        carpeta_salida,
    }

# ── Git: archivos modificados ─────────────────────────────────────────────────

def obtener_archivos_modificados(raiz: Path) -> list[Path] | None:
    """
    Devuelve los archivos que cambiaron desde el último pull (ORIG_HEAD vs HEAD).
    Si no hay ORIG_HEAD, usa los cambios no commiteados del working tree.
    Devuelve None si la carpeta no es un repo git.
    """
    def run(cmd: list[str]) -> list[str]:
        result = subprocess.run(cmd, cwd=raiz, capture_output=True, text=True)
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    # Verificar que es un repo git
    check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=raiz, capture_output=True, text=True
    )
    if check.returncode != 0:
        print("[GIT] La carpeta no es un repositorio git. Se omite el archivo de cambios.")
        return None

    # Intentar ORIG_HEAD (existe después de un pull/merge/rebase)
    orig_head = run(["git", "rev-parse", "--verify", "ORIG_HEAD"])
    if orig_head:
        archivos = run(["git", "diff", "--name-only", "--diff-filter=ACMR", "ORIG_HEAD", "HEAD"])
        origen   = "ORIG_HEAD → HEAD (último pull)"
    else:
        # Fallback: cambios staged + unstaged sin commitear
        staged   = run(["git", "diff", "--name-only", "--diff-filter=ACMR", "--cached"])
        unstaged = run(["git", "diff", "--name-only", "--diff-filter=ACMR"])
        archivos = list(dict.fromkeys(staged + unstaged))  # deduplicar preservando orden
        origen   = "working tree (cambios sin commitear)"

    if not archivos:
        print("[GIT] No se detectaron archivos modificados.")
        return []

    print(f"[GIT] {len(archivos)} archivo(s) modificado(s) detectados ({origen})")
    return [raiz / p for p in archivos if (raiz / p).exists()]

# ── Helpers ───────────────────────────────────────────────────────────────────

def debe_ignorar(path: Path, ignorar: set) -> bool:
    return any(parte in ignorar for parte in path.parts)


def en_carpetas_permitidas(path: Path, raiz: Path, incluir_solo: list | None) -> bool:
    if not incluir_solo:
        return True
    try:
        relativo = path.relative_to(raiz)
        return any(relativo.parts[0] == carpeta for carpeta in incluir_solo)
    except ValueError:
        return False


def recolectar_archivos(raiz: Path, config: dict) -> list[Path]:
    archivos = []
    for archivo in sorted(raiz.rglob("*")):
        if not archivo.is_file():
            continue
        if debe_ignorar(archivo.relative_to(raiz), config["ignorar"]):
            continue
        if not en_carpetas_permitidas(archivo, raiz, config["incluir_solo"]):
            continue
        if archivo.suffix in config["extensiones"]:
            archivos.append(archivo)
    return archivos


def filtrar_por_config(archivos: list[Path], raiz: Path, config: dict) -> list[Path]:
    """Filtra una lista de paths aplicando las mismas reglas de extensión/ignorar/incluir_solo."""
    resultado = []
    for archivo in archivos:
        if not archivo.is_file():
            continue
        try:
            rel = archivo.relative_to(raiz)
        except ValueError:
            continue
        if debe_ignorar(rel, config["ignorar"]):
            continue
        if not en_carpetas_permitidas(archivo, raiz, config["incluir_solo"]):
            continue
        if archivo.suffix in config["extensiones"]:
            resultado.append(archivo)
    return resultado


def construir_arbol(archivos: list[Path], raiz: Path) -> str:
    lineas = [f"{raiz.resolve().name}/"]
    directorios_vistos = set()

    for archivo in archivos:
        relativo = archivo.relative_to(raiz)
        partes   = relativo.parts

        for i, parte in enumerate(partes[:-1]):
            clave = partes[: i + 1]
            if clave not in directorios_vistos:
                directorios_vistos.add(clave)
                lineas.append(f"{'  ' * (i + 1)}{parte}/")

        lineas.append(f"{'  ' * len(partes)}{partes[-1]}")

    return "\n".join(lineas)


def escribir_archivo(
    salida_path: Path,
    archivos: list[Path],
    raiz: Path,
    config: dict,
    titulo: str,
    nota_extra: str = "",
) -> None:
    """Escribe un archivo de contexto con encabezado, árbol y contenido."""
    separador = "=" * 72

    with open(salida_path, "w", encoding="utf-8") as f:
        f.write(f"# Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# {titulo}\n")
        f.write(f"# Carpeta origen: {raiz}\n")
        f.write(f"# Extensiones incluidas: {', '.join(sorted(config['extensiones']))}\n")
        f.write(f"# Ignorados: {', '.join(sorted(config['ignorar']))}\n")
        if config["incluir_solo"]:
            f.write(f"# Carpetas incluidas: {', '.join(config['incluir_solo'])}\n")
        if nota_extra:
            f.write(f"# {nota_extra}\n")
        f.write(f"# Total de archivos: {len(archivos)}\n")
        f.write("\n")

        f.write(f"# {separador}\n")
        f.write("# ÁRBOL DE ARCHIVOS\n")
        f.write(f"# {separador}\n\n")
        f.write(construir_arbol(archivos, raiz))
        f.write("\n\n")

        f.write(f"# {separador}\n")
        f.write("# CONTENIDO\n")
        f.write(f"# {separador}\n")

        for archivo in archivos:
            relativo = archivo.relative_to(raiz)
            f.write(f"\n\n# --- {relativo} ---\n\n")
            try:
                contenido = archivo.read_text(encoding="utf-8", errors="replace")
                f.write(contenido)
                if not contenido.endswith("\n"):
                    f.write("\n")
            except Exception as e:
                f.write(f"# [No se pudo leer el archivo: {e}]\n")

# ── Función principal ─────────────────────────────────────────────────────────

def unificar(carpeta_origen: str = ".") -> None:
    raiz = Path(carpeta_origen).resolve()

    if not raiz.exists():
        print(f"[ERROR] La carpeta '{raiz}' no existe.")
        sys.exit(1)

    config     = cargar_config(raiz)
    salida_dir = config["carpeta_salida"]

    try:
        salida_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[ERROR] No se pudo crear la carpeta de salida '{salida_dir}': {e}")
        sys.exit(1)

    print(f"[CONFIG] Carpeta de salida: {salida_dir}")

    # ── Archivo 1: contexto completo ──────────────────────────────────────────
    todos = recolectar_archivos(raiz, config)

    if not todos:
        print("[AVISO] No se encontraron archivos con las extensiones configuradas.")
        return

    salida_completa = salida_dir / config["nombre_salida"]
    escribir_archivo(
        salida_path=salida_completa,
        archivos=todos,
        raiz=raiz,
        config=config,
        titulo="CONTEXTO COMPLETO DEL PROYECTO",
    )
    print(f"[OK] Contexto completo → {salida_completa}  ({len(todos)} archivos)")

    # ── Archivo 2: solo cambios git ───────────────────────────────────────────
    modificados_raw = obtener_archivos_modificados(raiz)

    if modificados_raw is None:
        # No es repo git
        return

    if not modificados_raw:
        print("[OK] Sin cambios detectados, no se genera archivo de cambios.")
        return

    modificados = filtrar_por_config(modificados_raw, raiz, config)

    if not modificados:
        print("[OK] Los archivos modificados no coinciden con las extensiones/carpetas configuradas.")
        return

    salida_cambios = salida_dir / config["nombre_salida_cambios"]
    lista_nombres  = ", ".join(str(m.relative_to(raiz)) for m in modificados)
    escribir_archivo(
        salida_path=salida_cambios,
        archivos=modificados,
        raiz=raiz,
        config=config,
        titulo="ARCHIVOS MODIFICADOS DESDE EL ÚLTIMO PULL",
        nota_extra=f"Archivos modificados: {lista_nombres}",
    )
    print(f"[OK] Cambios git       → {salida_cambios}  ({len(modificados)} archivos)")

# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    origen = sys.argv[1] if len(sys.argv) > 1 else "."
    unificar(origen)