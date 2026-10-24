"""Cliente de IA (Google Gemini) para extraer datos de enunciados.

La IA SOLO traduce texto a JSON; todo el cálculo lo hace el motor en Python.

Clave de API:
- Por defecto se lee de la variable de entorno ``GEMINI_API_KEY`` (nunca va en el
  código ni en la imagen/repositorio).
- La interfaz puede pasar otra clave (``api_key``), que tiene prioridad.

Modelos: se prueban en orden hasta que uno responde (lista configurable con la
variable de entorno ``GEMINI_MODELOS``, separada por comas).

El SDK (``google-genai``) se importa de forma perezosa: el resto de la aplicación
funciona aunque no esté instalado.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, Literal

from pydantic import BaseModel, ValidationError

from core import validador
from core.esquemas import ExtraccionAsignacion, ExtraccionEOQ, ExtraccionPL, ExtraccionTransporte
from llm.prompts import PROMPT_PREGUNTA, PROMPTS

MODELOS_POR_DEFECTO = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
]
TIEMPO_TOTAL_S = 30.0  # tope para toda la consulta, sumando todos los modelos
MAX_CARACTERES = 6000

MAX_CARACTERES_PREGUNTA = 1000

MENSAJES: dict[str, str] = {
    "sin_clave": "No hay una clave de IA configurada. Ingresa tu clave de Google AI Studio en la barra lateral "
                 "(Configuración de IA) o usa el modo manual.",
    "clave_invalida": "La clave de IA no es válida o fue revocada. Cámbiala en la barra lateral "
                      "(Configuración de IA) o usa el modo manual.",
    "cuota": "Se agotó el límite de uso de la clave de IA. Espera unos minutos o ingresa otra clave en la barra "
             "lateral (Configuración de IA).",
    "saturado": "El servicio de IA está saturado en este momento. Intenta de nuevo en unos segundos o usa el modo manual.",
    "red": "No se pudo conectar con el servicio de IA. Revisa tu conexión o usa el modo manual.",
    "json_invalido": "La IA no devolvió datos en el formato esperado. Reformula el enunciado o usa el modo manual.",
    "texto_vacio": "Escribe primero el enunciado del problema.",
    "texto_largo": f"El enunciado es demasiado largo (máximo {MAX_CARACTERES} caracteres).",
    "pregunta_vacia": "Escribe primero tu pregunta.",
    "pregunta_larga": f"La pregunta es demasiado larga (máximo {MAX_CARACTERES_PREGUNTA} caracteres).",
    "respuesta_vacia": "La IA no devolvió una respuesta. Intenta reformular la pregunta.",
    "desconocido": "La IA no pudo procesar la solicitud. Usa el modo manual.",
}
# Si hubo varios errores distintos, se informa el más útil para el usuario.
_PRIORIDAD = ["cuota", "saturado", "red", "json_invalido", "respuesta_vacia", "desconocido"]

ESQUEMAS: dict[str, type[BaseModel]] = {
    "pl": ExtraccionPL,
    "eoq": ExtraccionEOQ,
    "transporte": ExtraccionTransporte,
    "asignacion": ExtraccionAsignacion,
}
_FALTANTES: dict[str, Callable[[Any], list[str]]] = {
    "pl": validador.faltantes_pl,
    "eoq": validador.faltantes_eoq,
    "transporte": validador.faltantes_transporte,
    "asignacion": validador.faltantes_asignacion,
}


class ResultadoIA(BaseModel):
    ok: bool
    datos: Any | None = None  # instancia del esquema de extracción
    texto: str | None = None  # respuesta en texto (preguntas sobre un ejercicio)
    faltantes: list[str] = []
    error: str | None = None
    mensaje: str = ""
    modelo: str | None = None


# --------------------------------------------------------------------------- #
# Configuración
# --------------------------------------------------------------------------- #
import os
import streamlit as st

def clave_por_defecto() -> str | None:
    # 1º prioridad: st.secrets (Streamlit Cloud y local)
    try:
        clave = st.secrets.get("GEMINI_API_KEY")
        if clave and str(clave).strip():
            return str(clave).strip()
    except Exception:
        # st.secrets lanza si no existe secrets.toml; se ignora
        pass
    # 2º: variable de entorno (útil en tests o ejecución fuera de Streamlit)
    return (os.environ.get("GEMINI_API_KEY") or "").strip() or None


def lista_modelos() -> list[str]:
    crudo = os.environ.get("GEMINI_MODELOS", "")
    modelos = [m.strip() for m in crudo.split(",") if m.strip()]
    return modelos or list(MODELOS_POR_DEFECTO)


def _crear_cliente(clave: str):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=clave,
        http_options=types.HttpOptions(
            timeout=20_000,  # milisegundos
            retry_options=types.HttpRetryOptions(
                attempts=2, initial_delay=1.0, max_delay=5.0, exp_base=2.0,
                http_status_codes=[408, 500, 502, 503, 504],
            ),
        ),
    )


def _config(instrucciones: str, esquema: type[BaseModel], con_esquema: bool):
    from google.genai import types

    if con_esquema:
        return types.GenerateContentConfig(
            system_instruction=instrucciones, response_mime_type="application/json",
            response_schema=esquema, temperature=0,
        )
    # Respaldo: si el servicio rechaza el esquema, se describe en el propio prompt.
    esquema_txt = json.dumps(esquema.model_json_schema(), ensure_ascii=False)
    return types.GenerateContentConfig(
        system_instruction=f"{instrucciones}\nESQUEMA JSON DE LA RESPUESTA:\n{esquema_txt}",
        response_mime_type="application/json", temperature=0,
    )


# --------------------------------------------------------------------------- #
# Errores
# --------------------------------------------------------------------------- #
def clasificar_error(exc: BaseException) -> str:
    """Convierte una excepción del SDK en: clave_invalida, cuota, saturado, modelo_no_disponible,
    solicitud_invalida, red o desconocido."""
    codigo = getattr(exc, "code", None)
    estado = str(getattr(exc, "status", "") or "").upper()
    msg = str(getattr(exc, "message", "") or exc).lower()
    if "api key" in msg or "api_key" in msg or estado in {"UNAUTHENTICATED", "PERMISSION_DENIED"} or codigo in (401, 403):
        return "clave_invalida"
    if codigo == 429 or estado == "RESOURCE_EXHAUSTED" or "quota" in msg:
        return "cuota"
    if codigo in (500, 502, 503, 504) or estado in {"UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED"} or "overloaded" in msg:
        return "saturado"
    if codigo == 404 or estado == "NOT_FOUND":
        return "modelo_no_disponible"
    if codigo == 400 or estado == "INVALID_ARGUMENT":
        return "solicitud_invalida"
    nombre = type(exc).__name__.lower()
    if isinstance(exc, (TimeoutError, ConnectionError)) or "timeout" in nombre or "connect" in nombre:
        return "red"
    return "desconocido"


def _error(tipo: str) -> ResultadoIA:
    return ResultadoIA(ok=False, error=tipo, mensaje=MENSAJES[tipo])


def _parsear(esquema: type[BaseModel], texto: str | None) -> BaseModel:
    t = (texto or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    return esquema.model_validate_json(t)


def _ejecutar(
    cliente: Any,
    contenido: str,
    config_fn: Callable[[bool], Any],
    procesar: Callable[[Any], Any],
    modelos: list[str],
    tiempo_total: float,
    reloj: Callable[[], float],
    reintento_sin_esquema: bool,
    tipo_invalido: str,
) -> tuple[Any, str | None, str | None]:
    """Recorre los modelos hasta obtener una respuesta válida. Devuelve (valor, modelo, error)."""
    inicio = reloj()
    errores: list[str] = []
    for modelo in modelos:
        if reloj() - inicio > tiempo_total:
            break
        con_esquema = True
        intentos_invalidos = 0
        while True:
            try:
                respuesta = cliente.models.generate_content(
                    model=modelo, contents=contenido, config=config_fn(con_esquema)
                )
                return procesar(respuesta), modelo, None
            except (ValidationError, ValueError):  # respuesta ausente, truncada o fuera del esquema
                intentos_invalidos += 1
                if intentos_invalidos < 2 and reloj() - inicio <= tiempo_total:
                    continue
                errores.append(tipo_invalido)
                break
            except Exception as exc:
                tipo = clasificar_error(exc)
                if tipo == "clave_invalida":
                    return None, None, "clave_invalida"
                if tipo == "solicitud_invalida" and con_esquema and reintento_sin_esquema:
                    con_esquema = False  # un reintento sin response_schema
                    continue
                errores.append({"modelo_no_disponible": "desconocido", "solicitud_invalida": "desconocido"}.get(tipo, tipo))
                break
    for tipo in _PRIORIDAD:
        if tipo in errores:
            return None, None, tipo
    return None, None, "desconocido"


def _preparar(api_key: str | None, fabrica_cliente: Callable[[str], Any] | None):
    """Devuelve (cliente, None) o (None, ResultadoIA de error)."""
    clave = (api_key or "").strip() or clave_por_defecto()
    if not clave and fabrica_cliente is None:
        return None, _error("sin_clave")
    try:
        return (fabrica_cliente or _crear_cliente)(clave or ""), None
    except Exception:  # SDK no instalado o configuración inválida
        return None, _error("desconocido")


# --------------------------------------------------------------------------- #
# Extracción (texto -> JSON)
# --------------------------------------------------------------------------- #
def extraer(
    esquema: type[BaseModel],
    texto: str,
    instrucciones: str,
    api_key: str | None = None,
    modelos: list[str] | None = None,
    fabrica_cliente: Callable[[str], Any] | None = None,
    tiempo_total: float = TIEMPO_TOTAL_S,
    reloj: Callable[[], float] = time.monotonic,
) -> ResultadoIA:
    """Pide a la IA que traduzca ``texto`` al ``esquema``. Nunca lanza excepciones."""
    texto = (texto or "").strip()
    if not texto:
        return _error("texto_vacio")
    if len(texto) > MAX_CARACTERES:
        return _error("texto_largo")
    cliente, fallo = _preparar(api_key, fabrica_cliente)
    if fallo:
        return fallo
    datos, modelo, error = _ejecutar(
        cliente, texto, lambda con_esquema: _config(instrucciones, esquema, con_esquema),
        lambda resp: _parsear(esquema, getattr(resp, "text", None)),
        modelos or lista_modelos(), tiempo_total, reloj, reintento_sin_esquema=True, tipo_invalido="json_invalido",
    )
    return ResultadoIA(ok=True, datos=datos, modelo=modelo) if error is None else _error(error)


def extraer_modulo(
    modulo: str, texto: str, api_key: str | None = None, **opciones: Any
) -> ResultadoIA:
    """Extrae los datos de ``texto`` para un módulo ('pl', 'eoq', 'transporte' o 'asignacion')."""
    resultado = extraer(ESQUEMAS[modulo], texto, PROMPTS[modulo], api_key=api_key, **opciones)
    if resultado.ok:
        resultado.faltantes = _FALTANTES[modulo](resultado.datos)
    return resultado


# --------------------------------------------------------------------------- #
# Preguntas sobre un ejercicio ya resuelto (texto libre)
# --------------------------------------------------------------------------- #
def _config_texto():
    from google.genai import types

    return types.GenerateContentConfig(system_instruction=PROMPT_PREGUNTA, temperature=0.3)


def _texto_respuesta(respuesta: Any) -> str:
    texto = (getattr(respuesta, "text", None) or "").strip()
    if not texto:
        raise ValueError("respuesta vacía")
    return texto


def responder(
    pregunta: str,
    contexto: str,
    api_key: str | None = None,
    modelos: list[str] | None = None,
    fabrica_cliente: Callable[[str], Any] | None = None,
    tiempo_total: float = TIEMPO_TOTAL_S,
    reloj: Callable[[], float] = time.monotonic,
) -> ResultadoIA:
    """Responde una pregunta del estudiante sobre un ejercicio ya resuelto por el motor.

    ``contexto`` trae el ejercicio y el resultado calculado (ver ``llm.contexto``). La IA solo explica:
    no calcula. Nunca lanza excepciones.
    """
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return _error("pregunta_vacia")
    if len(pregunta) > MAX_CARACTERES_PREGUNTA:
        return _error("pregunta_larga")
    cliente, fallo = _preparar(api_key, fabrica_cliente)
    if fallo:
        return fallo
    prompt = f"PREGUNTA DEL ESTUDIANTE:\n{pregunta}\n\n{contexto}"
    texto, modelo, error = _ejecutar(
        cliente, prompt, lambda _: _config_texto(), _texto_respuesta,
        modelos or lista_modelos(), tiempo_total, reloj, reintento_sin_esquema=False, tipo_invalido="respuesta_vacia",
    )
    return ResultadoIA(ok=True, texto=texto, modelo=modelo) if error is None else _error(error)
