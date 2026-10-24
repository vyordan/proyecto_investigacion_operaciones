"""Preguntas sobre un ejercicio resuelto: contexto enviado a la IA y respuesta mostrada."""
import json

from algoritmos import inventarios, simplex
from llm import cliente
from llm.cliente import responder
from llm.contexto import contexto_ejercicio, tabla_a_texto
from llm.prompts import PROMPT_PREGUNTA

RUBRICA = {
    "objetivo": "max", "coef_objetivo": [40, 30], "nombres_variables": ["x", "y"],
    "restricciones": [{"coeficientes": [2, 1], "signo": "<=", "rhs": 100},
                      {"coeficientes": [1, 2], "signo": "<=", "rhs": 80}],
}


class Resp:
    def __init__(self, text):
        self.text = text


class ClienteFalso:
    def __init__(self, guion):
        self.guion, self.llamadas, self.models = list(guion), [], self

    def generate_content(self, model, contents, config):
        self.llamadas.append({"model": model, "contents": contents, "config": config})
        paso = self.guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return Resp(paso)


def _contexto():
    return contexto_ejercicio(simplex.resolver_datos(RUBRICA), datos=RUBRICA, enunciado="Maximiza Z = 40x + 30y")


def test_contexto_incluye_ejercicio_resultado_y_procedimiento():
    c = _contexto()
    assert "EJERCICIO:" in c and "Maximiza Z = 40x + 30y" in c
    assert '"coef_objetivo": [40, 30]' in c
    assert "RESULTADO CALCULADO POR EL MOTOR:" in c and "Z = 2200" in c and "x = 40" in c
    assert "PROCEDIMIENTO PASO A PASO:" in c and "Iteración 1" in c
    assert "fila del pivote" in c  # las tablas indican dónde está el pivote


def test_contexto_se_recorta_conservando_la_solucion():
    res = simplex.resolver_datos(RUBRICA)
    c = contexto_ejercicio(res, datos=RUBRICA, limite=1500)
    assert "omitido(s) por longitud" in c
    assert "Verificación en las restricciones" in c  # los últimos pasos se conservan
    assert "Resumen:" in c and "Z = 2200" in c       # la cabecera nunca se recorta


def test_contexto_con_valores_fraccionarios_muestra_exacto_y_decimal():
    res = simplex.resolver_datos({"objetivo": "max", "coef_objetivo": [5, 4],
                                  "restricciones": [{"coeficientes": [6, 4], "signo": "<=", "rhs": 24},
                                                    {"coeficientes": [1, 2], "signo": "<=", "rhs": 6}]})
    assert "x2 = 3/2 (≈ 1.5)" in contexto_ejercicio(res)


def test_contexto_de_eoq_y_advertencias():
    res = inventarios.resolver_datos({"demanda": 1000, "costo_pedido": 10, "costo_mantener": 2.5})
    c = contexto_ejercicio(res)
    assert "Advertencias:" in c and "plazo de entrega" in c


def test_tabla_a_texto():
    res = simplex.resolver_datos(RUBRICA)
    tabla = next(p.tabla for p in res.pasos if p.titulo.startswith("Iteración 1"))
    texto = tabla_a_texto(tabla)
    assert texto.splitlines()[0].startswith("Base | x | y") and "Razón" in texto


def test_el_prompt_enviado_lleva_pregunta_ejercicio_y_resultado():
    falso = ClienteFalso(["Entra y porque tiene el coeficiente más negativo."])
    res = responder("¿Por qué entra y?", _contexto(), api_key="k", modelos=["m"], fabrica_cliente=lambda c: falso)
    assert res.ok and res.texto.startswith("Entra y")
    enviado = falso.llamadas[0]["contents"]
    assert enviado.startswith("PREGUNTA DEL ESTUDIANTE:\n¿Por qué entra y?")
    assert "EJERCICIO:" in enviado and "RESULTADO CALCULADO POR EL MOTOR:" in enviado
    assert falso.llamadas[0]["config"].system_instruction == PROMPT_PREGUNTA


def test_el_prompt_prohibe_recalcular():
    assert "NO los" in PROMPT_PREGUNTA and "recalcules" in PROMPT_PREGUNTA
    assert "no des cifras nuevas" in PROMPT_PREGUNTA


def test_errores_de_responder():
    contexto = _contexto()
    assert responder("   ", contexto, api_key="k").error == "pregunta_vacia"
    assert responder("x" * 1001, contexto, api_key="k").error == "pregunta_larga"

    class Error(Exception):
        code, status, message = 400, "INVALID_ARGUMENT", "API key not valid"

    falso = ClienteFalso([Error()])
    r = responder("¿por qué?", contexto, api_key="k", modelos=["m1", "m2"], fabrica_cliente=lambda c: falso)
    assert r.error == "clave_invalida" and len(falso.llamadas) == 1

    class Saturado(Exception):
        code, status, message = 503, "UNAVAILABLE", "overloaded"

    falso = ClienteFalso([Saturado(), "Respuesta del segundo modelo"])
    r = responder("¿por qué?", contexto, api_key="k", modelos=["m1", "m2"], fabrica_cliente=lambda c: falso)
    assert r.ok and r.modelo == "m2"


def test_respuesta_vacia_se_reintenta_y_luego_informa():
    falso = ClienteFalso(["", "  ", "", ""])
    r = responder("¿por qué?", _contexto(), api_key="k", modelos=["m1", "m2"], fabrica_cliente=lambda c: falso)
    assert r.error == "respuesta_vacia" and len(falso.llamadas) == 4
    falso = ClienteFalso(["", "ahora sí"])
    r = responder("¿por qué?", _contexto(), api_key="k", modelos=["m1"], fabrica_cliente=lambda c: falso)
    assert r.ok and r.texto == "ahora sí"


def test_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert responder("¿por qué?", _contexto()).error == "sin_clave"


def test_responder_con_config_real_del_sdk():
    """Sin red: la configuración de texto se construye con el SDK real."""
    cfg = cliente._config_texto()
    assert cfg.system_instruction == PROMPT_PREGUNTA and cfg.response_mime_type is None
