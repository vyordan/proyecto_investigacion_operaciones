"""Configuración general de la interfaz: encabezado, navegación y páginas."""
from __future__ import annotations

import streamlit as st

from interfaz.componentes.panel_ia import configuracion_ia
from interfaz.paginas import (
    asignacion,
    inventarios,
    modelacion,
    practica,
    programacion_lineal,
    transporte,
)

# TODO: completar antes de entregar (requisito 7 del enunciado).
NOMBRE_APP = "Asistente de Investigación de Operaciones"
INTEGRANTES = ["Integrante Jeremy Paredes", "Integrante Yordan Vasquez"]
ASIGNATURA = "Investigación de Operaciones"
SECCION = "Facultada de Ing en sistemas de la informacion"


def _inicio() -> None:
    st.header("Bienvenido")
    st.markdown(
        "Este asistente resuelve problemas de Investigación de Operaciones **mostrando el procedimiento completo**: "
        "fórmulas, sustitución de valores, pasos y respuesta final con su interpretación.\n\n"
        "- **Modelación:** del enunciado a variables, función objetivo y restricciones (con ayuda opcional de IA).\n"
        "- **Programación lineal:** método gráfico y simplex (maximizar, minimizar, restricciones ≤, ≥ y =).\n"
        "- **Transporte:** solución inicial (esquina noroeste, costo mínimo o Vogel) y optimización con MODI.\n"
        "- **Asignación:** método húngaro.\n"
        "- **Inventarios:** cantidad económica de pedido (EOQ) y punto de reorden.\n"
        "- **Práctica:** ejercicios nuevos generados al momento, con corrección y pistas.\n\n"
        "Elige un módulo en el menú lateral. Todos los cálculos los hace un motor matemático exacto; "
        "si faltan datos o hay errores, el asistente te avisa."
    )


PAGINAS = {
    "Inicio": _inicio,
    "Modelación": modelacion.mostrar,
    "Programación lineal": programacion_lineal.mostrar,
    "Transporte": transporte.mostrar,
    "Asignación": asignacion.mostrar,
    "Inventarios (EOQ)": inventarios.mostrar,
    "Práctica": practica.mostrar,
}


def main() -> None:
    st.set_page_config(page_title=NOMBRE_APP, page_icon="📐", layout="wide")

    with st.sidebar:
        st.title("📐 " + NOMBRE_APP)
        pagina = st.radio("Módulo", list(PAGINAS), label_visibility="collapsed")
        st.divider()
        configuracion_ia()
        st.divider()
        st.caption(f"{ASIGNATURA} · {SECCION}")
        st.caption("Integrantes: " + " y ".join(INTEGRANTES))

    PAGINAS[pagina]()
