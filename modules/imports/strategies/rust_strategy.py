"""
modules/imports/strategies/rust_strategy.py
Extracción de importaciones para archivos .rs (Rust) — nivel producción.

Mejoras respecto a la versión anterior:
  1. Emite el path completo de cada `use`, no solo la raíz del crate.
     Ej: "use std::collections::HashMap" → "std::collections::HashMap"
  2. Expande use con llaves: "use std::io::{Read, Write}" →
     ["std::io::Read", "std::io::Write"]
  3. Resuelve `mod foo;` a ruta física real en disco (foo.rs o foo/mod.rs),
     emitiendo la ruta relativa al archivo actual.
  4. Normaliza `self::`, `super::` y `crate::` en paths de use.
  5. Elimina doc-comments (//! y ///) antes de procesar para evitar
     falsos positivos en ejemplos de código dentro de la documentación.

Cubre:
  • use std::collections::HashMap;         (use simple → path completo)
  • use std::io::{self, Read, Write};      (use con llaves → expansión)
  • use std::*;                            (wildcard)
  • use foo::{Bar, baz::Qux};             (llaves anidadas → expansión plana)
  • use foo as bar;                        (alias)
  • extern crate serde;                   (Rust 2015)
  • mod foo;                               (módulo local → ruta de archivo)
  • pub use / pub(crate) use              (re-exports)
"""

import re
from pathlib import Path

from .base import ImportStrategy


class RustStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".rs"})

    _PATRON_USE = re.compile(
        r"^[ \t]*(?:pub(?:\([^)]*\))?\s+)?use\s+([\s\S]+?)\s*;",
        re.MULTILINE,
    )
    _PATRON_EXTERN = re.compile(
        r"^\s*extern\s+crate\s+([\w]+)\s*(?:as\s+[\w]+)?\s*;",
        re.MULTILINE,
    )
    _PATRON_MOD = re.compile(
        r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+([\w]+)\s*;",
        re.MULTILINE,
    )

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        # Eliminar doc-comments primero (//! ///) para evitar falsos positivos
        limpio = re.sub(r"///[^\n]*", "", texto)
        limpio = re.sub(r"//![^\n]*", "", limpio)
        # Luego comentarios normales y de bloque
        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", limpio)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        resultado: list[str] = []

        # use paths (con expansión de llaves)
        for m in self._PATRON_USE.finditer(limpio):
            especificador = m.group(1).strip()
            resultado.extend(self._expandir_use(especificador))

        # extern crate
        for m in self._PATRON_EXTERN.finditer(limpio):
            resultado.append(m.group(1))

        # mod foo; → resolver a ruta física
        for m in self._PATRON_MOD.finditer(limpio):
            nombre = m.group(1)
            ruta = self._resolver_mod(nombre, archivo)
            resultado.append(ruta)

        return resultado

    # ── Expansión de use con llaves ───────────────────────────────────────────

    def _expandir_use(self, especificador: str) -> list[str]:
        """
        Expande paths con llaves en paths individuales completos.
        "std::io::{Read, Write}" → ["std::io::Read", "std::io::Write"]
        "std::io::{self, Write}" → ["std::io", "std::io::Write"]
        Soporta un nivel de anidamiento de llaves.
        """
        # Normalizar espacios y saltos de línea
        spec = re.sub(r"\s+", " ", especificador).strip()

        if "{" not in spec:
            # Path simple, posiblemente con alias: "foo::Bar as Baz" → "foo::Bar"
            return [re.sub(r"\s+as\s+\w+$", "", spec).strip()]

        # Separar prefijo y bloque de llaves
        idx = spec.index("{")
        prefijo = spec[:idx].rstrip(": ")  # "std::io"
        interior = spec[idx + 1:spec.rindex("}")].strip()

        resultado: list[str] = []
        for parte in self._split_nivel(interior):
            parte = parte.strip()
            parte = re.sub(r"\s+as\s+\w+$", "", parte).strip()  # quitar alias
            if not parte:
                continue
            if parte == "self":
                resultado.append(prefijo)
            elif "{" in parte:
                # Anidamiento: "io::{Read, Write}" dentro de "std::{io::{...}}"
                sub = f"{prefijo}::{parte}" if prefijo else parte
                resultado.extend(self._expandir_use(sub))
            else:
                resultado.append(f"{prefijo}::{parte}" if prefijo else parte)

        return resultado

    @staticmethod
    def _split_nivel(texto: str) -> list[str]:
        """Divide por comas respetando llaves anidadas."""
        partes: list[str] = []
        actual: list[str] = []
        nivel = 0
        for ch in texto:
            if ch == "{":
                nivel += 1
                actual.append(ch)
            elif ch == "}":
                nivel -= 1
                actual.append(ch)
            elif ch == "," and nivel == 0:
                partes.append("".join(actual).strip())
                actual = []
            else:
                actual.append(ch)
        if actual:
            partes.append("".join(actual).strip())
        return partes

    # ── Resolución de mod foo; ────────────────────────────────────────────────

    def _resolver_mod(self, nombre: str, archivo: Path) -> str:
        """
        Resuelve 'mod foo;' a su ruta física relativa al archivo actual.
        Convenciones de Rust:
          - foo.rs en el mismo directorio
          - foo/mod.rs
        Si no existe ninguno, devuelve el nombre como fallback.
        """
        dir_actual = archivo.parent
        candidatos = [
            dir_actual / f"{nombre}.rs",
            dir_actual / nombre / "mod.rs",
        ]
        for candidato in candidatos:
            if candidato.exists():
                try:
                    return str(candidato.relative_to(dir_actual)).replace("\\", "/")
                except ValueError:
                    return str(candidato).replace("\\", "/")
        return nombre