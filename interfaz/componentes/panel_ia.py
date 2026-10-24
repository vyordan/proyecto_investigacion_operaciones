"""Panel «Describir el problema con IA» y configuración de la clave.

La IA solo traduce el enunciado a datos y pre-llena el formulario del módulo;
el usuario los revisa y el cálculo lo hace siempre el motor en Python.
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from llm import cliente

# Con la clave del proyecto (compartida) se limita el uso por sesión; con la clave propia no.
LIMITE_CONSULTAS_SESION = 20
_SIN_CONTAR = {"texto_vacio", "texto_largo", "pregunta_vacia", "pregunta_larga", "sin_clave"}


def clave_activa() -> str | None:
    """Clave ingresada por el usuario en la barra lateral (tiene prioridad sobre la del proyecto)."""
    return (st.session_state.get("ia_api_key") or "").strip() or None


def configuracion_ia() -> None:
    """Sección de la barra lateral para cambiar la clave de IA."""
    with st.expander("⚙️ Configuración de IA"):
        st.text_input(
            "Tu clave de Google AI Studio (opcional)", type="password", key="ia_api_key",
            help="Si la clave del proyecto falla o se agota, ingresa aquí la tuya. Solo se guarda en esta sesión.",
        )
        if clave_activa():
            st.caption("Usando **tu clave**.")
        elif cliente.clave_por_defecto():
            st.caption("Usando la **clave del proyecto**.")
        else:
            st.warning("No hay clave de IA configurada. El modo manual sigue disponible.")


def consulta_permitida() -> bool:
    """Con la clave del proyecto hay un tope de consultas por sesión; con la clave propia no."""
    return clave_activa() is not None or st.session_state.get("ia_consultas", 0) < LIMITE_CONSULTAS_SESION


def contar_consulta(res: Any) -> None:
    """Suma una consulta al contador de la sesión (solo con la clave del proyecto y si realmente se intentó)."""
    if clave_activa() is None and res.error not in _SIN_CONTAR:
        st.session_state["ia_consultas"] = st.session_state.get("ia_consultas", 0) + 1


def _consultar(modulo: str, texto: str, aplicar: Callable[[Any], None]) -> list[tuple[str, str]]:
    if not consulta_permitida():
        return [("warning", "Alcanzaste el límite de consultas de IA con la clave del proyecto en esta sesión. "
                            "Ingresa tu propia clave en la barra lateral o usa el modo manual.")]
    with st.spinner("Consultando a la IA…"):
        res = cliente.extraer_modulo(modulo, texto, api_key=clave_activa())
    contar_consulta(res)
    if not res.ok:
        return [("error", res.mensaje)]
    aplicar(res.datos)
    mensajes = [("success", "Datos extraídos. **Revisa el formulario** antes de calcular: la IA solo traduce el "
                            "texto y puede equivocarse.")]
    if res.faltantes:
        mensajes.append(("warning", "La IA no encontró: " + "; ".join(res.faltantes) + ". Complétalos en el formulario."))
    return mensajes


def panel_ia(modulo: str, clave: str, aplicar: Callable[[Any], None], ejemplo: str = "") -> None:
    """Muestra el panel. ``aplicar`` recibe los datos extraídos y pre-llena el formulario.

    Debe colocarse ANTES del formulario del módulo (así el formulario ya nace con los datos).
    """
    with st.expander("🤖 Describir el problema con IA (opcional)"):
        texto = st.text_area("Enunciado del problema", key=f"{clave}_ia_texto", height=150, placeholder=ejemplo)
        if st.button("Extraer datos con IA", key=f"{clave}_ia_boton"):
            st.session_state[f"{clave}_ia_msg"] = _consultar(modulo, texto, aplicar)
        for nivel, mensaje in st.session_state.get(f"{clave}_ia_msg", []):
            getattr(st, nivel)(mensaje)
