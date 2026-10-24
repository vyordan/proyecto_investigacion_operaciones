"""Contrato de salida común a todos los algoritmos.

Todos los módulos devuelven un ``Resultado``. La interfaz (Streamlit u otra)
solo necesita saber dibujar este objeto; no conoce los algoritmos.

Convenciones:
- Las fórmulas (``formula``, ``sustitucion``, ``resultado``, ``lineas``) están
  en LaTeX.
- Las figuras son *especificaciones declarativas* (``Figura.datos``): este
  módulo no importa matplotlib; quien dibuja es la interfaz.
"""
from __future__ import annotations

from enum import Enum
from fractions import Fraction
from typing import Any, Literal

from pydantic import BaseModel, Field


class Estado(str, Enum):
    OPTIMO = "optimo"
    MULTIPLES_OPTIMOS = "multiples_optimos"
    INFACTIBLE = "infactible"
    NO_ACOTADO = "no_acotado"
    ERROR_DATOS = "error_datos"
    NO_SOPORTADO = "no_soportado"
    ERROR_INTERNO = "error_interno"


ESTADOS_EXITOSOS = {Estado.OPTIMO, Estado.MULTIPLES_OPTIMOS}


class Advertencia(BaseModel):
    nivel: Literal["info", "aviso", "error"] = "aviso"
    mensaje: str


class Tabla(BaseModel):
    titulo: str = ""
    columnas: list[str]
    filas: list[list[str]]
    # (fila, columna) del elemento pivote; la interfaz resalta también su fila y columna.
    pivote: tuple[int, int] | None = None
    filas_resaltadas: list[int] = Field(default_factory=list)
    celdas_resaltadas: list[tuple[int, int]] = Field(default_factory=list)  # p. ej. asignaciones
    filas_cubiertas: list[int] = Field(default_factory=list)  # líneas del método húngaro
    columnas_cubiertas: list[int] = Field(default_factory=list)
    notas: str = ""


class Figura(BaseModel):
    tipo: Literal["region_factible", "curva_costos", "diente_sierra"]
    titulo: str = ""
    datos: dict[str, Any] = Field(default_factory=dict)


class Paso(BaseModel):
    titulo: str
    explicacion: str = ""
    formula: str = ""
    sustitucion: str = ""
    resultado: str = ""
    lineas: list[str] = Field(default_factory=list)  # bloque de varias líneas LaTeX
    tabla: Tabla | None = None
    tablas: list[Tabla] = Field(default_factory=list)  # tablas adicionales del mismo paso


class Resultado(BaseModel):
    modulo: str
    estado: Estado
    titulo: str
    resumen: str = ""  # respuesta final en una frase
    interpretacion: str = ""
    valores: dict[str, float] = Field(default_factory=dict)
    exactos: dict[str, str] = Field(default_factory=dict)  # '100/3' para valores racionales
    pasos: list[Paso] = Field(default_factory=list)
    figuras: list[Figura] = Field(default_factory=list)
    advertencias: list[Advertencia] = Field(default_factory=list)

    # ---- utilidades --------------------------------------------------------
    @property
    def exitoso(self) -> bool:
        return self.estado in ESTADOS_EXITOSOS

    def advertir(self, mensaje: str, nivel: Literal["info", "aviso", "error"] = "aviso") -> None:
        self.advertencias.append(Advertencia(nivel=nivel, mensaje=mensaje))

    def fijar(self, nombre: str, valor: Fraction | float | int) -> None:
        """Registra un valor numérico (y su forma exacta si es una fracción)."""
        self.valores[nombre] = float(valor)
        if isinstance(valor, Fraction):
            self.exactos[nombre] = str(valor)
