"""
modules/imports/strategies/vue_strategy.py
Extracción de importaciones para archivos .vue (Vue SFC) — nivel producción.

Fuentes cubiertas:
  1. Bloque <script> / <script setup> — lógica JS/TS completa heredada.
  2. Tags de componentes en <template> — heurística PascalCase / kebab-case.
  3. Mapa de auto-imports — lee components.d.ts generado por
     unplugin-vue-components (Vite) o .nuxt/components.d.ts (Nuxt)
     y resuelve el nombre del componente a su ruta real.
"""

import re
from functools import cached_property
from pathlib import Path

from .js_strategy import JsStrategy


class VueStrategy(JsStrategy):
    """
    Extrae importaciones de archivos Vue SFC (.vue) a nivel producción.

    Jerarquía de fuentes (de más a menos confiable):
      1. imports explícitos del bloque <script>      → rutas exactas
      2. auto-imports resueltos via components.d.ts  → rutas exactas
      3. tags del <template> sin resolver            → nombres PascalCase
         (resolver_importacion los descartará si no existen en el índice)

    Detección de components.d.ts
    ────────────────────────────
    Se busca en este orden hasta encontrar el primero que exista:
      • <raiz>/.nuxt/components.d.ts      (Nuxt 3)
      • <raiz>/components.d.ts            (unplugin-vue-components / Vite)
      • <raiz>/src/components.d.ts        (estructura src/ alternativa)

    El archivo se parsea una sola vez por instancia de VueStrategy
    (cached_property) y se comparte entre todos los archivos del proyecto.
    Si no existe ninguno de los candidatos, la instancia opera como antes
    (solo heurística de template) sin lanzar errores.

    Formato esperado de components.d.ts
    ─────────────────────────────────────
    El archivo contiene declaraciones como:

        // unplugin-vue-components / Vite
        declare module '@vue/runtime-core' {
          export interface GlobalComponents {
            MyButton: typeof import('./src/components/MyButton.vue')['default']
            RouterView: typeof import('vue-router')['RouterView']
          }
        }

        // Nuxt 3
        declare module 'vue' {
          interface GlobalComponents {
            NuxtLink: typeof import('../node_modules/nuxt/dist/...')['default']
            MyCard: typeof import('../components/MyCard.vue')['default']
          }
        }

    Solo se extraen entradas cuya ruta apunte a un archivo .vue, .ts o .js
    dentro del proyecto (se descartan las de node_modules y las externas).
    """

    EXTENSIONES: frozenset[str] = frozenset({".vue"})

    _PATRON_SCRIPT = re.compile(
        r"<script[^>]*>([\s\S]*?)</script>",
        re.IGNORECASE,
    )
    _PATRON_TEMPLATE = re.compile(
        r"<template[^>]*>([\s\S]*?)</template>",
        re.IGNORECASE,
    )
    # Tags PascalCase (MyComponent) o kebab-case con guion (my-component).
    # Excluye tags HTML nativos en minúsculas sin guion.
    _PATRON_COMPONENT_TAG = re.compile(
        r"<([A-Z][A-Za-z0-9]*|[a-z][a-z0-9]*(?:-[a-z0-9]+)+)"
        r"(?:\s|/?>)"
    )
    # Línea de components.d.ts:
    #   MyButton: typeof import('./src/components/MyButton.vue')['default']
    _PATRON_DTS_ENTRY = re.compile(
        r"""^\s{4,}(\w+)\s*:\s*typeof\s+import\(['"]([^'"]+)['"]\)""",
        re.MULTILINE,
    )
    # Candidatos de components.d.ts a ignorar (librerías externas conocidas)
    _PREFIJOS_EXTERNOS: tuple[str, ...] = (
        "vue-router",
        "vue-i18n",
        "@vueuse",
        "@headlessui",
        "@heroicons",
        "primevue",
        "naive-ui",
        "element-plus",
        "ant-design-vue",
        "vuetify",
        "quasar",
    )
    _TAGS_HTML_NATIVOS: frozenset[str] = frozenset({
        "accept-charset",
        "http-equiv",
        "annotation-xml",
    })

    # ── Constructor ───────────────────────────────────────────────────────────

    def __init__(self, raiz: Path | None = None) -> None:
        """
        Args:
            raiz: directorio raíz del proyecto. Necesario para localizar
                  components.d.ts. Si es None, se desactiva el auto-import.
        """
        self._raiz = raiz

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        # 1. Imports explícitos del bloque <script>
        script_body   = self._extraer_script(texto)
        imports_script = self._extraer_especificadores(self._sanitizar(script_body))
        vistos         = set(imports_script)

        # 2. Auto-imports resueltos (rutas reales desde components.d.ts)
        imports_auto: list[str] = []
        if self._raiz is not None:
            mapa = self._mapa_autoimports
            candidatos_tpl = self._extraer_nombres_template(texto)
            for nombre in candidatos_tpl:
                if nombre in mapa and mapa[nombre] not in vistos:
                    imports_auto.append(mapa[nombre])
                    vistos.add(mapa[nombre])

        # 3. Candidatos heurísticos del template que no resolvió el mapa
        mapa_disponible  = self._mapa_autoimports if self._raiz else {}
        candidatos_extra = [
            nombre
            for nombre in self._extraer_nombres_template(texto)
            if nombre not in mapa_disponible and nombre not in vistos
        ]

        return imports_script + imports_auto + candidatos_extra

    # ── Auto-import map (cargado una sola vez por instancia) ──────────────────

    @cached_property
    def _mapa_autoimports(self) -> dict[str, str]:
        """
        Devuelve { 'MyButton': './src/components/MyButton.vue', ... }.
        Solo incluye rutas internas al proyecto (descarta node_modules y externos).
        Retorna {} si no se encuentra ningún components.d.ts.
        """
        if self._raiz is None:
            return {}

        dts = self._encontrar_dts()
        if dts is None:
            return {}

        try:
            contenido = dts.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {}

        mapa: dict[str, str] = {}
        for m in self._PATRON_DTS_ENTRY.finditer(contenido):
            nombre = m.group(1)
            ruta   = m.group(2)

            # Descartar librerías externas conocidas
            if any(ruta.startswith(p) for p in self._PREFIJOS_EXTERNOS):
                continue
            # Descartar node_modules
            if "node_modules" in ruta:
                continue
            # Solo archivos con extensión relevante
            if not ruta.endswith((".vue", ".ts", ".js", ".tsx", ".jsx")):
                continue

            mapa[nombre] = ruta

        return mapa

    def _encontrar_dts(self) -> Path | None:
        """Busca components.d.ts en los candidatos estándar."""
        candidatos = [
            self._raiz / ".nuxt" / "components.d.ts",        # Nuxt 3
            self._raiz / "components.d.ts",                  # Vite / unplugin
            self._raiz / "src" / "components.d.ts",          # estructura src/
        ]
        for c in candidatos:
            if c.exists():
                return c
        return None

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _extraer_script(self, texto: str) -> str:
        """Concatena el contenido de todos los bloques <script>."""
        return "\n".join(self._PATRON_SCRIPT.findall(texto))

    def _extraer_nombres_template(self, texto: str) -> list[str]:
        """
        Extrae nombres de componentes (PascalCase) del bloque <template>.
        Convierte kebab-case → PascalCase para unificar con el mapa.
        """
        bloque = self._PATRON_TEMPLATE.search(texto)
        if not bloque:
            return []

        nombres: list[str] = []
        for m in self._PATRON_COMPONENT_TAG.finditer(bloque.group(1)):
            tag = m.group(1)
            if tag in self._TAGS_HTML_NATIVOS:
                continue
            nombres.append(self._a_pascal_case(tag))

        return list(dict.fromkeys(nombres))

    @staticmethod
    def _a_pascal_case(nombre: str) -> str:
        """'my-component' → 'MyComponent'. 'MyComponent' → 'MyComponent'."""
        if "-" in nombre:
            return "".join(p.capitalize() for p in nombre.split("-"))
        return nombre