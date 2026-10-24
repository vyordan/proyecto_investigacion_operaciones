import pytest

from algoritmos import simplex
from core.resultado import Estado

RUBRICA = {
    "objetivo": "max",
    "coef_objetivo": [40, 30],
    "nombres_variables": ["x", "y"],
    "restricciones": [
        {"coeficientes": [2, 1], "signo": "<=", "rhs": 100},
        {"coeficientes": [1, 2], "signo": "<=", "rhs": 80},
    ],
}


def _r(coef, restr, objetivo="max", **extra):
    datos = {"objetivo": objetivo, "coef_objetivo": coef,
             "restricciones": [{"coeficientes": c, "signo": s, "rhs": b} for c, s, b in restr]}
    datos.update(extra)
    return simplex.resolver_datos(datos)


def test_ejemplo_de_la_rubrica():
    r = simplex.resolver_datos(RUBRICA)
    assert r.estado == Estado.OPTIMO
    assert r.exactos == {"x": "40", "y": "20", "Z": "2200"}
    assert "R1" in r.interpretacion and "R2" in r.interpretacion
    # Tabla inicial con razones, tabla final y verificación
    titulos = [p.titulo for p in r.pasos]
    assert titulos[:3] == ["Modelo del problema", "Forma estándar", "Iteración 1 (tabla inicial)"]
    assert "Tabla final (óptima)" in titulos
    final = next(p for p in r.pasos if p.titulo == "Tabla final (óptima)").tabla
    assert final.filas[-1][-1] == "2200"  # valor de Z


def test_solucion_fraccionaria_exacta():
    r = _r([5, 4], [([6, 4], "<=", 24), ([1, 2], "<=", 6)])
    assert r.exactos["x1"] == "3" and r.exactos["x2"] == "3/2" and r.exactos["Z"] == "21"


def test_minimizacion_con_mayor_o_igual_dos_fases():
    r = _r([3, 2], [([1, 1], ">=", 4), ([1, 3], ">=", 6)], objetivo="min")
    assert r.estado == Estado.OPTIMO
    assert r.valores == {"x1": 0.0, "x2": 4.0, "Z": 8.0}
    titulos = [p.titulo for p in r.pasos]
    assert any(t.startswith("Fase 1") for t in titulos) and any(t.startswith("Fase 2") for t in titulos)


def test_restriccion_de_igualdad():
    r = _r([1, 2], [([1, 1], "=", 4), ([1, 0], "<=", 3)])
    assert r.estado == Estado.OPTIMO and r.valores["Z"] == 8.0 and r.valores["x2"] == 4.0


def test_lado_derecho_negativo_se_normaliza():
    r = _r([2, 1], [([-1, -1], "<=", -4), ([1, 0], "<=", 10)], objetivo="min")
    assert r.estado == Estado.OPTIMO and r.valores["Z"] == 4.0
    assert any("negativo" in a.mensaje for a in r.advertencias)


def test_infactible():
    r = _r([1, 1], [([1, 1], "<=", 2), ([1, 1], ">=", 5)])
    assert r.estado == Estado.INFACTIBLE and not r.exitoso
    assert "infactible" in r.resumen


def test_no_acotado():
    r = _r([1, 1], [([1, -1], "<=", 2)])
    assert r.estado == Estado.NO_ACOTADO and not r.exitoso


def test_multiples_optimos():
    r = _r([1, 1], [([1, 1], "<=", 4), ([1, 0], "<=", 3)])
    assert r.estado == Estado.MULTIPLES_OPTIMOS and r.valores["Z"] == 4.0
    assert {"alt_x1", "alt_x2"} <= set(r.valores)
    assert any(p.titulo == "Óptimos alternativos" for p in r.pasos)


def test_degenerado_termina_y_es_correcto():
    r = _r([1, 1], [([1, 0], "<=", 2), ([0, 1], "<=", 2), ([1, 1], "<=", 4)])
    assert r.estado in (Estado.OPTIMO, Estado.MULTIPLES_OPTIMOS) and r.valores["Z"] == 4.0


def test_restriccion_redundante_en_igualdades():
    r = _r([1, 1], [([1, 1], "=", 3), ([2, 2], "=", 6), ([1, 0], "<=", 2)])
    assert r.exitoso and r.valores["Z"] == 3.0


def test_nombres_y_descripciones_en_la_interpretacion():
    r = simplex.resolver_datos({**RUBRICA, "descripciones_variables": ["mesas", "sillas"]})
    assert "mesas: 40" in r.interpretacion and "sillas: 20" in r.interpretacion


def test_datos_invalidos_no_lanzan_excepcion():
    r = simplex.resolver_datos({"objetivo": "max", "coef_objetivo": [1, 2], "restricciones": []})
    assert r.estado == Estado.ERROR_DATOS and r.advertencias
    r = simplex.resolver_datos("esto no es json")
    assert r.estado == Estado.ERROR_DATOS
    r = simplex.resolver_datos(None)
    assert r.estado == Estado.ERROR_DATOS


def test_resultado_serializable_a_json():
    r = simplex.resolver_datos(RUBRICA)
    texto = r.model_dump_json()
    assert '"estado":"optimo"' in texto
