"""Página de programación lineal: método gráfico y simplex."""
from __future__ import annotations

import streamlit as st

from algoritmos import grafico, simplex
from core import validador
from interfaz.componentes import formularios, render_resultado
from interfaz.componentes.panel_ia import panel_ia
from practica.ejercicios import EJEMPLOS

CLAVE = "pl"
EJEMPLO_TEXTO = (
    "Maximiza Z = 40x + 30y sujeto a 2x + y ≤ 100, x + 2y ≤ 80, con x, y ≥ 0."
)


def _aplicar_ia(datos) -> None:
    formularios.cargar_ejemplo(CLAVE, validador.base_pl(datos))


def mostrar() -> None:
    st.header("Programación lineal")
    st.caption("Resuelve problemas de maximización y minimización con el método gráfico (2 variables) o el simplex.")

    metodo = st.radio("Método", ["Simplex", "Método gráfico"], horizontal=True, key=f"{CLAVE}_metodo")

    ejemplos = EJEMPLOS["pl"]
    elegido = st.selectbox("Ejemplos", range(len(ejemplos)), format_func=lambda i: ejemplos[i]["titulo"],
                           key=f"{CLAVE}_ejemplo")
    st.button("Cargar ejemplo", on_click=formularios.cargar_ejemplo_pl, args=(CLAVE, ejemplos[elegido]))

    panel_ia("pl", CLAVE, _aplicar_ia, ejemplo=EJEMPLO_TEXTO)

    st.divider()
    datos = formularios.formulario_pl(CLAVE)

    if st.button("Resolver", type="primary", key=f"{CLAVE}_resolver"):
        motor = simplex if metodo == "Simplex" else grafico
        st.session_state[f"{CLAVE}_resultado"] = motor.resolver_datos(datos)
        st.session_state[f"{CLAVE}_datos"] = datos

    resultado = st.session_state.get(f"{CLAVE}_resultado")
    if resultado is not None:
        st.divider()
        render_resultado.mostrar(resultado, clave=CLAVE, datos=st.session_state.get(f"{CLAVE}_datos"),
                                 enunciado=st.session_state.get(f"{CLAVE}_ia_texto") or None)
