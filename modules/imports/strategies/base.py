"""
modules/imports/strategies/base.py
Contrato que debe cumplir toda strategy de extracción de importaciones.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class ImportStrategy(ABC):
    """
    Interfaz común para todos los extractores de importaciones.

    Cada subclase es responsable de:
      1. Declarar qué extensiones maneja  → soporta()
      2. Extraer los especificadores crudos del texto fuente → extraer()

    El texto ya viene leído por el contexto (ExtractorImportaciones),
    así que las strategies no tocan el disco salvo para resolver
    rutas relativas (caso Python).
    """

    @abstractmethod
    def soporta(self, archivo: Path) -> bool:
        """
        Devuelve True si esta strategy puede procesar el archivo dado.
        Se evalúa normalmente por sufijo, pero puede usar cualquier criterio.
        """
        ...

    @abstractmethod
    def extraer(self, archivo: Path, texto: str) -> list[str]:
        """
        Devuelve la lista de strings de importación crudos presentes en `texto`.
        No desduplicar aquí: el contexto aplica dict.fromkeys() al final.
        """
        ...