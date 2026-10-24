"""Página de asignación: método húngaro."""
from __future__ import annotations

import streamlit as st

from algoritmos import asignacion
from core import validador
from interfaz.componentes import formularios, render_resultado
from interfaz.componentes.panel_ia import panel_ia
from practica.ejercicios import EJEMPLOS

CLAVE = "as"
EJEMPLO_TEXTO = (
    "Tres operarios deben asignarse a tres máquinas. Tiempos en horas: Luis (9, 2, 7), Marta (6, 4, 3), "
    "Pablo (5, 8, 1). Se busca minimizar el tiempo total."
)


def _aplicar_ia(datos) -> None:
    formularios.cargar_ejemplo(CLAVE, validador.base_asignacion(datos))


def mostrar() -> None:
    st.header("Asignación")
    st.caption("Asigna agentes a tareas (uno a uno) minimizando el costo o maximizando el beneficio.")

    ejemplos = EJEMPLOS["asignacion"]
    elegido = st.selectbox("Ejemplos", range(len(ejemplos)), format_func=lambda i: ejemplos[i]["titulo"],
                           key=f"{CLAVE}_ejemplo")
    st.button("Cargar ejemplo", on_click=formularios.cargar_ejemplo, args=(CLAVE, ejemplos[elegido]))

    panel_ia("asignacion", CLAVE, _aplicar_ia, ejemplo=EJEMPLO_TEXTO)

    st.divider()
    datos = formularios.formulario_asignacion(CLAVE)

    if st.button("Resolver", type="primary", key=f"{CLAVE}_resolver"):
        st.session_state[f"{CLAVE}_resultado"] = asignacion.resolver_datos(datos)
        st.session_state[f"{CLAVE}_datos"] = datos

    resultado = st.session_state.get(f"{CLAVE}_resultado")
    if resultado is not None:
        st.divider()
        render_resultado.mostrar(resultado, clave=CLAVE, datos=st.session_state.get(f"{CLAVE}_datos"),
                                 enunciado=st.session_state.get(f"{CLAVE}_ia_texto") or None)
