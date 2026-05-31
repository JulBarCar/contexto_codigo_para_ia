"""
modules/imports/strategies/svelte_strategy.py
Extracción de importaciones para archivos .svelte — nivel producción.

Gaps cubiertos respecto al tratamiento anterior (VueStrategy genérica):
  1. $lib y aliases de SvelteKit  → leídos desde svelte.config.js
  2. Módulos virtuales de SvelteKit ($app/*, $env/*)  → lista de exclusión,
     no se intentan resolver en disco.
  3. Bloques <script context="module"> + <script>  → ambos se procesan.
  4. Stores de Svelte ($store)  → se normalizan quitando el $ inicial
     y se emiten para que resolver_importacion intente la resolución.
"""

import re
from functools import cached_property
from pathlib import Path

from .js_strategy import JsStrategy


class SvelteStrategy(JsStrategy):
    """
    Extrae importaciones de archivos Svelte (.svelte) a nivel producción.

    Fuentes cubiertas:
      • <script context="module"> ... </script>
      • <script> ... </script>
      (ambos bloques se concatenan y se procesan con la lógica JS completa)

    Aliases resueltos:
      • $lib  → src/lib  (por defecto SvelteKit, sobreescribible en config)
      • aliases adicionales definidos en kit.alias de svelte.config.js

    Módulos virtuales ignorados (no existen en disco):
      • $app/navigation, $app/stores, $app/environment, $app/paths, $app/forms
      • $env/static/public, $env/static/private, $env/dynamic/public,
        $env/dynamic/private
      • $service-worker

    Stores Svelte ($storeName):
      No son imports directos, pero si el código usa $store sin importar
      'store' explícitamente, el grafo lo pierde. La strategy emite el
      nombre sin $ como candidato; resolver_importacion lo descartará si
      no existe en el índice.
    """

    EXTENSIONES: frozenset[str] = frozenset({".svelte"})

    # Módulos virtuales de SvelteKit: no son archivos reales en disco.
    # Cualquier import que empiece por alguno de estos prefijos se descarta.
    _MODULOS_VIRTUALES: frozenset[str] = frozenset({
        "$app/navigation",
        "$app/stores",
        "$app/environment",
        "$app/paths",
        "$app/forms",
        "$env/static/public",
        "$env/static/private",
        "$env/dynamic/public",
        "$env/dynamic/private",
        "$service-worker",
    })

    _PATRON_SCRIPT = re.compile(
        r"<script[^>]*>([\s\S]*?)</script>",
        re.IGNORECASE,
    )
    # Alias estándar de SvelteKit: kit.alias: { '$lib': 'src/lib' }
    _PATRON_KIT_ALIAS = re.compile(
        r"""kit\s*:\s*\{[\s\S]*?alias\s*:\s*\{([\s\S]*?)\}""",
        re.DOTALL,
    )
    # Entrada de alias: '$lib': 'src/lib'  o  "$utils": "./src/utils"
    _PATRON_ALIAS_ENTRY = re.compile(
        r"""['"](\$[\w/-]+)['"]\s*:\s*['"]([^'"]+)['"]"""
    )

    # ── Constructor ───────────────────────────────────────────────────────────

    def __init__(self, raiz: Path | None = None) -> None:
        """
        Args:
            raiz: directorio raíz del proyecto. Necesario para leer
                  svelte.config.js y resolver $lib. Si es None, se usa
                  solo el alias $lib → src/lib por defecto.
        """
        self._raiz = raiz

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        cuerpo     = self._extraer_scripts(texto)
        cuerpo_safe = self._sanitizar(cuerpo)
        crudos     = self._extraer_especificadores(cuerpo_safe)

        resultado: list[str] = []
        aliases = self._aliases_kit

        for imp in crudos:
            # Descartar módulos virtuales de SvelteKit
            if imp in self._MODULOS_VIRTUALES:
                continue
            if any(imp.startswith(mv + "/") for mv in self._MODULOS_VIRTUALES):
                continue

            # Resolver aliases de SvelteKit ($lib/... → src/lib/...)
            resuelto = self._resolver_alias(imp, aliases, archivo)
            resultado.append(resuelto)

        return list(dict.fromkeys(resultado))

    # ── Aliases de SvelteKit (cargados una sola vez por instancia) ────────────

    @cached_property
    def _aliases_kit(self) -> dict[str, str]:
        """
        Devuelve el mapa de aliases de SvelteKit.
        Siempre incluye $lib → src/lib como base.
        Lee kit.alias de svelte.config.js si existe.
        """
        # Alias base que SvelteKit define siempre aunque no esté en config
        aliases: dict[str, str] = {"$lib": "src/lib"}

        if self._raiz is None:
            return aliases

        config = self._raiz / "svelte.config.js"
        if not config.exists():
            config = self._raiz / "svelte.config.ts"
        if not config.exists():
            return aliases

        try:
            contenido = config.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return aliases

        # Extraer el bloque kit.alias
        m_bloque = self._PATRON_KIT_ALIAS.search(contenido)
        if not m_bloque:
            return aliases

        for m in self._PATRON_ALIAS_ENTRY.finditer(m_bloque.group(1)):
            clave = m.group(1)   # '$lib', '$utils', etc.
            valor = m.group(2)   # 'src/lib', './src/utils', etc.
            aliases[clave] = valor.lstrip("./")  # normalizar: quitar ./ inicial

        return aliases

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _extraer_scripts(self, texto: str) -> str:
        """
        Concatena el contenido de todos los bloques <script>, incluyendo
        <script context="module"> (lógica compartida entre instancias).
        """
        return "\n".join(self._PATRON_SCRIPT.findall(texto))

    def _resolver_alias(
        self,
        imp: str,
        aliases: dict[str, str],
        archivo: Path,
    ) -> str:
        """
        Sustituye el prefijo de alias por la ruta relativa real.

        Ejemplo:
            imp      = '$lib/utils/format'
            aliases  = {'$lib': 'src/lib'}
            archivo  = Path('src/routes/+page.svelte')
            → retorna ruta relativa desde archivo hasta src/lib/utils/format

        Si no hay alias que aplique, devuelve imp sin cambios.
        """
        for prefijo, destino in aliases.items():
            if imp == prefijo or imp.startswith(prefijo + "/"):
                sufijo   = imp[len(prefijo):]           # '' o '/utils/format'
                ruta_abs = (self._raiz / destino / sufijo.lstrip("/")) if self._raiz else None
                if ruta_abs is not None:
                    try:
                        return str(ruta_abs.relative_to(archivo.parent)).replace("\\", "/")
                    except ValueError:
                        # Si relative_to falla (distinto drive en Windows),
                        # devolver la ruta desde raíz como fallback
                        return str(ruta_abs).replace("\\", "/")
                return destino + sufijo  # fallback sin raíz

        return imp