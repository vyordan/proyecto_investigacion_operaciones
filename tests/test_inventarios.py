import math

import pytest

from algoritmos import inventarios
from core.resultado import Estado

BASE = {"demanda": 1000, "costo_pedido": 10, "costo_mantener": 2.5, "plazo_entrega": 7}


def test_eoq_y_punto_de_reorden():
    r = inventarios.resolver_datos(BASE)
    assert r.estado == Estado.OPTIMO
    assert r.valores["Q*"] == pytest.approx(math.sqrt(8000))
    assert r.valores["N"] == pytest.approx(1000 / math.sqrt(8000))
    assert r.valores["CT"] == pytest.approx(math.sqrt(2 * 1000 * 10 * 2.5))
    assert r.valores["ROP"] == pytest.approx(1000 / 365 * 7)
    assert r.valores["Q_practico"] == 89.0
    assert len(r.figuras) == 2


def test_costo_de_mantener_como_porcentaje_y_costo_total_con_compra():
    r = inventarios.resolver_datos(
        {"demanda": 1000, "costo_pedido": 10, "modo_mantener": "porcentaje",
         "porcentaje_mantener": 20, "costo_unitario": 50}
    )
    assert r.valores["H"] == 10.0
    assert r.valores["Q*"] == pytest.approx(math.sqrt(2 * 1000 * 10 / 10))
    assert r.valores["CT"] == pytest.approx(math.sqrt(2 * 1000 * 10 * 10) + 1000 * 50)


def test_conversion_de_unidades():
    r = inventarios.resolver_datos(
        {"demanda": 100, "periodo_demanda": "mensual", "costo_pedido": 10, "costo_mantener": 2,
         "plazo_entrega": 2, "unidad_plazo": "semanas", "dias_laborales_anio": 365}
    )
    assert r.valores["D_anual"] == 1200.0
    assert r.valores["ROP"] == pytest.approx(1200 * 2 / 52)
    d = inventarios.resolver_datos(
        {"demanda": 5, "periodo_demanda": "diario", "costo_pedido": 10, "costo_mantener": 2, "dias_laborales_anio": 250}
    )
    assert d.valores["D_anual"] == 1250.0


def test_stock_de_seguridad():
    r = inventarios.resolver_datos({**BASE, "stock_seguridad": 15})
    assert r.valores["ROP"] == pytest.approx(1000 / 365 * 7 + 15)


def test_sin_plazo_avisa_y_no_calcula_rop():
    r = inventarios.resolver_datos({"demanda": 1000, "costo_pedido": 10, "costo_mantener": 2.5})
    assert r.exitoso and "ROP" not in r.valores
    assert any("plazo de entrega" in a.mensaje for a in r.advertencias)


def test_rop_mayor_que_q_advierte():
    r = inventarios.resolver_datos({**BASE, "plazo_entrega": 200})
    assert any("posición de inventario" in a.mensaje for a in r.advertencias)


def test_datos_invalidos():
    for datos in ({"demanda": -5, "costo_pedido": 10, "costo_mantener": 1},
                  {"demanda": 5, "costo_pedido": 0, "costo_mantener": 1},
                  {"demanda": 5, "costo_pedido": 1},
                  {"demanda": "mucha", "costo_pedido": 1, "costo_mantener": 1},
                  {"demanda": 5, "costo_pedido": 1, "modo_mantener": "porcentaje", "porcentaje_mantener": 20}):
        r = inventarios.resolver_datos(datos)
        assert r.estado == Estado.ERROR_DATOS and r.advertencias, datos
