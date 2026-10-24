"""Página de inventarios: EOQ y punto de reorden."""
from __future__ import annotations

import streamlit as st

from algoritmos import inventarios
from core import validador
from interfaz.componentes import formularios, render_resultado
from interfaz.componentes.panel_ia import panel_ia
from practica.ejercicios import EJEMPLOS

CLAVE = "eoq"
EJEMPLO_TEXTO = (
    "Una tienda vende 1200 cajas al año. Cada pedido cuesta Q50 y mantener una caja cuesta Q3 al año. "
    "El proveedor tarda 10 días en entregar."
)


def _aplicar_ia(datos) -> None:
    formularios.cargar_ejemplo_eoq(validador.base_eoq(datos))


def mostrar() -> None:
    st.header("Inventarios")
    st.caption("Cantidad económica de pedido (EOQ) y punto de reorden.")

    ejemplos = EJEMPLOS["eoq"]
    elegido = st.selectbox("Ejemplos", range(len(ejemplos)), format_func=lambda i: ejemplos[i]["titulo"],
                           key=f"{CLAVE}_ejemplo")
    st.button("Cargar ejemplo", on_click=formularios.cargar_ejemplo_eoq, args=(ejemplos[elegido],))

    panel_ia("eoq", CLAVE, _aplicar_ia, ejemplo=EJEMPLO_TEXTO)

    st.divider()
    datos = formularios.formulario_eoq()

    if st.button("Calcular", type="primary", key=f"{CLAVE}_calcular"):
        st.session_state[f"{CLAVE}_resultado"] = inventarios.resolver_datos(datos)
        st.session_state[f"{CLAVE}_datos"] = datos

    resultado = st.session_state.get(f"{CLAVE}_resultado")
    if resultado is not None:
        st.divider()
        render_resultado.mostrar(resultado, clave=CLAVE, datos=st.session_state.get(f"{CLAVE}_datos"),
                                 enunciado=st.session_state.get(f"{CLAVE}_ia_texto") or None)
