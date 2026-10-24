"""Caja «Pregunta sobre este ejercicio»: al final de cada ejercicio resuelto.

Se envía a la IA la pregunta del estudiante, el ejercicio y el resultado calculado por el motor
(más el procedimiento); se muestra la respuesta. La IA solo explica: no recalcula.
"""
from __future__ import annotations

import hashlib
from typing import Any

import streamlit as st

from core.resultado import Estado, Resultado
from interfaz.componentes.panel_ia import clave_activa, consulta_permitida, contar_consulta
from llm import cliente
from llm.contexto import contexto_ejercicio

_SIN_CAJA = {Estado.ERROR_DATOS, Estado.ERROR_INTERNO}
_LIMITE_MSG = (
    "Alcanzaste el límite de consultas de IA con la clave del proyecto en esta sesión. "
    "Ingresa tu propia clave en la barra lateral (Configuración de IA)."
)


def _al_pulsar(clave: str) -> None:
    """Callback: guarda la pregunta pendiente y limpia el cuadro de texto."""
    st.session_state[f"{clave}_qa_pendiente"] = (st.session_state.get(f"{clave}_qa_texto") or "").strip()
    st.session_state[f"{clave}_qa_texto"] = ""


def caja_pregunta(res: Resultado, clave: str, datos: dict[str, Any] | None = None, enunciado: str | None = None) -> None:
    if res.estado in _SIN_CAJA:
        return

    st.divider()
    st.markdown("#### 💬 Pregunta sobre este ejercicio")
    st.caption("La IA responde con base en el ejercicio y en el resultado calculado por el motor; no recalcula.")

    # Cada cálculo nuevo reinicia la conversación.
    huella = hashlib.md5(res.model_dump_json().encode()).hexdigest()
    if st.session_state.get(f"{clave}_qa_huella") != huella:
        st.session_state[f"{clave}_qa_huella"] = huella
        st.session_state[f"{clave}_qa"] = []
    historial: list[dict[str, Any]] = st.session_state.setdefault(f"{clave}_qa", [])

    pendiente = st.session_state.pop(f"{clave}_qa_pendiente", None)
    if pendiente is not None:
        if not consulta_permitida():
            historial.append({"pregunta": pendiente or "(vacía)", "respuesta": None, "error": _LIMITE_MSG})
        else:
            with st.spinner("Consultando a la IA…"):
                respuesta = cliente.responder(
                    pendiente, contexto_ejercicio(res, datos=datos, enunciado=enunciado), api_key=clave_activa()
                )
            contar_consulta(respuesta)
            historial.append(
                {
                    "pregunta": pendiente or "(vacía)",
                    "respuesta": respuesta.texto if respuesta.ok else None,
                    "error": None if respuesta.ok else respuesta.mensaje,
                }
            )

    for turno in historial:
        with st.chat_message("user"):
            st.markdown(turno["pregunta"])
        with st.chat_message("assistant"):
            if turno["respuesta"] is not None:
                st.markdown(turno["respuesta"])
            else:
                st.error(turno["error"])

    st.text_area(
        "Tu pregunta", key=f"{clave}_qa_texto", height=90,
        placeholder="p. ej., ¿Por qué entra esta variable a la base? ¿Qué significa que una restricción esté activa?",
    )
    st.button("Preguntar", key=f"{clave}_qa_boton", on_click=_al_pulsar, args=(clave,))
