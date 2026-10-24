"""Caja «Pregunta sobre este ejercicio» en la interfaz (respuestas de la IA simuladas)."""
import pathlib

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from llm import cliente
from llm.cliente import ResultadoIA

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _abrir(pagina):
    at = AppTest.from_file(str(RAIZ / "main.py"), default_timeout=30).run()
    at.sidebar.radio[0].set_value(pagina).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _boton(at, clave):
    return next(b for b in at.button if b.key == clave)


def _resolver_pl(at):
    next(b for b in at.button if b.label == "Cargar ejemplo").click().run()
    _boton(at, "pl_resolver").click().run()
    assert not at.exception, [e.value for e in at.exception]


def _preguntar(at, clave, texto):
    at.text_area(key=f"{clave}_qa_texto").set_value(texto).run()
    _boton(at, f"{clave}_qa_boton").click().run()
    assert not at.exception, [e.value for e in at.exception]


def _simular(monkeypatch, respuesta="Entra y porque tiene el coeficiente más negativo.", error=None):
    llamadas = []

    def falso(pregunta, contexto, api_key=None, **kw):
        llamadas.append({"pregunta": pregunta, "contexto": contexto, "api_key": api_key})
        if error:
            return ResultadoIA(ok=False, error=error, mensaje=cliente.MENSAJES[error])
        return ResultadoIA(ok=True, texto=respuesta, modelo="falso")

    monkeypatch.setattr(cliente, "responder", falso)
    return llamadas


def test_la_caja_aparece_al_final_del_ejercicio_resuelto(monkeypatch):
    _simular(monkeypatch)
    at = _abrir("Programación lineal")
    assert not any("Pregunta sobre este ejercicio" in m.value for m in at.markdown)  # aún no hay ejercicio
    _resolver_pl(at)
    assert any("Pregunta sobre este ejercicio" in m.value for m in at.markdown)
    assert at.text_area(key="pl_qa_texto") is not None


def test_se_envia_pregunta_ejercicio_y_resultado_y_se_muestra_la_respuesta(monkeypatch):
    llamadas = _simular(monkeypatch)
    at = _abrir("Programación lineal")
    _resolver_pl(at)
    _preguntar(at, "pl", "¿Por qué entra y a la base?")

    assert len(llamadas) == 1
    assert llamadas[0]["pregunta"] == "¿Por qué entra y a la base?"
    contexto = llamadas[0]["contexto"]
    assert '"coef_objetivo": [40.0, 30.0]' in contexto or '"coef_objetivo": [40, 30]' in contexto  # el ejercicio
    assert "Z = 2200" in contexto and "Iteración 1" in contexto                                      # resultado del motor
    assert llamadas[0]["api_key"] is None                                                            # clave del proyecto

    textos = [m.value for c in at.chat_message for m in c.markdown]
    assert "¿Por qué entra y a la base?" in textos
    assert "Entra y porque tiene el coeficiente más negativo." in textos
    assert at.text_area(key="pl_qa_texto").value == ""  # el cuadro queda listo para otra pregunta


def test_varias_preguntas_se_acumulan_y_un_nuevo_calculo_reinicia(monkeypatch):
    llamadas = _simular(monkeypatch)
    at = _abrir("Programación lineal")
    _resolver_pl(at)
    _preguntar(at, "pl", "Primera pregunta")
    _preguntar(at, "pl", "Segunda pregunta")
    assert len(llamadas) == 2 and len(at.chat_message) == 4

    _boton(at, "pl_resolver").click().run()  # se vuelve a resolver (mismo resultado)
    assert len(at.chat_message) == 4  # misma huella: se conserva la conversación

    at.radio(key="pl_metodo").set_value("Método gráfico").run()
    _boton(at, "pl_resolver").click().run()  # resultado distinto -> conversación nueva
    assert len(at.chat_message) == 0


def test_pregunta_vacia_no_llama_a_la_ia(monkeypatch):
    llamadas = _simular(monkeypatch)
    at = _abrir("Programación lineal")
    _resolver_pl(at)
    _boton(at, "pl_qa_boton").click().run()
    assert not at.exception
    assert len(llamadas) == 1 and llamadas[0]["pregunta"] == ""  # la validación de texto vacío la hace responder()


def test_error_de_la_ia_se_muestra_en_la_conversacion(monkeypatch):
    _simular(monkeypatch, error="saturado")
    at = _abrir("Programación lineal")
    _resolver_pl(at)
    _preguntar(at, "pl", "¿Por qué?")
    assert any("saturado" in e.value for e in at.error)
    # el ejercicio y su procedimiento siguen visibles
    assert any("Z = 2200" in s.value for s in at.success)


def test_limite_de_consultas_con_la_clave_del_proyecto(monkeypatch):
    llamadas = _simular(monkeypatch)
    at = _abrir("Programación lineal")
    _resolver_pl(at)
    at.session_state["ia_consultas"] = 20
    _preguntar(at, "pl", "¿Por qué?")
    assert not llamadas
    assert any("límite de consultas" in e.value for e in at.error)


def test_con_clave_propia_no_hay_limite_y_se_usa_esa_clave(monkeypatch):
    llamadas = _simular(monkeypatch)
    at = _abrir("Programación lineal")
    _resolver_pl(at)
    at.session_state["ia_consultas"] = 20
    at.sidebar.text_input(key="ia_api_key").set_value("mi-clave").run()
    _preguntar(at, "pl", "¿Por qué?")
    assert len(llamadas) == 1 and llamadas[0]["api_key"] == "mi-clave"


def test_no_hay_caja_si_los_datos_son_invalidos(monkeypatch):
    _simular(monkeypatch)
    at = _abrir("Inventarios (EOQ)")
    next(b for b in at.button if b.label == "Calcular").click().run()
    assert not any("Pregunta sobre este ejercicio" in m.value for m in at.markdown)


def test_la_caja_esta_en_todos_los_modulos(monkeypatch):
    _simular(monkeypatch)
    for pagina, boton in (("Transporte", "tr_resolver"), ("Asignación", "as_resolver"), ("Inventarios (EOQ)", "eoq_calcular")):
        at = _abrir(pagina)
        next(b for b in at.button if b.label == "Cargar ejemplo").click().run()
        _boton(at, boton).click().run()
        assert any("Pregunta sobre este ejercicio" in m.value for m in at.markdown), pagina


def test_la_caja_esta_en_la_solucion_de_la_practica(monkeypatch):
    llamadas = _simular(monkeypatch)
    at = _abrir("Práctica")
    at.number_input(key="pr_semilla").set_value(7).run()
    _boton(at, "pr_generar").click().run()
    _boton(at, "pr_revisar").click().run()
    assert not at.exception, [e.value for e in at.exception]
    _preguntar(at, "pr_sol", "¿Cómo se resuelve?")
    assert len(llamadas) == 1
    assert "EJERCICIO:" in llamadas[0]["contexto"] and "Un taller fabrica" in llamadas[0]["contexto"]
