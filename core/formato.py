"""Formato de números y de expresiones matemáticas (texto plano y LaTeX).

Todo el cálculo del proyecto usa ``Fraction`` (aritmética exacta); este módulo
solo se encarga de *mostrar* los valores. No tiene dependencias externas.
"""
from __future__ import annotations

import math
import re
from fractions import Fraction
from typing import Sequence

SIGNO_TEXTO = {"<=": "≤", ">=": "≥", "=": "="}
SIGNO_LATEX = {"<=": r"\leq", ">=": r"\geq", "=": "="}


# --------------------------------------------------------------------------- #
# Conversión
# --------------------------------------------------------------------------- #
def a_fraccion(valor) -> Fraction:
    """Convierte int, float, str ('2.5', '1/3', '1,5') o Fraction a Fraction.

    Los float se convierten desde su representación decimal más corta
    (0.1 -> 1/10) para evitar los errores de la representación binaria.
    """
    if isinstance(valor, Fraction):
        return valor
    if isinstance(valor, bool):
        raise ValueError("Se esperaba un número, no un valor lógico.")
    if isinstance(valor, int):
        return Fraction(valor)
    if isinstance(valor, float):
        if not math.isfinite(valor):
            raise ValueError("El número debe ser finito.")
        return Fraction(str(valor))
    if isinstance(valor, str):
        return Fraction(valor.strip().replace(",", "."))
    raise ValueError(f"No se puede interpretar «{valor}» como número.")


def es_entero(x: Fraction) -> bool:
    return x.denominator == 1


# --------------------------------------------------------------------------- #
# Números
# --------------------------------------------------------------------------- #
def decimal_exacto(x: Fraction, max_decimales: int = 6) -> str | None:
    """Expansión decimal exacta de ``x`` si existe y es corta; si no, None."""
    for k in range(max_decimales + 1):
        escalado = x * 10**k
        if escalado.denominator == 1:
            n = int(escalado)
            signo = "-" if n < 0 else ""
            digitos = str(abs(n)).rjust(k + 1, "0")
            if k == 0:
                return signo + digitos
            return f"{signo}{digitos[:-k]}.{digitos[-k:]}"
    return None


def decimal(x, decimales: int = 2) -> str:
    """Decimal redondeado sin ceros sobrantes: 33.333 -> '33.33', 2.50 -> '2.5'."""
    s = f"{float(a_fraccion(x)):.{decimales}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def texto(x, decimales: int = 2) -> str:
    """Texto para explicaciones: '5', '2.5' o '100/3 ≈ 33.33'."""
    x = a_fraccion(x)
    exacto = decimal_exacto(x)
    if exacto is not None:
        return exacto
    return f"{x.numerator}/{x.denominator} ≈ {decimal(x, decimales)}"


def celda(x) -> str:
    """Texto compacto para celdas de tablas: '5' o '100/3'."""
    x = a_fraccion(x)
    if es_entero(x):
        return str(x.numerator)
    return f"{x.numerator}/{x.denominator}"


def latex(x) -> str:
    """LaTeX de un número: '5', '2.5' o '\\frac{100}{3}' (con signo)."""
    x = a_fraccion(x)
    exacto = decimal_exacto(x)
    if exacto is not None:
        return exacto
    signo = "-" if x < 0 else ""
    return f"{signo}\\frac{{{abs(x.numerator)}}}{{{x.denominator}}}"


# --------------------------------------------------------------------------- #
# Variables y expresiones lineales
# --------------------------------------------------------------------------- #
def var_latex(nombre: str) -> str:
    """'x' -> x ; 'x1' -> x_{1} ; 'mesas' -> \\text{mesas}."""
    if len(nombre) == 1 and nombre.isalpha() and nombre.isascii():
        return nombre
    m = re.fullmatch(r"([A-Za-z]+)(\d+)", nombre)
    if m:
        return f"{m.group(1)}_{{{m.group(2)}}}"
    return "\\text{" + nombre.replace("_", "\\_") + "}"


def expresion_latex(coefs: Sequence, nombres: Sequence[str], signo_inicial: bool = False) -> str:
    """'40x + 30y' en LaTeX. Con ``signo_inicial`` cada término lleva su signo
    (útil para escribir 'Z - 40x - 30y = 0')."""
    partes: list[str] = []
    for c, nombre in zip(coefs, nombres):
        c = a_fraccion(c)
        if c == 0:
            continue
        v = var_latex(nombre)
        magnitud = abs(c)
        cuerpo = v if magnitud == 1 else f"{latex(magnitud)}{v}"
        if signo_inicial or partes:
            partes.append((" - " if c < 0 else " + ") + cuerpo)
        else:
            partes.append(("-" if c < 0 else "") + cuerpo)
    if partes:
        return "".join(partes)
    return "" if signo_inicial else "0"


def expresion_texto(coefs: Sequence, nombres: Sequence[str]) -> str:
    """'40x + 30y' en texto plano."""
    partes: list[str] = []
    for c, nombre in zip(coefs, nombres):
        c = a_fraccion(c)
        if c == 0:
            continue
        magnitud = abs(c)
        exacto = decimal_exacto(magnitud)
        if magnitud == 1:
            cuerpo = nombre
        elif exacto is not None:
            cuerpo = f"{exacto}{nombre}"
        else:
            cuerpo = f"({magnitud.numerator}/{magnitud.denominator}){nombre}"
        if partes:
            partes.append((" - " if c < 0 else " + ") + cuerpo)
        else:
            partes.append(("-" if c < 0 else "") + cuerpo)
    return "".join(partes) if partes else "0"


def lista_es(items: Sequence[str]) -> str:
    """['R1', 'R2', 'R3'] -> 'R1, R2 y R3'."""
    items = list(items)
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]
