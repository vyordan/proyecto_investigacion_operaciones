"""Muestra un ``Resultado`` del motor en Streamlit (pasos, fórmulas, tablas, figuras)."""
from __future__ import annotations

from html import escape

import streamlit as st

from core.resultado import Estado, Resultado, Tabla
from interfaz.componentes.figuras import dibujar
from interfaz.componentes.preguntas import caja_pregunta

_MENSAJES_ESTADO = {
    Estado.OPTIMO: ("success", "Solución encontrada"),
    Estado.MULTIPLES_OPTIMOS: ("success", "Solución encontrada (múltiples óptimos)"),
    Estado.INFACTIBLE: ("warning", "Problema infactible"),
    Estado.NO_ACOTADO: ("warning", "Problema no acotado"),
    Estado.ERROR_DATOS: ("error", "Revisa los datos ingresados"),
    Estado.NO_SOPORTADO: ("warning", "Caso no soportado"),
    Estado.ERROR_INTERNO: ("error", "No se pudo completar el cálculo"),
}

_ETIQUETAS_FILA_Z = {"Z", "Z'", "W"}


def _tabla_html(t: Tabla) -> str:
    estilo_celda = "border:1px solid rgba(128,128,128,.35);padding:4px 10px;text-align:center;"
    filas_html = []
    encabezado = "".join(
        f"<th style='{estilo_celda}background:rgba(128,128,128,.15);'>{escape(c)}</th>" for c in t.columnas
    )
    filas_html.append(f"<tr>{encabezado}</tr>")
    for i, fila in enumerate(t.filas):
        celdas = []
        es_z = fila and fila[0] in _ETIQUETAS_FILA_Z
        for j, valor in enumerate(fila):
            fondo = ""
            if t.pivote is not None:
                pf, pc = t.pivote
                if (i, j) == (pf, pc):
                    fondo = "background:rgba(255,160,0,.55);font-weight:700;"
                elif i == pf or j == pc:
                    fondo = "background:rgba(255,160,0,.15);"
            if i in t.filas_resaltadas or (i, j) in t.celdas_resaltadas:
                fondo = "background:rgba(46,160,67,.28);font-weight:600;"
            elif (i in t.filas_cubiertas and j > 0) or j in t.columnas_cubiertas:
                fondo = "background:rgba(47,111,237,.20);"
                if i in t.filas_cubiertas and j in t.columnas_cubiertas:
                    fondo = "background:rgba(47,111,237,.40);"
            if es_z or j == 0:
                fondo += "font-weight:600;"
            if es_z:
                fondo += "border-top:2px solid rgba(128,128,128,.7);"
            celdas.append(f"<td style='{estilo_celda}{fondo}'>{escape(valor)}</td>")
        filas_html.append("<tr>" + "".join(celdas) + "</tr>")
    titulo = f"<div style='font-weight:600;margin:6px 0 4px;'>{escape(t.titulo)}</div>" if t.titulo else ""
    notas = f"<div style='opacity:.7;font-size:.85em;margin-top:4px;'>{escape(t.notas)}</div>" if t.notas else ""
    return (
        f"{titulo}<div style='overflow-x:auto;'><table style='border-collapse:collapse;margin:4px auto;"
        f"font-variant-numeric:tabular-nums;'>{''.join(filas_html)}</table></div>{notas}"
    )


def _bloque_latex(lineas: list[str]) -> str:
    if len(lineas) == 1:
        return lineas[0]
    return r"\begin{array}{l}" + r" \\ ".join(lineas) + r"\end{array}"


def mostrar_paso(paso) -> None:
    if paso.explicacion:
        st.markdown(paso.explicacion)
    if paso.formula:
        st.caption("Fórmula")
        st.latex(paso.formula)
    if paso.sustitucion:
        st.caption("Sustitución de valores")
        st.latex(paso.sustitucion)
    if paso.resultado:
        st.caption("Resultado")
        st.latex(paso.resultado)
    if paso.lineas:
        st.latex(_bloque_latex(paso.lineas))
    for tabla in ([paso.tabla] if paso.tabla else []) + list(paso.tablas):
        st.markdown(_tabla_html(tabla), unsafe_allow_html=True)


def mostrar(res: Resultado, clave: str = "res", datos: dict | None = None, enunciado: str | None = None,
            preguntas: bool = True) -> None:
    tipo, titulo = _MENSAJES_ESTADO[res.estado]
    getattr(st, tipo)(f"**{titulo}.** {res.resumen}" if res.resumen else f"**{titulo}.**")

    errores = [a for a in res.advertencias if a.nivel == "error"]
    if len(errores) > 1:  # varios errores: una sola lista, más fácil de leer
        st.error("\n".join(f"- {a.mensaje}" for a in errores), icon="🚫")
        errores = []
    for a in res.advertencias:
        if a.nivel == "error" and not errores:
            continue
        icono = {"info": "ℹ️", "aviso": "⚠️", "error": "🚫"}[a.nivel]
        {"info": st.info, "aviso": st.warning, "error": st.error}[a.nivel](a.mensaje, icon=icono)

    if res.interpretacion:
        st.markdown("#### Interpretación")
        st.markdown(res.interpretacion)

    for i, figura in enumerate(res.figuras):
        st.pyplot(dibujar(figura), clear_figure=True)

    if res.pasos:
        st.markdown("#### Procedimiento paso a paso")
        expandir = st.toggle("Expandir todos los pasos", value=True, key=f"{clave}_expandir")
        for n, paso in enumerate(res.pasos, 1):
            with st.expander(f"{n}. {paso.titulo}", expanded=expandir):
                mostrar_paso(paso)

    if preguntas:
        caja_pregunta(res, clave, datos=datos, enunciado=enunciado)
