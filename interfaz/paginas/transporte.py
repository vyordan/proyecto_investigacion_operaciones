"""Página de transporte: solución inicial y optimización con MODI."""
from __future__ import annotations

import streamlit as st

from algoritmos import transporte
from core import validador
from interfaz.componentes import formularios, render_resultado
from interfaz.componentes.panel_ia import panel_ia
from practica.ejercicios import EJEMPLOS

CLAVE = "tr"
EJEMPLO_TEXTO = (
    "Dos plantas (A con oferta 40 y B con 50) abastecen a tres ciudades con demandas 20, 25 y 30. "
    "Costos por unidad: de A a las ciudades 4, 6 y 8; de B, 5, 3 y 7."
)


def _aplicar_ia(datos) -> None:
    formularios.cargar_ejemplo(CLAVE, validador.base_transporte(datos))


def mostrar() -> None:
    st.header("Transporte")
    st.caption("Distribución de recursos de varios orígenes a varios destinos al menor costo (o mayor beneficio).")

    ejemplos = EJEMPLOS["transporte"]
    elegido = st.selectbox("Ejemplos", range(len(ejemplos)), format_func=lambda i: ejemplos[i]["titulo"],
                           key=f"{CLAVE}_ejemplo")
    st.button("Cargar ejemplo", on_click=formularios.cargar_ejemplo, args=(CLAVE, ejemplos[elegido]))

    panel_ia("transporte", CLAVE, _aplicar_ia, ejemplo=EJEMPLO_TEXTO)

    st.divider()
    datos = formularios.formulario_transporte(CLAVE)

    if st.button("Resolver", type="primary", key=f"{CLAVE}_resolver"):
        st.session_state[f"{CLAVE}_resultado"] = transporte.resolver_datos(datos)
        st.session_state[f"{CLAVE}_datos"] = datos

    resultado = st.session_state.get(f"{CLAVE}_resultado")
    if resultado is not None:
        st.divider()
        render_resultado.mostrar(resultado, clave=CLAVE, datos=st.session_state.get(f"{CLAVE}_datos"),
                                 enunciado=st.session_state.get(f"{CLAVE}_ia_texto") or None)
