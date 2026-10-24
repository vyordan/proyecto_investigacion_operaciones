"""Arma el contexto (ejercicio + resultado calculado) que se envía a la IA junto con la pregunta.

Solo convierte a texto lo que ya calculó el motor; no calcula nada.
"""
from __future__ import annotations

import json
from typing import Any

from core.resultado import Paso, Resultado, Tabla

LIMITE_CARACTERES = 12000
_PASOS_FINALES = 2  # si hay que recortar, siempre se conservan los últimos pasos (la solución)


def tabla_a_texto(t: Tabla) -> str:
    lineas = []
    if t.titulo:
        lineas.append(f"[Tabla] {t.titulo}")
    lineas.append(" | ".join(t.columnas))
    for i, fila in enumerate(t.filas):
        marca = ""
        if t.pivote and t.pivote[0] == i:
            marca = f"    <- fila del pivote (columna «{t.columnas[t.pivote[1]]}»)"
        lineas.append(" | ".join(fila) + marca)
    if t.notas:
        lineas.append(t.notas)
    return "\n".join(lineas)


def paso_a_texto(n: int, paso: Paso) -> str:
    partes = [f"Paso {n}: {paso.titulo}"]
    if paso.explicacion:
        partes.append(paso.explicacion)
    for etiqueta, valor in (("Fórmula", paso.formula), ("Sustitución", paso.sustitucion), ("Resultado", paso.resultado)):
        if valor:
            partes.append(f"{etiqueta} (LaTeX): {valor}")
    if paso.lineas:
        partes.append("Líneas (LaTeX): " + " ; ".join(paso.lineas))
    for tabla in ([paso.tabla] if paso.tabla else []) + list(paso.tablas):
        partes.append(tabla_a_texto(tabla))
    return "\n".join(partes)


def _valor(res: Resultado, clave: str) -> str:
    v = res.valores[clave]
    exacto = res.exactos.get(clave)
    return f"{exacto} (≈ {v:g})" if exacto and "/" in exacto else f"{v:g}"


def contexto_ejercicio(
    res: Resultado,
    datos: dict[str, Any] | None = None,
    enunciado: str | None = None,
    limite: int = LIMITE_CARACTERES,
) -> str:
    """Texto con el ejercicio, el resultado calculado y el procedimiento (recortado si es muy largo)."""
    cabecera = ["EJERCICIO:"]
    if enunciado:
        cabecera.append(enunciado.strip())
    if datos:
        cabecera.append("Datos de entrada (JSON):\n" + json.dumps(datos, ensure_ascii=False, default=str))
    cabecera.append("\nRESULTADO CALCULADO POR EL MOTOR:")
    cabecera.append(f"Módulo: {res.titulo}")
    cabecera.append(f"Estado: {res.estado.value}")
    if res.resumen:
        cabecera.append(f"Resumen: {res.resumen}")
    if res.valores:
        cabecera.append("Valores: " + "; ".join(f"{k} = {_valor(res, k)}" for k in res.valores))
    if res.interpretacion:
        cabecera.append(f"Interpretación: {res.interpretacion}")
    if res.advertencias:
        cabecera.append("Advertencias: " + " | ".join(a.mensaje for a in res.advertencias))
    encabezado = "\n".join(cabecera)

    pasos = [paso_a_texto(i, p) for i, p in enumerate(res.pasos, 1)]
    cuerpo = "\n\n".join(pasos)
    presupuesto = max(limite - len(encabezado), 0)
    if len(cuerpo) > presupuesto:
        finales = pasos[-_PASOS_FINALES:]
        reserva = sum(len(t) for t in finales) + 120
        elegidos: list[str] = []
        usado = 0
        for t in pasos[: max(len(pasos) - _PASOS_FINALES, 0)]:
            if usado + len(t) > max(presupuesto - reserva, 0):
                break
            elegidos.append(t)
            usado += len(t)
        omitidos = len(pasos) - len(elegidos) - len(finales)
        cuerpo = "\n\n".join(elegidos + [f"[... {omitidos} paso(s) intermedio(s) omitido(s) por longitud ...]"] + finales)
    return f"{encabezado}\n\nPROCEDIMIENTO PASO A PASO:\n{cuerpo}"
