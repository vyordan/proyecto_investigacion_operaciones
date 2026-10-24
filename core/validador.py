"""Manejo de errores y datos faltantes.

Reglas del proyecto:
- Ningún error de datos llega a la interfaz como excepción: siempre se convierte
  en un ``Resultado`` con ``Estado.ERROR_DATOS`` y mensajes claros en español.
- Se distingue entre «falta un dato» y «el dato es inválido».
"""
from __future__ import annotations

import math
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

import unicodedata

from core.esquemas import (
    _OBJETIVOS,
    _SIGNOS,
    ExtraccionAsignacion,
    ExtraccionEOQ,
    ExtraccionPL,
    ExtraccionTransporte,
)
from core.resultado import Advertencia, Estado, Resultado

ETIQUETAS = {
    # EOQ
    "demanda": "Demanda",
    "periodo_demanda": "Período de la demanda",
    "costo_pedido": "Costo de pedido (S)",
    "modo_mantener": "Forma del costo de mantener",
    "costo_mantener": "Costo de mantener (H)",
    "porcentaje_mantener": "Porcentaje de mantener (i)",
    "costo_unitario": "Costo unitario (C)",
    "plazo_entrega": "Plazo de entrega (L)",
    "unidad_plazo": "Unidad del plazo",
    "dias_laborales_anio": "Días laborales al año",
    "stock_seguridad": "Stock de seguridad",
    # Programación lineal
    "objetivo": "Tipo de objetivo",
    "coef_objetivo": "Coeficiente de la función objetivo",
    "restricciones": "Restricción",
    "coeficientes": "Coeficiente",
    "signo": "Signo",
    "rhs": "Lado derecho",
    "nombres_variables": "Nombres de variables",
    "descripciones_variables": "Descripciones de variables",
    # Transporte y asignación
    "oferta": "Oferta",
    "costos": "Matriz de costos",
    "metodo_inicial": "Método de solución inicial",
    "nombres_origenes": "Nombres de orígenes",
    "nombres_destinos": "Nombres de destinos",
    "nombres_filas": "Nombres de filas",
    "nombres_columnas": "Nombres de columnas",
}


def _num(v: Any) -> str:
    """12.0 -> '12'; 0.5 -> '0.5'."""
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def _etiqueta(loc: tuple) -> str:
    """('restricciones', 0, 'coeficientes', 1) -> 'Restricción 1 › Coeficiente 2'."""
    partes: list[str] = []
    i = 0
    while i < len(loc):
        p = loc[i]
        if isinstance(p, int):
            if i + 1 < len(loc) and isinstance(loc[i + 1], int) and partes:  # matriz: fila y columna
                partes[-1] += f" (fila {p + 1}, columna {loc[i + 1] + 1})"
                i += 1
            elif partes:
                partes[-1] += f" {p + 1}"
            else:
                partes.append(str(p + 1))
        else:
            partes.append(ETIQUETAS.get(p, str(p)))
        i += 1
    return " › ".join(partes)


def _es_vacio(err: dict) -> bool:
    """Celda sin completar (None o NaN en un campo numérico)."""
    v = err.get("input")
    return err.get("type") in {"finite_number", "float_type", "float_parsing"} and (
        v is None or (isinstance(v, float) and math.isnan(v))
    )


def _mensaje_vacios(etiquetas: list[str]) -> str:
    """Agrupa las celdas vacías: 'Restricción 1: coeficiente 1, lado derecho; Restricción 2: ...'."""
    grupos: dict[str, list[str]] = {}
    for etq in etiquetas:
        prefijo, _, hoja = etq.rpartition(" › ")
        grupos.setdefault(prefijo, []).append(hoja if prefijo else etq)
    partes = []
    for prefijo, hojas in grupos.items():
        if prefijo:
            partes.append(f"{prefijo}: " + ", ".join(h[:1].lower() + h[1:] for h in hojas))
        else:
            partes.extend(hojas)
    return "Hay celdas vacías por completar — " + "; ".join(partes) + "."


def _traducir(err: dict) -> str:
    tipo = err.get("type", "")
    campo = _etiqueta(tuple(err.get("loc", ())))
    ctx = err.get("ctx") or {}
    if tipo == "missing":
        return f"Falta el dato «{campo}»."
    if tipo == "greater_than":
        return f"«{campo}» debe ser mayor que {_num(ctx.get('gt'))}."
    if tipo == "greater_than_equal":
        return f"«{campo}» debe ser mayor o igual que {_num(ctx.get('ge'))}."
    if tipo == "less_than_equal":
        return f"«{campo}» debe ser menor o igual que {_num(ctx.get('le'))}."
    if tipo == "less_than":
        return f"«{campo}» debe ser menor que {_num(ctx.get('lt'))}."
    if tipo == "finite_number":  # celda vacía (NaN) o valor no finito
        return f"Falta completar «{campo}»."
    if tipo in {"float_parsing", "float_type", "int_parsing", "int_type", "int_from_float"}:
        return f"«{campo}» debe ser un número válido."
    if tipo == "literal_error":
        return f"«{campo}» tiene un valor no permitido (opciones: {str(ctx.get('expected')).replace(' or ', ' o ')})."
    if tipo in {"string_type"}:
        return f"«{campo}» debe ser texto."
    if tipo in {"list_type", "dict_type", "model_type", "model_attributes_type"}:
        return f"«{campo or 'Los datos'}» no tienen el formato esperado."
    if tipo == "json_invalid":
        return "El texto no es un JSON válido."
    if tipo == "value_error":
        mensaje = str(err.get("msg", "")).removeprefix("Value error, ")
        return f"{campo}: {mensaje}" if campo else mensaje
    return f"«{campo}»: {err.get('msg', 'valor inválido')}" if campo else str(err.get("msg", "datos inválidos"))


def validar(clase: type[BaseModel], datos: Any) -> tuple[BaseModel | None, list[Advertencia]]:
    """Valida ``datos`` (dict, JSON o instancia) contra ``clase``.

    Devuelve (objeto, []) si son válidos o (None, errores) si no.
    """
    try:
        if isinstance(datos, (str, bytes)):
            return clase.model_validate_json(datos), []
        if isinstance(datos, clase):
            return clase.model_validate(datos.model_dump()), []
        return clase.model_validate(datos), []
    except ValidationError as exc:
        vistos: list[str] = []
        vacios: list[str] = []
        for e in exc.errors():
            if _es_vacio(e):
                vacios.append(_etiqueta(tuple(e.get("loc", ()))))
                continue
            msg = _traducir(e)
            if msg not in vistos:
                vistos.append(msg)
        if vacios:
            vistos.insert(0, _mensaje_vacios(vacios))
        return None, [Advertencia(nivel="error", mensaje=m) for m in vistos]
    except (TypeError, ValueError) as exc:
        return None, [Advertencia(nivel="error", mensaje=f"No se pudieron leer los datos: {exc}")]


def resultado_error(
    modulo: str,
    titulo: str,
    advertencias: list[Advertencia],
    estado: Estado = Estado.ERROR_DATOS,
) -> Resultado:
    resumen = (
        "Corrige los puntos señalados abajo e inténtalo de nuevo."
        if estado == Estado.ERROR_DATOS
        else "No se pudo completar el cálculo."
    )
    return Resultado(modulo=modulo, estado=estado, titulo=titulo, resumen=resumen, advertencias=advertencias)


def ejecutar(
    clase: type[BaseModel],
    datos: Any,
    funcion: Callable[[Any], Resultado],
    modulo: str,
    titulo: str,
) -> Resultado:
    """Valida, calcula y garantiza que nunca se propague una excepción."""
    objeto, errores = validar(clase, datos)
    if objeto is None:
        return resultado_error(modulo, titulo, errores)
    try:
        return funcion(objeto)
    except Exception as exc:  # defensa final: la UI nunca debe caerse
        return resultado_error(
            modulo,
            titulo,
            [Advertencia(nivel="error", mensaje=f"Error inesperado al calcular: {type(exc).__name__}: {exc}")],
            estado=Estado.ERROR_INTERNO,
        )


# --------------------------------------------------------------------------- #
# Datos faltantes en la extracción de la IA
# --------------------------------------------------------------------------- #
def faltantes_eoq(e: ExtraccionEOQ) -> list[str]:
    """Lista legible de los datos obligatorios que la IA no encontró."""
    falta: list[str] = []
    if e.demanda is None:
        falta.append(ETIQUETAS["demanda"])
    if e.costo_pedido is None:
        falta.append(ETIQUETAS["costo_pedido"])
    por_porcentaje = e.modo_mantener == "porcentaje" or (
        e.modo_mantener is None
        and e.costo_mantener is None
        and e.porcentaje_mantener is not None
    )
    if por_porcentaje:
        if e.porcentaje_mantener is None:
            falta.append(ETIQUETAS["porcentaje_mantener"])
        if e.costo_unitario is None:
            falta.append(ETIQUETAS["costo_unitario"])
    elif e.costo_mantener is None:
        falta.append(ETIQUETAS["costo_mantener"])
    return falta


def faltantes_pl(e: ExtraccionPL) -> list[str]:
    """Lista legible de los datos obligatorios que la IA no encontró."""
    falta: list[str] = []
    if e.objetivo is None:
        falta.append("Tipo de objetivo (maximizar o minimizar)")
    n = None
    if not e.coef_objetivo:
        falta.append("Coeficientes de la función objetivo")
    else:
        n = len(e.coef_objetivo)
        if any(c is None for c in e.coef_objetivo):
            falta.append("Algún coeficiente de la función objetivo")
    if not e.restricciones:
        falta.append("Restricciones")
    else:
        for i, r in enumerate(e.restricciones, 1):
            if not r.coeficientes or any(c is None for c in r.coeficientes):
                falta.append(f"Restricción {i}: coeficientes")
            elif n is not None and len(r.coeficientes) != n:
                falta.append(f"Restricción {i}: número de coeficientes distinto al de variables")
            if r.signo is None:
                falta.append(f"Restricción {i}: signo")
            if r.rhs is None:
                falta.append(f"Restricción {i}: lado derecho")
    return falta


def _matriz_incompleta(costos: list[list[float | None]] | None) -> bool:
    return not costos or any(v is None for fila in costos for v in fila) or len({len(f) for f in costos}) > 1


def faltantes_transporte(e: ExtraccionTransporte) -> list[str]:
    falta: list[str] = []
    if not e.oferta or any(v is None for v in e.oferta):
        falta.append("Oferta de cada origen")
    if not e.demanda or any(v is None for v in e.demanda):
        falta.append("Demanda de cada destino")
    if _matriz_incompleta(e.costos):
        falta.append("Matriz de costos completa")
    elif e.oferta and e.demanda and (len(e.costos) != len(e.oferta) or len(e.costos[0]) != len(e.demanda)):
        falta.append("Matriz de costos con tantas filas como orígenes y columnas como destinos")
    return falta


def faltantes_asignacion(e: ExtraccionAsignacion) -> list[str]:
    return ["Matriz de costos completa"] if _matriz_incompleta(e.costos) else []


# --------------------------------------------------------------------------- #
# De la extracción de la IA al «estado base» de los formularios
# --------------------------------------------------------------------------- #
NAN = float("nan")


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower().strip()) if unicodedata.category(c) != "Mn")


def _nan(v):
    return NAN if v is None else v


def _objetivo(t: str | None) -> str:
    return _OBJETIVOS.get(_sin_acentos(t or ""), "max")


def base_pl(e: ExtraccionPL) -> dict:
    n = len(e.coef_objetivo) if e.coef_objetivo else 2
    restr = []
    for r in e.restricciones or [None, None]:
        r = r or None
        restr.append(
            {
                "coeficientes": [_nan(v) for v in (r.coeficientes if r and r.coeficientes else [])],
                "signo": _SIGNOS.get((r.signo or "<=").strip(), "<=") if r else "<=",
                "rhs": _nan(r.rhs) if r else NAN,
                "nombre": (r.nombre or "") if r else "",
            }
        )
    return {
        "titulo": e.titulo or "Problema de programación lineal",
        "objetivo": _objetivo(e.objetivo),
        "coef_objetivo": [_nan(v) for v in (e.coef_objetivo or [None] * n)],
        "restricciones": restr,
        "nombres_variables": e.nombres_variables,
        "descripciones_variables": e.descripciones_variables,
    }


_PERIODOS = {"anual": "anual", "ano": "anual", "anio": "anual", "mensual": "mensual", "mes": "mensual",
             "semanal": "semanal", "semana": "semanal", "diario": "diario", "diaria": "diario", "dia": "diario"}
_UNIDADES = {"dias": "dias", "dia": "dias", "semanas": "semanas", "semana": "semanas", "meses": "meses", "mes": "meses"}


def base_eoq(e: ExtraccionEOQ) -> dict:
    """Solo incluye lo que la IA encontró; los valores desconocidos quedan vacíos en el formulario."""
    base: dict = {k: v for k, v in e.model_dump(exclude_none=True).items()}
    for clave, mapa in (("periodo_demanda", _PERIODOS), ("unidad_plazo", _UNIDADES)):
        if clave in base:
            normal = mapa.get(_sin_acentos(str(base[clave])))
            if normal:
                base[clave] = normal
            else:
                del base[clave]
    if base.get("modo_mantener") not in (None, "unitario", "porcentaje"):
        del base["modo_mantener"]
    if "modo_mantener" not in base:
        base["modo_mantener"] = "porcentaje" if (e.porcentaje_mantener is not None and e.costo_mantener is None) else "unitario"
    return base


def base_transporte(e: ExtraccionTransporte) -> dict:
    costos = e.costos or []
    m = len(e.oferta) if e.oferta else (len(costos) or 2)
    n = len(e.demanda) if e.demanda else (len(costos[0]) if costos and costos[0] else 2)
    return {
        "titulo": e.titulo or "Problema de transporte",
        "objetivo": "max" if _objetivo(e.objetivo) == "max" and e.objetivo else "min",
        "metodo_inicial": "vogel",
        "oferta": [_nan(v) for v in (e.oferta or [None] * m)],
        "demanda": [_nan(v) for v in (e.demanda or [None] * n)],
        "costos": [[_nan(v) for v in fila] for fila in costos],
        "nombres_origenes": e.nombres_origenes,
        "nombres_destinos": e.nombres_destinos,
    }


def base_asignacion(e: ExtraccionAsignacion) -> dict:
    return {
        "titulo": e.titulo or "Problema de asignación",
        "objetivo": "max" if e.objetivo and _objetivo(e.objetivo) == "max" else "min",
        "costos": [[_nan(v) for v in fila] for fila in (e.costos or [[], []])],
        "nombres_filas": e.nombres_filas,
        "nombres_columnas": e.nombres_columnas,
    }
