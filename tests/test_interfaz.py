"""Pruebas de humo de la interfaz con el simulador de Streamlit (sin navegador)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

RAIZ = __import__("pathlib").Path(__file__).resolve().parent.parent


def _abrir(pagina: str) -> AppTest:
    at = AppTest.from_file(str(RAIZ / "main.py"), default_timeout=30).run()
    at.sidebar.radio[0].set_value(pagina).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _boton(at: AppTest, etiqueta: str):
    return next(b for b in at.button if b.label == etiqueta)


@pytest.mark.parametrize(
    "pagina, boton_calcular, esperado",
    [
        ("Programación lineal", "Resolver", "Z = 2200"),
        ("Transporte", "Resolver", "Z = 585"),
        ("Asignación", "Resolver", "Z = 13"),
        ("Inventarios (EOQ)", "Calcular", "Q* ≈ 89.44"),
    ],
)
def test_cargar_ejemplo_y_resolver(pagina, boton_calcular, esperado):
    at = _abrir(pagina)
    _boton(at, "Cargar ejemplo").click().run()
    _boton(at, boton_calcular).click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any(esperado in s.value for s in at.success), [s.value for s in at.success]


@pytest.mark.parametrize("pagina, boton_calcular", [
    ("Programación lineal", "Resolver"), ("Transporte", "Resolver"),
    ("Asignación", "Resolver"), ("Inventarios (EOQ)", "Calcular"),
])
def test_formulario_vacio_muestra_errores_sin_caerse(pagina, boton_calcular):
    at = _abrir(pagina)
    _boton(at, boton_calcular).click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.error) >= 2  # el resumen y al menos un mensaje concreto


def test_metodo_grafico_desde_la_interfaz():
    at = _abrir("Programación lineal")
    at.radio(key="pl_metodo").set_value("Método gráfico").run()
    _boton(at, "Cargar ejemplo").click().run()
    _boton(at, "Resolver").click().run()
    assert not at.exception
    assert any("x = 40, y = 20" in s.value for s in at.success)


def test_practica_generar_y_corregir():
    from practica import generador

    at = _abrir("Práctica")
    at.number_input(key="pr_semilla").set_value(7).run()
    _boton(at, "Generar práctica").click().run()
    assert not at.exception, [e.value for e in at.exception]
    practica = generador.generar("pl", "facil", 7)
    assert practica.enunciado.split("\n")[0][:30] in "".join(m.value for m in at.markdown)

    # Con las respuestas correctas -> nota completa
    sol = generador.resolver(practica)
    for q in practica.preguntas:
        at.number_input(key=f"pr_resp_pl_facil_7_{q.id}").set_value(round(generador._esperado(practica, sol, q.id), 2))
    at.run()
    _boton(at, "Revisar respuestas").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Excelente" in s.value for s in at.success), [s.value for s in at.success]


def test_practica_con_respuesta_incorrecta_muestra_pistas():
    at = _abrir("Práctica")
    at.number_input(key="pr_semilla").set_value(7).run()
    _boton(at, "Generar práctica").click().run()
    for k in [n.key for n in at.number_input if n.key and n.key.startswith("pr_resp_")]:
        at.number_input(key=k).set_value(1000.0)
    at.run()
    _boton(at, "Revisar respuestas").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("no se cumple" in i.value for i in at.info)
