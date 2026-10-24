"""Verificación cruzada: nuestro simplex exacto contra SciPy (``linprog``).

SciPy solo se usa aquí (requirements-dev.txt); la aplicación no lo necesita.
"""
import random

import pytest

scipy_opt = pytest.importorskip("scipy.optimize")

from algoritmos import simplex
from algoritmos import grafico
from core.esquemas import ProblemaPL
from core.resultado import Estado


def _problema_aleatorio(rng: random.Random, n_vars: int | None = None) -> dict:
    n = n_vars or rng.randint(2, 4)
    m = rng.randint(2, 5)
    restricciones = []
    for _ in range(m):
        restricciones.append(
            {
                "coeficientes": [rng.randint(-3, 9) for _ in range(n)],
                "signo": rng.choice(["<=", "<=", ">=", "="]),
                "rhs": rng.randint(-3, 30),
            }
        )
    coef = [rng.randint(-4, 9) for _ in range(n)]
    if all(c == 0 for c in coef):
        coef[0] = 1
    return {"objetivo": rng.choice(["max", "min"]), "coef_objetivo": coef, "restricciones": restricciones}


def _scipy(datos: dict, objetivo_cero: bool = False, cota: float | None = None):
    """linprog sobre el problema. ``objetivo_cero`` solo comprueba factibilidad;
    ``cota`` limita cada variable (para comprobar que un problema crece sin límite)."""
    c = [0.0] * len(datos["coef_objetivo"]) if objetivo_cero else [float(v) for v in datos["coef_objetivo"]]
    if datos["objetivo"] == "max":
        c = [-v for v in c]
    a_ub, b_ub, a_eq, b_eq = [], [], [], []
    for r in datos["restricciones"]:
        fila = [float(v) for v in r["coeficientes"]]
        if r["signo"] == "<=":
            a_ub.append(fila)
            b_ub.append(float(r["rhs"]))
        elif r["signo"] == ">=":
            a_ub.append([-v for v in fila])
            b_ub.append(-float(r["rhs"]))
        else:
            a_eq.append(fila)
            b_eq.append(float(r["rhs"]))
    return scipy_opt.linprog(
        c,
        A_ub=a_ub or None,
        b_ub=b_ub or None,
        A_eq=a_eq or None,
        b_eq=b_eq or None,
        bounds=(0, cota),
        method="highs",
    )


def test_simplex_coincide_con_scipy():
    rng = random.Random(20261021)
    conteo = {"optimo": 0, "infactible": 0, "no_acotado": 0}
    for caso in range(400):
        datos = _problema_aleatorio(rng)
        ref = _scipy(datos)
        res = simplex.resolver_datos(datos)
        assert res.estado not in (Estado.ERROR_DATOS, Estado.ERROR_INTERNO, Estado.NO_SOPORTADO), (caso, datos, res.advertencias)

        if res.estado in (Estado.OPTIMO, Estado.MULTIPLES_OPTIMOS):
            assert ref.status == 0, (caso, datos, ref.message)
            z_ref = -ref.fun if datos["objetivo"] == "max" else ref.fun
            assert res.valores["Z"] == pytest.approx(z_ref, abs=1e-7), (caso, datos)
            conteo["optimo"] += 1
        elif res.estado == Estado.INFACTIBLE:
            # Comprobación independiente: ni siquiera existe un punto factible.
            assert _scipy(datos, objetivo_cero=True).status == 2, (caso, datos)
            conteo["infactible"] += 1
        elif res.estado == Estado.NO_ACOTADO:
            # HiGHS a veces informa «infactible» para un problema no acotado, así que se
            # comprueba por separado: (1) existe un punto factible y (2) el objetivo
            # sigue mejorando al ampliar una cota artificial sobre las variables.
            assert _scipy(datos, objetivo_cero=True).status == 0, (caso, datos)
            assert ref.status != 0, (caso, datos)
            z1 = _scipy(datos, cota=1e3)
            z2 = _scipy(datos, cota=1e5)
            assert z1.status == 0 and z2.status == 0, (caso, datos)
            mejora = (z2.fun < z1.fun - 1e-6) if datos["objetivo"] == "max" else (z2.fun < z1.fun - 1e-6)
            assert mejora, (caso, datos, z1.fun, z2.fun)
            conteo["no_acotado"] += 1
    # La muestra aleatoria debe ejercitar los tres desenlaces.
    assert all(v > 0 for v in conteo.values()), conteo


def test_grafico_coincide_con_simplex_en_dos_variables():
    rng = random.Random(7)
    comparados = 0
    for caso in range(300):
        datos = _problema_aleatorio(rng, n_vars=2)
        res_s = simplex.resolver_datos(datos)
        res_g = grafico.resolver_datos(datos)
        assert res_g.estado == res_s.estado, (caso, datos, res_g.estado, res_s.estado)
        if res_s.exitoso:
            assert res_g.valores["Z"] == pytest.approx(res_s.valores["Z"], abs=1e-7), (caso, datos)
            comparados += 1
    assert comparados > 20
