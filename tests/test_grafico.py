from algoritmos import grafico
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


def _g(coef, restr, objetivo="max"):
    return grafico.resolver_datos(
        {"objetivo": objetivo, "coef_objetivo": coef,
         "restricciones": [{"coeficientes": c, "signo": s, "rhs": b} for c, s, b in restr]}
    )


def test_ejemplo_de_la_rubrica():
    r = grafico.resolver_datos(RUBRICA)
    assert r.estado == Estado.OPTIMO and r.exactos == {"x": "40", "y": "20", "Z": "2200"}
    vertices = next(p for p in r.pasos if p.titulo.startswith("Evaluación")).tabla
    assert [f[1] for f in vertices.filas] == ["(0, 0)", "(0, 40)", "(40, 20)", "(50, 0)"]
    assert vertices.filas_resaltadas == [2]
    fig = r.figuras[0]
    assert fig.tipo == "region_factible" and len(fig.datos["poligono"]) == 4
    assert fig.datos["recta_objetivo"]["valor"] == 2200.0


def test_solo_dos_variables():
    r = _g([1, 1, 1], [([1, 1, 1], "<=", 5)])
    assert r.estado == Estado.NO_SOPORTADO and "simplex" in r.advertencias[0].mensaje


def test_infactible():
    r = _g([1, 1], [([1, 1], "<=", 2), ([1, 1], ">=", 5)])
    assert r.estado == Estado.INFACTIBLE


def test_no_acotado_y_region_no_acotada_con_optimo_finito():
    assert _g([1, 1], [([1, -1], "<=", 2)]).estado == Estado.NO_ACOTADO
    r = _g([2, 1], [([1, 1], ">=", 4)], objetivo="min")
    assert r.exitoso and r.valores["Z"] == 4.0
    assert r.figuras[0].datos["no_acotada"] is True


def test_multiples_optimos():
    r = _g([1, 1], [([1, 1], "<=", 4), ([1, 0], "<=", 3)])
    assert r.estado == Estado.MULTIPLES_OPTIMOS and r.valores["Z"] == 4.0
