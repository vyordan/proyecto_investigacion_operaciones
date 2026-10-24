"""Esquemas Pydantic (contratos de entrada) de cada módulo.

Hay dos capas:
- Capa **estricta** (``ProblemaPL``, ``DatosEOQ``...): lo que el motor de cálculo
  exige. Si no valida, no se calcula.
- Capa **permisiva** (``Extraccion*``): lo que puede devolver la IA; todos los
  campos son opcionales para que el modelo use ``null`` en lo que no aparece en
  el enunciado en lugar de inventarlo. Luego se revisa qué falta.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Número real finito (se convierte a Fraction dentro de los algoritmos).
Num = Annotated[float, Field(allow_inf_nan=False)]

MAX_VARIABLES = 10
MAX_RESTRICCIONES = 15

_NOMBRE_VALIDO = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")
# s1, e1, a1 se reservan para variables de holgura, exceso y artificiales.
_NOMBRE_RESERVADO = re.compile(r"^[sea]\d+$")

_SIGNOS = {
    "<=": "<=", "=<": "<=", "≤": "<=", "<": "<=",
    ">=": ">=", "=>": ">=", "≥": ">=", ">": ">=",
    "=": "=", "==": "=",
}
_OBJETIVOS = {
    "max": "max", "maximizar": "max", "maximiza": "max", "maximización": "max", "maximizacion": "max",
    "min": "min", "minimizar": "min", "minimiza": "min", "minimización": "min", "minimizacion": "min",
}


# --------------------------------------------------------------------------- #
# Programación lineal (modelación, gráfico, simplex)
# --------------------------------------------------------------------------- #
class Restriccion(BaseModel):
    coeficientes: list[Num]
    signo: Literal["<=", ">=", "="]
    rhs: Num
    nombre: str = ""

    @field_validator("signo", mode="before")
    @classmethod
    def _normalizar_signo(cls, v):
        if isinstance(v, str):
            return _SIGNOS.get(v.strip(), v)
        return v


class ProblemaPL(BaseModel):
    titulo: str = "Problema de programación lineal"
    objetivo: Literal["max", "min"]
    coef_objetivo: list[Num]
    restricciones: list[Restriccion]
    nombres_variables: list[str] | None = None
    descripciones_variables: list[str] | None = None

    @field_validator("objetivo", mode="before")
    @classmethod
    def _normalizar_objetivo(cls, v):
        if isinstance(v, str):
            return _OBJETIVOS.get(v.strip().lower(), v)
        return v

    @model_validator(mode="after")
    def _validar(self):
        n = len(self.coef_objetivo)
        if n < 1:
            raise ValueError("Debe haber al menos una variable de decisión.")
        if n > MAX_VARIABLES:
            raise ValueError(f"Se admiten como máximo {MAX_VARIABLES} variables (hay {n}).")
        if not self.restricciones:
            raise ValueError("Debe haber al menos una restricción.")
        if len(self.restricciones) > MAX_RESTRICCIONES:
            raise ValueError(
                f"Se admiten como máximo {MAX_RESTRICCIONES} restricciones (hay {len(self.restricciones)})."
            )
        for i, r in enumerate(self.restricciones, 1):
            if len(r.coeficientes) != n:
                raise ValueError(
                    f"La restricción {i} tiene {len(r.coeficientes)} coeficientes, "
                    f"pero el problema tiene {n} variables."
                )
        if all(c == 0 for c in self.coef_objetivo):
            raise ValueError("La función objetivo no puede tener todos sus coeficientes en cero.")

        if self.nombres_variables is None:
            self.nombres_variables = [f"x{i}" for i in range(1, n + 1)]
        else:
            nombres = [s.strip() for s in self.nombres_variables]
            if len(nombres) != n:
                raise ValueError(f"Hay {len(nombres)} nombres de variables, pero {n} variables.")
            for nom in nombres:
                if not _NOMBRE_VALIDO.match(nom):
                    raise ValueError(
                        f"El nombre de variable «{nom}» no es válido: usa letras, números o guion bajo "
                        "(máximo 16 caracteres) y empieza con una letra."
                    )
                if _NOMBRE_RESERVADO.match(nom):
                    raise ValueError(
                        f"El nombre «{nom}» está reservado para variables de holgura, exceso o artificiales."
                    )
            if len(set(nombres)) != n:
                raise ValueError("Los nombres de las variables deben ser distintos entre sí.")
            self.nombres_variables = nombres

        if self.descripciones_variables is not None and len(self.descripciones_variables) != n:
            raise ValueError(
                f"Hay {len(self.descripciones_variables)} descripciones de variables, pero {n} variables."
            )
        return self

    # ---- conveniencias -----------------------------------------------------
    @property
    def variables(self) -> list[str]:
        return list(self.nombres_variables or [])

    @property
    def n(self) -> int:
        return len(self.coef_objetivo)

    @property
    def m(self) -> int:
        return len(self.restricciones)

    def etiqueta_restriccion(self, i: int) -> str:
        """Nombre de la restricción i (base 0): el dado por el usuario o 'R{i+1}'."""
        return self.restricciones[i].nombre.strip() or f"R{i + 1}"


# --------------------------------------------------------------------------- #
# Inventarios (EOQ y punto de reorden)
# --------------------------------------------------------------------------- #
class DatosEOQ(BaseModel):
    nombre_articulo: str = ""

    demanda: float = Field(gt=0, allow_inf_nan=False)
    periodo_demanda: Literal["anual", "mensual", "semanal", "diario"] = "anual"

    costo_pedido: float = Field(gt=0, allow_inf_nan=False)  # S: costo de ordenar un pedido

    # Costo de mantener: valor directo H (por unidad y por año) o porcentaje i del costo unitario C.
    modo_mantener: Literal["unitario", "porcentaje"] = "unitario"
    costo_mantener: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    porcentaje_mantener: float | None = Field(default=None, gt=0, allow_inf_nan=False)  # en %, p. ej. 20
    costo_unitario: float | None = Field(default=None, gt=0, allow_inf_nan=False)  # C

    plazo_entrega: float | None = Field(default=None, ge=0, allow_inf_nan=False)  # L
    unidad_plazo: Literal["dias", "semanas", "meses"] = "dias"
    dias_laborales_anio: int = Field(default=365, ge=1, le=366)
    stock_seguridad: float = Field(default=0, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _validar(self):
        if self.modo_mantener == "unitario":
            if self.costo_mantener is None:
                raise ValueError("Falta el costo de mantener una unidad en inventario por año (H).")
        else:
            if self.porcentaje_mantener is None:
                raise ValueError("Falta el porcentaje de costo de mantener (i, en %).")
            if self.costo_unitario is None:
                raise ValueError("Con el costo de mantener como porcentaje hace falta el costo unitario (C).")
        return self


# --------------------------------------------------------------------------- #
# Transporte y asignación
# --------------------------------------------------------------------------- #
MAX_DIM_TRANSPORTE = 8
MAX_DIM_ASIGNACION = 10


def _nombres_validos(nombres: list[str] | None, cantidad: int, que: str) -> list[str] | None:
    if nombres is None:
        return None
    nombres = [s.strip() for s in nombres]
    if len(nombres) != cantidad:
        raise ValueError(f"Hay {len(nombres)} nombres de {que}, pero {cantidad} {que}.")
    if any(not s for s in nombres):
        raise ValueError(f"Los nombres de {que} no pueden estar vacíos.")
    if len(set(nombres)) != cantidad:
        raise ValueError(f"Los nombres de {que} deben ser distintos entre sí.")
    return nombres


def _matriz_valida(costos: list[list[float]]) -> tuple[int, int]:
    if not costos or not costos[0]:
        raise ValueError("La matriz de costos no puede estar vacía.")
    n = len(costos[0])
    for i, fila in enumerate(costos, 1):
        if len(fila) != n:
            raise ValueError(f"La fila {i} de la matriz de costos tiene {len(fila)} columnas; se esperaban {n}.")
    return len(costos), n


class DatosTransporte(BaseModel):
    titulo: str = "Problema de transporte"
    objetivo: Literal["min", "max"] = "min"
    oferta: list[Annotated[float, Field(ge=0, allow_inf_nan=False)]]
    demanda: list[Annotated[float, Field(ge=0, allow_inf_nan=False)]]
    costos: list[list[Num]]
    metodo_inicial: Literal["esquina_noroeste", "costo_minimo", "vogel"] = "vogel"
    nombres_origenes: list[str] | None = None
    nombres_destinos: list[str] | None = None

    @field_validator("objetivo", mode="before")
    @classmethod
    def _normalizar_objetivo(cls, v):
        if isinstance(v, str):
            return _OBJETIVOS.get(v.strip().lower(), v)
        return v

    @model_validator(mode="after")
    def _validar(self):
        m, n = len(self.oferta), len(self.demanda)
        if m < 1 or n < 1:
            raise ValueError("Debe haber al menos un origen y un destino.")
        if m > MAX_DIM_TRANSPORTE or n > MAX_DIM_TRANSPORTE:
            raise ValueError(f"Se admiten como máximo {MAX_DIM_TRANSPORTE} orígenes y {MAX_DIM_TRANSPORTE} destinos.")
        filas, cols = _matriz_valida(self.costos)
        if (filas, cols) != (m, n):
            raise ValueError(
                f"La matriz de costos es de {filas}×{cols}, pero hay {m} orígenes y {n} destinos."
            )
        if sum(self.oferta) <= 0 or sum(self.demanda) <= 0:
            raise ValueError("La oferta total y la demanda total deben ser mayores que cero.")
        self.nombres_origenes = _nombres_validos(self.nombres_origenes, m, "orígenes")
        self.nombres_destinos = _nombres_validos(self.nombres_destinos, n, "destinos")
        return self


class DatosAsignacion(BaseModel):
    titulo: str = "Problema de asignación"
    objetivo: Literal["min", "max"] = "min"
    costos: list[list[Num]]
    nombres_filas: list[str] | None = None
    nombres_columnas: list[str] | None = None

    @field_validator("objetivo", mode="before")
    @classmethod
    def _normalizar_objetivo(cls, v):
        if isinstance(v, str):
            return _OBJETIVOS.get(v.strip().lower(), v)
        return v

    @model_validator(mode="after")
    def _validar(self):
        m, n = _matriz_valida(self.costos)
        if m > MAX_DIM_ASIGNACION or n > MAX_DIM_ASIGNACION:
            raise ValueError(f"Se admiten como máximo {MAX_DIM_ASIGNACION} filas y {MAX_DIM_ASIGNACION} columnas.")
        self.nombres_filas = _nombres_validos(self.nombres_filas, m, "filas")
        self.nombres_columnas = _nombres_validos(self.nombres_columnas, n, "columnas")
        return self


# --------------------------------------------------------------------------- #
# Capa permisiva de extracción (salida de la IA)
# --------------------------------------------------------------------------- #
class ExtraccionEOQ(BaseModel):
    nombre_articulo: str | None = None
    demanda: float | None = None
    periodo_demanda: str | None = None
    costo_pedido: float | None = None
    modo_mantener: str | None = None
    costo_mantener: float | None = None
    porcentaje_mantener: float | None = None
    costo_unitario: float | None = None
    plazo_entrega: float | None = None
    unidad_plazo: str | None = None
    dias_laborales_anio: int | None = None
    stock_seguridad: float | None = None


class ExtraccionRestriccion(BaseModel):
    coeficientes: list[float | None] | None = None
    signo: str | None = None
    rhs: float | None = None
    nombre: str | None = None


class ExtraccionPL(BaseModel):
    titulo: str | None = None
    objetivo: str | None = None
    coef_objetivo: list[float | None] | None = None
    restricciones: list[ExtraccionRestriccion] | None = None
    nombres_variables: list[str] | None = None
    descripciones_variables: list[str] | None = None


class ExtraccionTransporte(BaseModel):
    titulo: str | None = None
    objetivo: str | None = None
    oferta: list[float | None] | None = None
    demanda: list[float | None] | None = None
    costos: list[list[float | None]] | None = None
    nombres_origenes: list[str] | None = None
    nombres_destinos: list[str] | None = None


class ExtraccionAsignacion(BaseModel):
    titulo: str | None = None
    objetivo: str | None = None
    costos: list[list[float | None]] | None = None
    nombres_filas: list[str] | None = None
    nombres_columnas: list[str] | None = None
