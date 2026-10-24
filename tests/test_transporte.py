import random

import pytest

from algoritmos import transporte
from core.resultado import Estado

# Ejemplo balanceado: costo óptimo 585 (verificado con SciPy en la última prueba de este archivo).
BALANCEADO = {
    "oferta": [20, 30, 25],
    "demanda": [10, 15, 20, 30],
    "costos": [[8, 6, 10, 9], [9, 12, 13, 7], [14, 9, 16, 5]],
}


def _costo(res):
    return res.valores["Z"]


def test_balanceado_todos_los_metodos_llegan_al_mismo_optimo():
    costos = set()
    for metodo in ("esquina_noroeste", "costo_minimo", "vogel"):
        r = transporte.resolver_datos({**BALANCEADO, "metodo_inicial": metodo})
        assert r.exitoso, (metodo, r.advertencias)
        costos.add(_costo(r))
        assert any(p.titulo.startswith("Solución inicial") for p in r.pasos)
    assert costos == {585.0}


def test_oferta_mayor_agrega_destino_ficticio():
    r = transporte.resolver_datos({"oferta": [30, 40], "demanda": [20, 25], "costos": [[4, 6], [5, 3]]})
    assert r.exitoso
    assert any(p.titulo == "Balanceo del problema" for p in r.pasos)
    assert "sin enviar" in r.interpretacion
    enviado = sum(v for k, v in r.valores.items() if k.startswith("x"))
    assert enviado == 45


def test_demanda_mayor_agrega_origen_ficticio():
    r = transporte.resolver_datos({"oferta": [20, 25], "demanda": [30, 40], "costos": [[4, 6], [5, 3]]})
    assert r.exitoso and "sin cubrir" in r.interpretacion
    enviado = sum(v for k, v in r.valores.items() if k.startswith("x"))
    assert enviado == 45


def test_maximizar():
    r = transporte.resolver_datos({"oferta": [10, 10], "demanda": [10, 10], "costos": [[5, 1], [1, 5]], "objetivo": "max"})
    assert r.exitoso and r.valores["Z"] == 100.0


def test_degenerado_usa_epsilon_y_termina():
    r = transporte.resolver_datos({"oferta": [10, 20], "demanda": [10, 20], "costos": [[1, 2], [3, 1]],
                                   "metodo_inicial": "esquina_noroeste"})
    assert r.exitoso and r.valores["Z"] == 30.0


def test_datos_invalidos():
    for datos in (
        {"oferta": [10], "demanda": [10, 5], "costos": [[1]]},       # forma distinta
        {"oferta": [-1, 5], "demanda": [2, 2], "costos": [[1, 2], [3, 4]]},
        {"oferta": [0, 0], "demanda": [1], "costos": [[1], [2]]},
        {"oferta": [1, 1], "demanda": [1, 1], "costos": [[1, 2], [3]]},
        {"oferta": [1], "demanda": [1], "costos": [[1]], "metodo_inicial": "azar"},
    ):
        r = transporte.resolver_datos(datos)
        assert r.estado == Estado.ERROR_DATOS and r.advertencias, datos


def _scipy_transporte(oferta, demanda, costos, objetivo):
    from scipy.optimize import linprog

    m, n = len(oferta), len(demanda)
    c = [float(costos[i][j]) * (-1 if objetivo == "max" else 1) for i in range(m) for j in range(n)]
    a_ub, b_ub, a_eq, b_eq = [], [], [], []
    for i in range(m):
        fila = [1.0 if k // n == i else 0.0 for k in range(m * n)]
        (a_eq if sum(oferta) < sum(demanda) else a_ub).append(fila)
        (b_eq if sum(oferta) < sum(demanda) else b_ub).append(float(oferta[i]))
    for j in range(n):
        fila = [1.0 if k % n == j else 0.0 for k in range(m * n)]
        (a_eq if sum(oferta) >= sum(demanda) else a_ub).append(fila)
        (b_eq if sum(oferta) >= sum(demanda) else b_ub).append(float(demanda[j]))
    if sum(oferta) == sum(demanda):
        a_eq, b_eq = a_eq + a_ub, b_eq + b_ub
        a_ub, b_ub = [], []
    r = linprog(c, A_ub=a_ub or None, b_ub=b_ub or None, A_eq=a_eq or None, b_eq=b_eq or None,
                bounds=(0, None), method="highs")
    assert r.status == 0
    return -r.fun if objetivo == "max" else r.fun


def test_coincide_con_scipy_en_problemas_aleatorios():
    pytest.importorskip("scipy.optimize")
    rng = random.Random(2026)
    for caso in range(250):
        m, n = rng.randint(2, 5), rng.randint(2, 5)
        oferta = [rng.randint(1, 30) for _ in range(m)]
        demanda = [rng.randint(1, 30) for _ in range(n)]
        if rng.random() < 0.5:  # balancear la mitad de los casos
            dif = sum(oferta) - sum(demanda)
            if dif > 0:
                demanda[0] += dif
            else:
                oferta[0] -= dif
        costos = [[rng.randint(1, 20) for _ in range(n)] for _ in range(m)]
        objetivo = rng.choice(["min", "max"])
        metodo = rng.choice(["esquina_noroeste", "costo_minimo", "vogel"])
        r = transporte.resolver_datos(
            {"oferta": oferta, "demanda": demanda, "costos": costos, "objetivo": objetivo, "metodo_inicial": metodo}
        )
        assert r.exitoso, (caso, oferta, demanda, costos, r.advertencias)
        esperado = _scipy_transporte(oferta, demanda, costos, objetivo)
        assert r.valores["Z"] == pytest.approx(esperado, abs=1e-7), (caso, oferta, demanda, costos, objetivo, metodo)
