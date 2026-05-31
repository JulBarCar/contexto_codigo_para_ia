"""
modules/imports/strategies/swift_strategy.py
Extracción de importaciones para archivos .swift (Swift) — nivel producción.

NOTA: El archivo original era una copia accidental de kotlin_strategy.py
y no procesaba Swift en absoluto. Este es el reemplazo correcto.

Cubre:
  • import Foundation                  (framework de Apple / stdlib)
  • import UIKit                       (framework UIKit)
  • import MyModule                    (módulo del proyecto)
  • import class Foundation.NSObject  (import de tipo específico)
  • import func Darwin.C.abs          (import de función)
  • import var Foundation.NSNotFound  (import de variable)
  • @testable import MyModule          (import de testing)
  • #if canImport(UIKit)               (import condicional → __conditional__)
  •   import UIKit
  • #endif

Resolución de módulos del proyecto:
  Lee Package.swift para obtener los targets del paquete y mapea los
  imports a rutas físicas de archivo buscando en Sources/<TargetName>/.
  Si no hay Package.swift, busca en Sources/ y src/ como fallback.

  Para proyectos Xcode (.xcodeproj / .xcworkspace), la resolución es
  best-effort ya que la estructura de grupos no se puede leer sin las
  herramientas de Xcode; se emite el nombre del módulo como fallback.
"""

import re
from functools import cached_property
from pathlib import Path

from .base import ImportStrategy

_CONDITIONAL_SUFFIX = "__conditional__"


class SwiftStrategy(ImportStrategy):

    EXTENSIONES: frozenset[str] = frozenset({".swift"})

    # Frameworks y módulos de Apple que nunca existen como archivos del proyecto
    _MODULOS_APPLE: frozenset[str] = frozenset({
        "ABI", "AVFoundation", "AppKit", "AppTrackingTransparency",
        "AuthenticationServices", "CFNetwork", "CallKit", "CloudKit",
        "Combine", "CoreBluetooth", "CoreData", "CoreFoundation",
        "CoreGraphics", "CoreImage", "CoreLocation", "CoreML",
        "CoreMotion", "CoreNFC", "CoreSpotlight", "CoreTelephony",
        "CoreText", "CoreVideo", "CryptoKit", "Darwin",
        "EventKit", "ExposureNotification",
        "Foundation", "GameKit", "HealthKit", "HomeKit",
        "MapKit", "MessageUI", "MetalKit", "ModelIO",
        "MultipeerConnectivity", "NaturalLanguage", "NetworkExtension",
        "ObjectiveC", "PDFKit", "PassKit", "Photos", "PhotosUI",
        "PushKit", "QuickLook", "RealityKit", "ReplayKit",
        "SafariServices", "SceneKit", "Social", "SpriteKit",
        "StoreKit", "SwiftUI", "SystemConfiguration", "TVML", "TVMLKit",
        "TVUIKit", "UIKit", "UserNotifications", "VideoSubscriberAccount",
        "Vision", "WKWebView", "WatchConnectivity", "WebKit",
        "XCTest", "iAd", "os", "simd", "Swift", "SwiftShims",
        # Swift stdlib
        "Dispatch", "Darwin",
        # Paquetes comunes de terceros no locales
        "Alamofire", "Moya", "Kingfisher", "Lottie", "RxSwift",
        "Combine", "SnapKit", "Then",
    })

    _PATRON_IMPORT = re.compile(
        r"""^[ \t]*(?:@\w+\s+)?import\s+"""
        r"""(?:class|struct|enum|protocol|typealias|func|var|let\s+)?"""
        r"""([\w.]+)""",
        re.MULTILINE,
    )
    _PATRON_IF_OPEN  = re.compile(
        r"""^\s*#if\s+(?:canImport|os|swift|targetEnvironment)\s*\(""",
        re.MULTILINE,
    )
    _PATRON_IF_CLOSE = re.compile(r"""^\s*#endif\b""", re.MULTILINE)

    # Nombre del target en Package.swift
    _PATRON_TARGET_NAME = re.compile(
        r'\\.(?:target|testTarget|executableTarget)\s*\([\s\S]*?name\s*:\s*"([^"]+)"'
    )

    def __init__(self, raiz: Path | None = None) -> None:
        self._raiz = raiz

    def soporta(self, archivo: Path) -> bool:
        return archivo.suffix in self.EXTENSIONES

    def extraer(self, archivo: Path, texto: str) -> list[str]:
        raiz = self._raiz or self._detectar_raiz(archivo)

        limpio = re.sub(r"/\*[\s\S]*?\*/", " ", texto)
        limpio = re.sub(r"//[^\n]*", "", limpio)

        condicionales = self._rangos_condicionales(limpio)
        resultado: list[str] = []

        for m in self._PATRON_IMPORT.finditer(limpio):
            modulo = m.group(1)
            # Ignorar módulo raíz de imports calificados (import class Foo.Bar → "Foo")
            # El módulo relevante es el primero (antes del primer punto)
            modulo_raiz = modulo.split(".")[0]

            es_condicional = self._es_condicional(m.start(), condicionales)

            if modulo_raiz in self._MODULOS_APPLE:
                # Framework de Apple → emitir as-is (no hay archivo en disco)
                entrada = modulo_raiz + (_CONDITIONAL_SUFFIX if es_condicional else "")
                resultado.append(entrada)
                continue

            # Módulo candidato a ser del proyecto → intentar resolver
            if raiz is not None:
                resuelto = self._resolver(modulo_raiz, raiz, archivo)
            else:
                resuelto = modulo_raiz

            if es_condicional:
                resuelto = resuelto + _CONDITIONAL_SUFFIX
            resultado.append(resuelto)

        return resultado

    # ── Resolución de módulos del proyecto ────────────────────────────────────

    def _resolver(self, modulo: str, raiz: Path, archivo: Path) -> str:
        """
        Busca el módulo en Sources/<modulo>/ (convención SPM) y en src/.
        Si encuentra el directorio del target, devuelve una ruta relativa
        al primer archivo Swift del target.
        """
        # SPM: Sources/<TargetName>/
        candidatos_dir = [
            raiz / "Sources" / modulo,
            raiz / "src" / modulo,
            raiz / modulo,
        ]
        for dir_target in candidatos_dir:
            if dir_target.is_dir():
                # Buscar el archivo principal del módulo (mismo nombre o cualquier .swift)
                for nombre in (f"{modulo}.swift", "main.swift", "__init__.swift"):
                    f = dir_target / nombre
                    if f.exists():
                        try:
                            return f.relative_to(raiz).as_posix()
                        except ValueError:
                            return str(f).replace("\\", "/")
                # Emitir el directorio si no hay archivo principal
                try:
                    return dir_target.relative_to(raiz).as_posix()
                except ValueError:
                    pass

        return modulo  # no encontrado → emitir nombre del módulo

    # ── Targets de Package.swift ──────────────────────────────────────────────

    @cached_property
    def _targets_spm(self) -> list[str]:
        """Devuelve los nombres de targets declarados en Package.swift."""
        if self._raiz is None:
            return []
        pkg_swift = self._raiz / "Package.swift"
        if not pkg_swift.exists():
            return []
        try:
            contenido = pkg_swift.read_text(encoding="utf-8", errors="replace")
            return self._PATRON_TARGET_NAME.findall(contenido)
        except Exception:
            return []

    # ── Detección de bloques condicionales ────────────────────────────────────

    def _rangos_condicionales(self, texto: str) -> list[tuple[int, int]]:
        rangos: list[tuple[int, int]] = []
        pila:   list[int] = []
        for m in re.finditer(
            r"""^\s*#(?:(if\b)|(endif)\b)""",
            texto,
            re.MULTILINE,
        ):
            if m.group(1):
                pila.append(m.start())
            elif m.group(2) and pila:
                inicio = pila.pop()
                rangos.append((inicio, m.end()))
        return rangos

    @staticmethod
    def _es_condicional(pos: int, rangos: list[tuple[int, int]]) -> bool:
        return any(inicio <= pos <= fin for inicio, fin in rangos)

    # ── Detección de raíz ─────────────────────────────────────────────────────

    def _detectar_raiz(self, archivo: Path) -> Path | None:
        """Sube hasta encontrar Package.swift, .xcodeproj o .xcworkspace."""
        actual = archivo.parent
        for _ in range(20):
            if (
                (actual / "Package.swift").exists()
                or any(actual.glob("*.xcodeproj"))
                or any(actual.glob("*.xcworkspace"))
            ):
                return actual
            padre = actual.parent
            if padre == actual:
                break
            actual = padre
        return None