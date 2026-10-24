"""Pruebas del modo IA sin red: cliente simulado + serialización real de esquemas con el SDK."""
import json

import pytest

from core.esquemas import ExtraccionEOQ, ExtraccionPL
from llm import cliente
from llm.cliente import ResultadoIA, clasificar_error, extraer, extraer_modulo
from llm.prompts import PROMPTS

JSON_PL = {
    "titulo": "Taller", "objetivo": "max", "coef_objetivo": [40, 30], "nombres_variables": ["x", "y"],
    "descripciones_variables": ["Mesas", "Sillas"],
    "restricciones": [
        {"coeficientes": [2, 1], "signo": "<=", "rhs": 100, "nombre": "Carpintería"},
        {"coeficientes": [1, 2], "signo": "<=", "rhs": 80, "nombre": "Pintura"},
    ],
}


class ErrorAPI(Exception):
    def __init__(self, code, status="", message=""):
        super().__init__(message)
        self.code, self.status, self.message = code, status, message


class Respuesta:
    def __init__(self, texto):
        self.text = texto


class ClienteFalso:
    """Devuelve, en orden, respuestas o excepciones programadas; guarda las llamadas."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.llamadas = []
        self.models = self

    def generate_content(self, model, contents, config):
        self.llamadas.append({"model": model, "config": config})
        paso = self.guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return Respuesta(paso if isinstance(paso, str) else json.dumps(paso))


def _extraer(guion, **kw):
    falso = ClienteFalso(guion)
    res = extraer(ExtraccionPL, "enunciado", "prompt", api_key="k", modelos=["m1", "m2"],
                  fabrica_cliente=lambda clave: falso, **kw)
    return res, falso


def test_exito():
    res, falso = _extraer([JSON_PL])
    assert res.ok and res.modelo == "m1" and res.datos.coef_objetivo == [40, 30]
    assert len(falso.llamadas) == 1


def test_json_con_cercas_markdown():
    res, _ = _extraer(["```json\n" + json.dumps(JSON_PL) + "\n```"])
    assert res.ok


def test_saturado_pasa_al_siguiente_modelo():
    res, falso = _extraer([ErrorAPI(503, "UNAVAILABLE", "The model is overloaded"), JSON_PL])
    assert res.ok and res.modelo == "m2" and [c["model"] for c in falso.llamadas] == ["m1", "m2"]


def test_clave_invalida_no_prueba_mas_modelos():
    res, falso = _extraer([ErrorAPI(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key.")])
    assert not res.ok and res.error == "clave_invalida" and len(falso.llamadas) == 1
    assert "barra lateral" in res.mensaje


def test_cuota_agotada_en_todos_los_modelos():
    res, falso = _extraer([ErrorAPI(429, "RESOURCE_EXHAUSTED", "Quota exceeded")] * 2)
    assert res.error == "cuota" and len(falso.llamadas) == 2


def test_json_invalido_se_reintenta_una_vez_y_luego_cambia_de_modelo():
    res, falso = _extraer(["no es json", "{roto", JSON_PL])
    assert res.ok and res.modelo == "m2" and len(falso.llamadas) == 3
    res, _ = _extraer(["no es json", "{roto", "x", "y"])
    assert res.error == "json_invalido"


def test_json_que_no_cumple_el_esquema():
    res, _ = _extraer([{"objetivo": ["no", "es", "texto"]}] * 4)
    assert res.error == "json_invalido"


def test_esquema_rechazado_reintenta_sin_response_schema():
    res, falso = _extraer([ErrorAPI(400, "INVALID_ARGUMENT", "Unsupported schema"), JSON_PL])
    assert res.ok and len(falso.llamadas) == 2
    assert falso.llamadas[0]["config"].response_schema is not None
    assert falso.llamadas[1]["config"].response_schema is None
    assert "ESQUEMA JSON" in falso.llamadas[1]["config"].system_instruction


def test_error_de_red_y_desconocido():
    res, _ = _extraer([TimeoutError("lento")] * 2)
    assert res.error == "red"
    res, _ = _extraer([RuntimeError("???")] * 2)
    assert res.error == "desconocido"


def test_texto_vacio_largo_y_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert extraer(ExtraccionPL, "  ", "p", api_key="k").error == "texto_vacio"
    assert extraer(ExtraccionPL, "x" * 7000, "p", api_key="k").error == "texto_largo"
    assert extraer(ExtraccionPL, "enunciado", "p").error == "sin_clave"
    monkeypatch.setenv("GEMINI_API_KEY", "  clave-env ")
    assert cliente.clave_por_defecto() == "clave-env"


def test_tope_de_tiempo_total():
    tiempos = iter([0, 0, 100, 100, 100])
    falso = ClienteFalso([ErrorAPI(503, "UNAVAILABLE", "x")] * 4)
    res = extraer(ExtraccionPL, "t", "p", api_key="k", modelos=["m1", "m2", "m3"], fabrica_cliente=lambda c: falso,
                  tiempo_total=30, reloj=lambda: next(tiempos))
    assert not res.ok and len(falso.llamadas) == 1


def test_lista_de_modelos_configurable(monkeypatch):
    monkeypatch.setenv("GEMINI_MODELOS", "a, b ,c")
    assert cliente.lista_modelos() == ["a", "b", "c"]
    monkeypatch.delenv("GEMINI_MODELOS")
    assert cliente.lista_modelos() == cliente.MODELOS_POR_DEFECTO


def test_extraer_modulo_calcula_faltantes():
    falso = ClienteFalso([{"demanda": 1000, "costo_pedido": 10}])
    res = extraer_modulo("eoq", "enunciado", api_key="k", modelos=["m"], fabrica_cliente=lambda c: falso)
    assert res.ok and res.faltantes == ["Costo de mantener (H)"]
    assert falso.llamadas[0]["config"].system_instruction == PROMPTS["eoq"]


def test_prompts_exigen_null_y_no_calcular():
    for texto in PROMPTS.values():
        assert "NO resuelvas" in texto and "null" in texto


def test_clasificacion_con_errores_reales_del_sdk():
    errors = pytest.importorskip("google.genai.errors")
    assert clasificar_error(errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})) == "cuota"
    assert clasificar_error(errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})) == "saturado"
    assert clasificar_error(errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid.", "status": "INVALID_ARGUMENT"}})) == "clave_invalida"
    assert clasificar_error(errors.ClientError(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}})) == "clave_invalida"
    assert clasificar_error(errors.ClientError(404, {"error": {"code": 404, "message": "model not found", "status": "NOT_FOUND"}})) == "modelo_no_disponible"


@pytest.mark.parametrize("esquema", list(cliente.ESQUEMAS.values()))
def test_los_esquemas_se_serializan_para_el_sdk_real(esquema):
    """Sin red: se captura la petición que el SDK enviaría y se comprueba que incluye el esquema."""
    genai = pytest.importorskip("google.genai")
    capturado = {}

    class Detener(Exception):
        pass

    c = genai.Client(api_key="clave-falsa")

    def espia(metodo, ruta, cuerpo, *a, **k):
        capturado["cuerpo"] = cuerpo
        raise Detener()

    c._api_client.request = espia
    with pytest.raises(Detener):
        c.models.generate_content(model="gemini-x", contents="hola", config=cliente._config("sistema", esquema, True))
    gen = capturado["cuerpo"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json"
    assert "properties" in json.dumps(gen["responseSchema"])
