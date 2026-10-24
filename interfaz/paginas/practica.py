"""Página de práctica: genera ejercicios nuevos y los corrige con retroalimentación."""
from __future__ import annotations

import streamlit as st

from interfaz.componentes import render_resultado
from practica.generador import DIFICULTADES, MODULOS, Practica, evaluar, generar


def _clave(p: Practica, pid: str) -> str:
    return f"pr_resp_{p.modulo}_{p.dificultad}_{p.semilla}_{pid}"


def mostrar() -> None:
    st.header("Práctica")
    st.caption("Genera un ejercicio nuevo, resuélvelo por tu cuenta y revisa tus respuestas con retroalimentación.")

    c1, c2, c3 = st.columns([2, 1, 1])
    modulo = c1.selectbox("Módulo", list(MODULOS), format_func=MODULOS.get, key="pr_modulo")
    dificultad = c2.selectbox("Dificultad", list(DIFICULTADES), format_func=DIFICULTADES.get, key="pr_dificultad")
    semilla = c3.number_input("Semilla (opcional)", value=None, step=1, key="pr_semilla",
                              help="La misma semilla genera siempre el mismo ejercicio.")

    if st.button("Generar práctica", type="primary", key="pr_generar"):
        st.session_state["pr_practica"] = generar(modulo, dificultad, int(semilla) if semilla is not None else None)
        st.session_state.pop("pr_feedback", None)

    practica: Practica | None = st.session_state.get("pr_practica")
    if practica is None:
        st.info("Elige un módulo y la dificultad, y pulsa **Generar práctica**.")
        return

    st.divider()
    st.subheader(practica.titulo)
    st.caption(f"{MODULOS[practica.modulo]} · {DIFICULTADES[practica.dificultad]} · semilla {practica.semilla}")
    st.markdown(practica.enunciado)

    st.markdown("#### Tus respuestas")
    respuestas: dict[str, float | None] = {}
    for q in practica.preguntas:
        respuestas[q.id] = st.number_input(q.etiqueta, value=None, key=_clave(practica, q.id), format="%.2f")

    if st.button("Revisar respuestas", key="pr_revisar"):
        st.session_state["pr_feedback"] = (practica.semilla, practica.modulo, practica.dificultad,
                                           evaluar(practica, respuestas))

    guardado = st.session_state.get("pr_feedback")
    if guardado and guardado[:3] == (practica.semilla, practica.modulo, practica.dificultad):
        fb = guardado[3]
        st.divider()
        st.markdown("#### Retroalimentación")
        (st.success if fb.puntaje == fb.total else st.warning if fb.puntaje else st.error)(fb.resumen)
        for item in fb.items:
            icono = "✅" if item.correcta else "❌"
            propia = "sin responder" if item.respuesta is None else f"{item.respuesta:g}"
            st.markdown(f"{icono} **{item.etiqueta}** — tu respuesta: `{propia}`. {item.mensaje}")
        for pista in fb.pistas:
            st.info(pista, icon="💡")
        with st.expander("Ver la solución paso a paso"):
            render_resultado.mostrar(fb.solucion, clave="pr_sol", datos=practica.datos, enunciado=practica.enunciado)
