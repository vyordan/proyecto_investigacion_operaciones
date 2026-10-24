from fractions import Fraction

from core.formato import a_fraccion, celda, decimal, expresion_latex, expresion_texto, latex, lista_es, texto, var_latex


def test_a_fraccion_evita_error_binario():
    assert a_fraccion(0.1) == Fraction(1, 10)
    assert a_fraccion("1,5") == Fraction(3, 2)
    assert a_fraccion("1/3") == Fraction(1, 3)


def test_texto_y_celda():
    assert texto(Fraction(100, 3)) == "100/3 ≈ 33.33"
    assert texto(Fraction(5, 2)) == "2.5"
    assert texto(7) == "7"
    assert texto(Fraction(-1, 3)) == "-1/3 ≈ -0.33"
    assert celda(Fraction(100, 3)) == "100/3"
    assert celda(Fraction(4, 2)) == "2"
    assert decimal(2.5) == "2.5" and decimal(3.0) == "3"


def test_latex_y_expresiones():
    assert latex(Fraction(1, 3)) == r"\frac{1}{3}"
    assert latex(Fraction(-1, 3)) == r"-\frac{1}{3}"
    assert latex(Fraction(5, 2)) == "2.5"
    assert var_latex("x") == "x" and var_latex("x1") == "x_{1}" and var_latex("mesas") == r"\text{mesas}"
    assert expresion_latex([40, 30], ["x", "y"]) == "40x + 30y"
    assert expresion_latex([1, -1], ["x", "y"]) == "x - y"
    assert expresion_latex([-40, -30], ["x", "y"], signo_inicial=True) == " - 40x - 30y"
    assert expresion_latex([0, 0], ["x", "y"]) == "0"
    assert expresion_texto([2, Fraction(1, 3)], ["x", "y"]) == "2x + (1/3)y"


def test_lista_es():
    assert lista_es(["R1"]) == "R1"
    assert lista_es(["R1", "R2", "R3"]) == "R1, R2 y R3"
