import random

import pytest

from algoritmos import asignacion
from core.resultado import Estado

COSTOS = [[9, 2, 7, 8], [6, 4, 3, 7], [5, 8, 1, 8], [7, 6, 9, 4]]  # óptimo conocido: 13


def test_cuadrada_minimizar():
    r = asignacion.resolver_datos({"costos": COSTOS})
    assert r.exitoso and r.valores["Z"] == 13.0
    assert sum(1 for k in r.valores if k.startswith("x")) == 4
    titulos = [p.titulo for p in r.pasos]
    assert "Reducción por filas" in titulos and "Reducción por columnas" in titulos


def test_maximizar():
    r = asignacion.resolver_datos({"costos": [[3, 1], [1, 3]], "objetivo": "max"})
    assert r.valores["Z"] == 6.0


def test_no_cuadrada_agrega_ficticias():
    r = asignacion.resolver_datos({"costos": [[4, 2, 8], [3, 5, 6]]})
    assert r.exitoso and r.valores["Z"] == 5.0  # 2 + 3
    assert any(p.titulo == "Matriz cuadrada" for p in r.pasos)
    assert "sin asignación" in r.interpretacion


def test_multiples_optimos():
    r = asignacion.resolver_datos({"costos": [[1, 1], [1, 1]]})
    assert r.estado == Estado.MULTIPLES_OPTIMOS and r.valores["Z"] == 2.0


def test_requiere_iteraciones_con_cobertura():
    # Caso que no se resuelve solo con las reducciones iniciales.
    r = asignacion.resolver_datos({"costos": [[1, 2, 3], [2, 4, 6], [3, 6, 9]]})
    assert r.exitoso and r.valores["Z"] == 10.0
    assert any("cubrir los ceros" in p.titulo for p in r.pasos)


def test_datos_invalidos():
    for datos in ({"costos": []}, {"costos": [[1, 2], [3]]}, {"costos": [[1, "a"]]},
                  {"costos": [[1]], "nombres_filas": ["a", "b"]}):
        r = asignacion.resolver_datos(datos)
        assert r.estado == Estado.ERROR_DATOS and r.advertencias, datos


def test_coincide_con_scipy():
    scipy_opt = pytest.importorskip("scipy.optimize")
    rng = random.Random(11)
    for caso in range(400):
        m, n = rng.randint(1, 6), rng.randint(1, 6)
        costos = [[rng.randint(-5, 30) for _ in range(n)] for _ in range(m)]
        objetivo = rng.choice(["min", "max"])
        r = asignacion.resolver_datos({"costos": costos, "objetivo": objetivo})
        assert r.exitoso, (caso, costos, r.advertencias)
        filas, cols = scipy_opt.linear_sum_assignment(costos, maximize=(objetivo == "max"))
        esperado = sum(costos[i][j] for i, j in zip(filas, cols))
        assert r.valores["Z"] == pytest.approx(esperado, abs=1e-9), (caso, costos, objetivo)
