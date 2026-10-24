"""Los 12 ejemplos del asistente deben resolverse con el motor (no hay respuestas escritas)."""
from algoritmos import asignacion, inventarios, simplex, transporte
from core.resultado import Estado
from practica.ejercicios import EJEMPLOS, TOTAL_EJEMPLOS

MOTORES = {"pl": simplex, "eoq": inventarios, "transporte": transporte, "asignacion": asignacion}
ESPERADO = {
    "Problema no acotado": Estado.NO_ACOTADO,
    "Óptimos alternativos (infinitas soluciones)": Estado.MULTIPLES_OPTIMOS,
}


def _datos(ejemplo):
    return {k: v for k, v in ejemplo.items() if k != "titulo"}


def test_hay_al_menos_diez_ejemplos():
    assert TOTAL_EJEMPLOS >= 10
    assert all(EJEMPLOS[m] for m in MOTORES)


def test_todos_los_ejemplos_se_resuelven():
    for modulo, lista in EJEMPLOS.items():
        for ejemplo in lista:
            r = MOTORES[modulo].resolver_datos(_datos(ejemplo))
            esperado = ESPERADO.get(ejemplo["titulo"], Estado.OPTIMO)
            assert r.estado == esperado, (ejemplo["titulo"], r.estado, [a.mensaje for a in r.advertencias])


def test_valores_conocidos():
    assert simplex.resolver_datos(_datos(EJEMPLOS["pl"][0])).exactos["Z"] == "2200"
    assert transporte.resolver_datos(_datos(EJEMPLOS["transporte"][0])).valores["Z"] == 585.0
    assert asignacion.resolver_datos(_datos(EJEMPLOS["asignacion"][0])).valores["Z"] == 13.0
