"""Modo IA en la interfaz: se simula la respuesta de Gemini (sin red)."""
import pathlib

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

from core.esquemas import ExtraccionAsignacion, ExtraccionEOQ, ExtraccionPL, ExtraccionTransporte
from llm import cliente
from llm.cliente import ResultadoIA

RAIZ = pathlib.Path(__file__).resolve().parent.parent

PL = ExtraccionPL.model_validate({
    "titulo": "Taller", "objetivo": "max", "coef_objetivo": [40, 30], "nombres_variables": ["x", "y"],
    "descripciones_variables": ["Mesas a fabricar", "Sillas a fabricar"],
    "restricciones": [
        {"coeficientes": [2, 1], "signo": "<=", "rhs": 100, "nombre": "Carpintería"},
        {"coeficientes": [1, 2], "signo": "≤", "rhs": 80, "nombre": "Pintura"},
    ],
})


def _simular(monkeypatch, modulo_datos: dict, error=None):
    def falso(modulo, texto, api_key=None, **kw):
        if error:
            return ResultadoIA(ok=False, error=error, mensaje=cliente.MENSAJES[error])
        datos = modulo_datos[modulo]
        res = ResultadoIA(ok=True, datos=datos, modelo="falso")
        res.faltantes = cliente._FALTANTES[modulo](datos)
        return res

    monkeypatch.setattr(cliente, "extraer_modulo", falso)


def _abrir(pagina):
    at = AppTest.from_file(str(RAIZ / "main.py"), default_timeout=30).run()
    at.sidebar.radio[0].set_value(pagina).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _boton(at, clave):
    return next(b for b in at.button if b.key == clave)


def test_modelacion_ia_extrae_formula_y_resuelve(monkeypatch):
    _simular(monkeypatch, {"pl": PL})
    at = _abrir("Modelación")
    at.text_area(key="mod_ia_texto").set_value("Un taller fabrica mesas y sillas...").run()
    _boton(at, "mod_ia_boton").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Revisa el formulario" in s.value for s in at.success)

    _boton(at, "mod_formular").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Modelo formulado" in s.value for s in at.success)
    assert any("Mesas a fabricar" in m.value for m in at.markdown)  # descripciones de variables

    _boton(at, "mod_simplex").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Z = 2200" in s.value for s in at.success)


def test_eoq_ia_con_datos_faltantes_avisa(monkeypatch):
    _simular(monkeypatch, {"eoq": ExtraccionEOQ(demanda=1200, costo_pedido=50, periodo_demanda="anual")})
    at = _abrir("Inventarios (EOQ)")
    at.text_area(key="eoq_ia_texto").set_value("Una tienda vende 1200 cajas al año...").run()
    _boton(at, "eoq_ia_boton").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("La IA no encontró" in w.value and "Costo de mantener" in w.value for w in at.warning)
    assert at.number_input(key="eoq_demanda").value == 1200
    # El usuario completa el dato faltante y calcula con el motor
    at.number_input(key="eoq_H").set_value(3.0).run()
    next(b for b in at.button if b.label == "Calcular").click().run()
    assert not at.exception
    assert any("Q* ≈ 200" in s.value for s in at.success), [s.value for s in at.success]


def test_eoq_ia_normaliza_valores_raros(monkeypatch):
    _simular(monkeypatch, {"eoq": ExtraccionEOQ(demanda=100, costo_pedido=10, costo_mantener=2,
                                                 periodo_demanda="Mensual ", unidad_plazo="semana", plazo_entrega=2)})
    at = _abrir("Inventarios (EOQ)")
    at.text_area(key="eoq_ia_texto").set_value("texto").run()
    _boton(at, "eoq_ia_boton").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="eoq_periodo").value == "Mensual"
    assert at.selectbox(key="eoq_unidad").value == "Semanas"


def test_transporte_y_asignacion_ia(monkeypatch):
    _simular(monkeypatch, {
        "transporte": ExtraccionTransporte(oferta=[40, 50], demanda=[20, 25, 30],
                                           costos=[[4, 6, 8], [5, 3, 7]], objetivo="minimizar"),
        "asignacion": ExtraccionAsignacion(costos=[[9, 2, 7], [6, 4, 3], [5, 8, 1]]),
    })
    at = _abrir("Transporte")
    at.text_area(key="tr_ia_texto").set_value("texto").run()
    _boton(at, "tr_ia_boton").click().run()
    assert not at.exception, [e.value for e in at.exception]
    _boton(at, "tr_resolver").click().run()
    assert not at.exception and any("Costo mínimo" in s.value for s in at.success)

    at = _abrir("Asignación")
    at.text_area(key="as_ia_texto").set_value("texto").run()
    _boton(at, "as_ia_boton").click().run()
    assert not at.exception, [e.value for e in at.exception]
    _boton(at, "as_resolver").click().run()
    assert not at.exception and any("Z = 9" in s.value or "total Z" in s.value for s in at.success)


def test_error_de_ia_se_muestra_y_el_modo_manual_sigue(monkeypatch):
    _simular(monkeypatch, {}, error="clave_invalida")
    at = _abrir("Programación lineal")
    at.text_area(key="pl_ia_texto").set_value("texto").run()
    _boton(at, "pl_ia_boton").click().run()
    assert not at.exception
    assert any("barra lateral" in e.value for e in at.error)
    next(b for b in at.button if b.label == "Cargar ejemplo").click().run()
    next(b for b in at.button if b.label == "Resolver").click().run()
    assert any("Z = 2200" in s.value for s in at.success)


def test_limite_de_consultas_con_la_clave_del_proyecto(monkeypatch):
    llamadas = []
    monkeypatch.setattr(cliente, "extraer_modulo", lambda *a, **k: llamadas.append(1))
    at = _abrir("Programación lineal")
    at.session_state["ia_consultas"] = 20
    at.text_area(key="pl_ia_texto").set_value("texto").run()
    _boton(at, "pl_ia_boton").click().run()
    assert not llamadas
    assert any("límite de consultas" in w.value for w in at.warning)


def test_texto_vacio_no_cuenta_como_consulta(monkeypatch):
    monkeypatch.setattr(cliente, "extraer_modulo", lambda *a, **k: ResultadoIA(
        ok=False, error="texto_vacio", mensaje=cliente.MENSAJES["texto_vacio"]))
    at = _abrir("Programación lineal")
    _boton(at, "pl_ia_boton").click().run()
    assert "ia_consultas" not in at.session_state or at.session_state["ia_consultas"] == 0
    assert any("Escribe primero" in e.value for e in at.error)
