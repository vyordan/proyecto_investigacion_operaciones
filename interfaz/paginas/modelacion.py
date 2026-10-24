"""Página de modelación: del enunciado a variables, función objetivo y restricciones."""
from __future__ import annotations

import streamlit as st

from algoritmos import grafico, modelacion, simplex
from core import validador
from interfaz.componentes import formularios, render_resultado
from interfaz.componentes.panel_ia import panel_ia

CLAVE = "mod"
EJEMPLO_TEXTO = (
    "Un taller fabrica mesas y sillas. Cada mesa deja una utilidad de Q40 y cada silla de Q30. Una mesa usa "
    "2 horas de carpintería y 1 de pintura; una silla usa 1 hora de carpintería y 2 de pintura. Hay 100 horas "
    "de carpintería y 80 de pintura disponibles. ¿Cuántas de cada una conviene fabricar?"
)


def _aplicar(datos) -> None:
    formularios.cargar_ejemplo(CLAVE, validador.base_pl(datos))


def mostrar() -> None:
    st.header("Modelación")
    st.caption("Identifica las variables de decisión, la función objetivo y las restricciones de un problema, "
               "y resuélvelo. Puedes escribir el enunciado y dejar que la IA proponga el modelo, o armarlo a mano.")

    panel_ia("pl", CLAVE, _aplicar, ejemplo=EJEMPLO_TEXTO)

    st.divider()
    datos = formularios.formulario_pl(CLAVE, con_descripciones=True)

    if st.button("Formular modelo", type="primary", key=f"{CLAVE}_formular"):
        st.session_state[f"{CLAVE}_modelo"] = (datos, modelacion.formular_datos(datos))
        st.session_state.pop(f"{CLAVE}_resultado", None)

    guardado = st.session_state.get(f"{CLAVE}_modelo")
    if guardado is None:
        return
    datos_modelo, resultado_modelo = guardado

    st.divider()
    if not resultado_modelo.exitoso:
        render_resultado.mostrar(resultado_modelo, clave=f"{CLAVE}_m")
        return

    st.success(resultado_modelo.resumen)
    for paso in resultado_modelo.pasos:
        render_resultado.mostrar_paso(paso)

    st.markdown("#### Resolver el modelo")
    c1, c2 = st.columns(2)
    if c1.button("Resolver con simplex", key=f"{CLAVE}_simplex"):
        st.session_state[f"{CLAVE}_resultado"] = simplex.resolver_datos(datos_modelo)
    if c2.button("Resolver con método gráfico", key=f"{CLAVE}_grafico"):
        st.session_state[f"{CLAVE}_resultado"] = grafico.resolver_datos(datos_modelo)

    resultado = st.session_state.get(f"{CLAVE}_resultado")
    if resultado is not None:
        st.divider()
        render_resultado.mostrar(resultado, clave=CLAVE, datos=datos_modelo,
                                 enunciado=st.session_state.get(f"{CLAVE}_ia_texto") or None)
