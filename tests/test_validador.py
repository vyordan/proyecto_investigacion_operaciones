from core.esquemas import DatosEOQ, ExtraccionEOQ, ExtraccionPL, ExtraccionRestriccion, ProblemaPL
from core.resultado import Estado
from core.validador import ejecutar, faltantes_eoq, faltantes_pl, validar


def _pl(**cambios):
    datos = {
        "objetivo": "max",
        "coef_objetivo": [1, 2],
        "restricciones": [{"coeficientes": [1, 1], "signo": "<=", "rhs": 4}],
    }
    datos.update(cambios)
    return datos


def test_datos_validos():
    obj, errores = validar(ProblemaPL, _pl())
    assert obj is not None and errores == []
    assert obj.variables == ["x1", "x2"]


def test_normaliza_signos_y_objetivo():
    obj, _ = validar(
        ProblemaPL,
        _pl(objetivo="Maximizar", restricciones=[{"coeficientes": [1, 1], "signo": "≤", "rhs": 4}]),
    )
    assert obj.objetivo == "max" and obj.restricciones[0].signo == "<="


def test_errores_en_espanol():
    casos = {
        "coeficientes distintos": (_pl(restricciones=[{"coeficientes": [1], "signo": "<=", "rhs": 4}]), "tiene 1 coeficientes"),
        "objetivo cero": (_pl(coef_objetivo=[0, 0]), "todos sus coeficientes en cero"),
        "sin restricciones": (_pl(restricciones=[]), "al menos una restricción"),
        "nombre reservado": (_pl(nombres_variables=["s1", "y"]), "reservado"),
        "nombres repetidos": (_pl(nombres_variables=["x", "x"]), "distintos"),
        "signo invalido": (_pl(restricciones=[{"coeficientes": [1, 1], "signo": "?", "rhs": 4}]), "valor no permitido"),
        "no numerico": (_pl(coef_objetivo=["a", 2]), "número válido"),
    }
    for nombre, (datos, fragmento) in casos.items():
        obj, errores = validar(ProblemaPL, datos)
        assert obj is None, nombre
        assert any(fragmento in e.mensaje for e in errores), (nombre, [e.mensaje for e in errores])


def test_falta_dato_obligatorio():
    obj, errores = validar(DatosEOQ, {"demanda": 100})
    assert obj is None
    assert any("Falta el dato" in e.mensaje and "Costo de pedido" in e.mensaje for e in errores)


def test_ejecutar_nunca_propaga_excepciones():
    def rompe(_):
        raise RuntimeError("boom")

    res = ejecutar(ProblemaPL, _pl(), rompe, "x", "X")
    assert res.estado == Estado.ERROR_INTERNO
    assert "boom" in res.advertencias[0].mensaje


def test_faltantes_de_extraccion():
    assert faltantes_eoq(ExtraccionEOQ(demanda=100)) == ["Costo de pedido (S)", "Costo de mantener (H)"]
    assert faltantes_eoq(ExtraccionEOQ(demanda=1, costo_pedido=1, costo_mantener=1)) == []
    assert faltantes_eoq(ExtraccionEOQ(demanda=1, costo_pedido=1, porcentaje_mantener=20)) == ["Costo unitario (C)"]
    assert "Restricciones" in faltantes_pl(ExtraccionPL(objetivo="max", coef_objetivo=[1, 2]))
    faltan = faltantes_pl(
        ExtraccionPL(
            objetivo="max",
            coef_objetivo=[1, 2],
            restricciones=[ExtraccionRestriccion(coeficientes=[1, 1], signo="<=")],
        )
    )
    assert faltan == ["Restricción 1: lado derecho"]
