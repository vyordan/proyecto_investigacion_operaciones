import pytest

from practica import generador
from practica.generador import DIFICULTADES, MODULOS, evaluar, generar, resolver
from core.resultado import Estado

COMBINACIONES = [(m, d) for m in MODULOS for d in DIFICULTADES]


def _respuestas_correctas(p):
    sol = resolver(p)
    return {q.id: generador._esperado(p, sol, q.id) for q in p.preguntas}


@pytest.mark.parametrize("modulo, dificultad", COMBINACIONES)
def test_genera_resuelve_y_corrige_con_nota_completa(modulo, dificultad):
    for semilla in range(40):
        p = generar(modulo, dificultad, semilla)
        sol = resolver(p)
        assert sol.exitoso, (modulo, dificultad, semilla, [a.mensaje for a in sol.advertencias])
        fb = evaluar(p, _respuestas_correctas(p))
        assert fb.puntaje == fb.total == len(p.preguntas), (modulo, dificultad, semilla, fb.items)
        assert fb.pistas == []


def test_reproducible_por_semilla():
    a = generar("pl", "medio", 123)
    b = generar("pl", "medio", 123)
    c = generar("pl", "medio", 124)
    assert a.model_dump() == b.model_dump()
    assert a.enunciado != c.enunciado


def test_el_enunciado_no_contiene_la_solucion():
    p = generar("pl", "facil", 5)
    assert "óptim" not in "".join(p.datos.keys())
    assert set(p.datos) <= {"titulo", "objetivo", "coef_objetivo", "restricciones", "nombres_variables",
                            "descripciones_variables"}


def test_sin_responder():
    p = generar("eoq", "facil", 1)
    fb = evaluar(p, {})
    assert fb.puntaje == 0 and all(i.mensaje == "Sin responder." for i in fb.items)


def test_pl_pista_punto_fuera_de_la_region():
    p = generar("pl", "facil", 3)
    nombres = p.datos["nombres_variables"]
    fb = evaluar(p, {**{n: 1000 for n in nombres}, "Z": 1})
    assert any("no se cumple" in t for t in fb.pistas)


def test_pl_pista_factible_pero_no_optimo():
    p = generar("pl", "facil", 3)
    nombres = p.datos["nombres_variables"]
    fb = evaluar(p, {**{n: 0 for n in nombres}, "Z": 0})
    assert any("factible pero no óptima" in t for t in fb.pistas)


def test_pl_pista_z_inconsistente():
    p = generar("pl", "facil", 3)
    sol = resolver(p)
    resp = {n: sol.valores[n] for n in p.datos["nombres_variables"]}
    resp["Z"] = sol.valores["Z"] + 7
    fb = evaluar(p, resp)
    assert any("no coincide con evaluar la función objetivo" in t for t in fb.pistas)


def test_eoq_pistas_de_errores_tipicos():
    p = generar("eoq", "facil", 2)
    sol = resolver(p)
    D, S, H = sol.valores["D_anual"], p.datos["costo_pedido"], sol.valores["H"]
    sin_dos = (D * S / H) ** 0.5
    fb = evaluar(p, {"Q": round(sin_dos, 2)})
    assert any("factor 2" in t for t in fb.pistas)
    fb = evaluar(p, {"N": round(sol.valores["Q*"] / D, 4)})
    assert any("Invertiste" in t for t in fb.pistas)
    L = p.datos["plazo_entrega"]
    fb = evaluar(p, {"ROP": round(D * L, 2)})
    assert any("diaria" in t for t in fb.pistas)


def test_eoq_medio_demanda_sin_convertir():
    p = generar("eoq", "medio", 4)
    d = p.datos
    sol = resolver(p)
    H = sol.valores["H"]
    q = (2 * d["demanda"] * d["costo_pedido"] / H) ** 0.5
    fb = evaluar(p, {"Q": round(q, 2)})
    assert any("anual" in t for t in fb.pistas)


def test_transporte_pistas():
    p = generar("transporte", "facil", 9)
    opt = resolver(p).valores["Z"]
    fb = evaluar(p, {"Z": opt + 10})
    assert any("mayor que el óptimo" in t for t in fb.pistas)
    fb = evaluar(p, {"Z": opt - 10})
    assert any("menor que el óptimo" in t for t in fb.pistas)


def test_asignacion_pista_columnas():
    for semilla in range(60):
        p = generar("asignacion", "facil", semilla)
        costos = p.datos["costos"]
        n = len(costos)
        filas = sum(min(f) for f in costos)
        cols = sum(min(costos[i][j] for i in range(n)) for j in range(n))
        if filas != cols:
            fb = evaluar(p, {"filas": cols})
            assert any("columnas" in t for t in fb.pistas)
            return
    pytest.fail("no se encontró una semilla con sumas distintas")


def test_argumentos_invalidos():
    with pytest.raises(ValueError):
        generar("inexistente")
    with pytest.raises(ValueError):
        generar("pl", "imposible")


def test_tolerancias():
    assert generador._cerca(2200, 2200)
    assert not generador._cerca(2201, 2200)  # enteros: exactitud
    assert generador._cerca(89.4, 89.4427)
    assert not generador._cerca(90, 89.4427)
