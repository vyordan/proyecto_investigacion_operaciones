"""Método simplex con tablas y aritmética exacta (``Fraction``).

Soporta maximizar/minimizar y restricciones <=, >= e = (método de dos fases).
Detecta y explica: problema infactible, no acotado, óptimos alternativos y
degeneración. Devuelve un ``Resultado`` con el procedimiento completo.

Convención de la fila Z: representa «Z - c·x = 0», es decir, guarda -c_j.
Para maximizar, la tabla es óptima cuando todos los coeficientes de la fila Z
son >= 0. Minimizar Z se resuelve como maximizar Z' = -Z.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from algoritmos import modelacion as mod
from core.esquemas import ProblemaPL
from core.formato import a_fraccion, celda, expresion_latex, latex, texto, var_latex
from core.resultado import Estado, Paso, Resultado, Tabla
from core.validador import ejecutar

MAX_ITERACIONES = 100
UMBRAL_BLAND = 6  # pivotes degenerados consecutivos antes de cambiar a la regla de Bland


# --------------------------------------------------------------------------- #
# Estructura interna
# --------------------------------------------------------------------------- #
@dataclass
class _Tabla:
    nombres: list[str]
    A: list[list[Fraction]]
    b: list[Fraction]
    z: list[Fraction]
    zval: Fraction
    base: list[int]
    etiqueta_z: str = "Z"

    def copia(self) -> "_Tabla":
        return _Tabla(
            list(self.nombres),
            [list(f) for f in self.A],
            list(self.b),
            list(self.z),
            self.zval,
            list(self.base),
            self.etiqueta_z,
        )


def _pivotear(t: _Tabla, fila: int, col: int) -> None:
    p = t.A[fila][col]
    t.A[fila] = [v / p for v in t.A[fila]]
    t.b[fila] = t.b[fila] / p
    for i in range(len(t.b)):
        if i != fila:
            f = t.A[i][col]
            if f != 0:
                t.A[i] = [a - f * r for a, r in zip(t.A[i], t.A[fila])]
                t.b[i] = t.b[i] - f * t.b[fila]
    f = t.z[col]
    if f != 0:
        t.z = [a - f * r for a, r in zip(t.z, t.A[fila])]
        t.zval = t.zval - f * t.b[fila]
    t.base[fila] = col


def _normalizar_z(t: _Tabla, c: list[Fraction]) -> None:
    """Fija la fila Z para maximizar c·x y la deja expresada en las variables no básicas."""
    t.z = [-v for v in c]
    t.zval = Fraction(0)
    for i, k in enumerate(t.base):
        f = t.z[k]
        if f != 0:
            t.z = [a - f * r for a, r in zip(t.z, t.A[i])]
            t.zval = t.zval - f * t.b[i]


def _valores(t: _Tabla) -> list[Fraction]:
    vals = [Fraction(0)] * len(t.nombres)
    for i, k in enumerate(t.base):
        vals[k] = t.b[i]
    return vals


def _a_tabla(t: _Tabla, titulo: str = "", pivote: tuple[int, int] | None = None,
             razones: dict[int, Fraction] | None = None, notas: str = "") -> Tabla:
    columnas = ["Base"] + list(t.nombres) + ["LD"]
    if razones is not None:
        columnas.append("Razón")
    filas = []
    for i in range(len(t.b)):
        fila = [t.nombres[t.base[i]]] + [celda(v) for v in t.A[i]] + [celda(t.b[i])]
        if razones is not None:
            fila.append(celda(razones[i]) if i in razones else "—")
        filas.append(fila)
    fz = [t.etiqueta_z] + [celda(v) for v in t.z] + [celda(t.zval)]
    if razones is not None:
        fz.append("")
    filas.append(fz)
    return Tabla(titulo=titulo, columnas=columnas, filas=filas, pivote=pivote, notas=notas)


# --------------------------------------------------------------------------- #
# Forma estándar
# --------------------------------------------------------------------------- #
def _forma_estandar(p: ProblemaPL) -> tuple[_Tabla, list[Fraction], int, list[str]]:
    """Construye la tabla inicial. Devuelve (tabla, c_max, n_real, notas).

    ``n_real`` es la cantidad de columnas que no son artificiales; las
    artificiales ocupan siempre las últimas columnas.
    """
    n = p.n
    c = [a_fraccion(v) for v in p.coef_objetivo]
    if p.objetivo == "min":
        c = [-v for v in c]  # maximizar Z' = -Z

    filas: list[tuple[list[Fraction], str, Fraction, int]] = []
    notas: list[str] = []
    invertir = {"<=": ">=", ">=": "<=", "=": "="}
    for i, r in enumerate(p.restricciones):
        coefs = [a_fraccion(v) for v in r.coeficientes]
        rhs = a_fraccion(r.rhs)
        signo = r.signo
        if rhs < 0:
            coefs = [-v for v in coefs]
            rhs = -rhs
            signo = invertir[signo]
            notas.append(
                f"La restricción {p.etiqueta_restriccion(i)} tenía lado derecho negativo: se multiplicó por −1 "
                "(el sentido de la desigualdad se invierte)."
            )
        filas.append((coefs, signo, rhs, i + 1))

    extra = []  # (nombre, fila, coeficiente) de holguras y excesos
    artificiales = []  # (nombre, fila)
    for k, (_, signo, _, idx) in enumerate(filas):
        if signo == "<=":
            extra.append((f"s{idx}", k, Fraction(1)))
        elif signo == ">=":
            extra.append((f"e{idx}", k, Fraction(-1)))
    for k, (_, signo, _, idx) in enumerate(filas):
        if signo in (">=", "="):
            artificiales.append((f"a{idx}", k))

    n_real = n + len(extra)
    nombres = p.variables + [e[0] for e in extra] + [a[0] for a in artificiales]
    N = len(nombres)
    A = [[Fraction(0)] * N for _ in filas]
    base = [0] * len(filas)
    for k, (coefs, _, _, _) in enumerate(filas):
        A[k][:n] = coefs
    for pos, (_, k, coef) in enumerate(extra):
        A[k][n + pos] = coef
        if coef == 1:
            base[k] = n + pos
    for pos, (_, k) in enumerate(artificiales):
        A[k][n_real + pos] = Fraction(1)
        base[k] = n_real + pos
    b = [f[2] for f in filas]

    t = _Tabla(nombres, A, b, [Fraction(0)] * N, Fraction(0), base)
    return t, c + [Fraction(0)] * len(extra), n_real, notas


def _paso_forma_estandar(p: ProblemaPL, t: _Tabla, c_max: list[Fraction], n_real: int, notas: list[str]) -> Paso:
    n_art = len(t.nombres) - n_real
    partes = ["Cada restricción se convierte en una ecuación agregando variables auxiliares:"]
    tipos = {nombre[0] for nombre in t.nombres[p.n:]}
    if "s" in tipos:
        partes.append("- Restricción ≤: se **suma** una variable de holgura `s`.")
    if "e" in tipos:
        partes.append("- Restricción ≥: se **resta** una variable de exceso `e` y se suma una artificial `a`.")
    if "a" in tipos and "e" not in tipos:
        partes.append("- Restricción =: se suma una variable artificial `a`.")
    elif "a" in tipos:
        partes.append("- Restricción =: se suma una variable artificial `a`.")
    if p.objetivo == "min":
        partes.append("Minimizar Z equivale a **maximizar Z' = −Z**; al final se invierte el signo.")
    if n_art:
        partes.append(
            "Como hay variables artificiales se usa el **método de dos fases**: "
            "la fase 1 busca una solución factible y la fase 2 optimiza."
        )
    partes.extend(f"- {nota}" for nota in notas)

    lineas = []
    for i in range(len(t.b)):
        izq = expresion_latex(t.A[i], t.nombres)
        lineas.append(f"{izq} = {latex(t.b[i])}")
    etiqueta = "Z" if p.objetivo == "max" else "Z'"
    fila_obj = expresion_latex([-v for v in c_max], t.nombres[: len(c_max)], signo_inicial=True)
    lineas.append(f"{etiqueta}{fila_obj} = 0")
    return Paso(titulo="Forma estándar", explicacion="\n".join(partes), lineas=lineas)


# --------------------------------------------------------------------------- #
# Iteraciones
# --------------------------------------------------------------------------- #
def _optimizar(t: _Tabla, res: Resultado, prefijo: str) -> tuple[str, int | None]:
    """Itera hasta el óptimo. Devuelve ('optimo'|'no_acotado'|'limite', columna)."""
    degenerados_seguidos = 0
    usar_bland = False
    for it in range(1, MAX_ITERACIONES + 1):
        candidatos = [j for j, v in enumerate(t.z) if v < 0]
        if not candidatos:
            return "optimo", None
        if usar_bland:
            col = min(candidatos)
            regla = (
                f"Entra {t.nombres[col]} (regla de Bland: la primera variable con coeficiente negativo "
                f"en la fila {t.etiqueta_z}; evita ciclos)."
            )
        else:
            col = min(candidatos, key=lambda j: (t.z[j], j))
            regla = (
                f"Entra {t.nombres[col]}: tiene el coeficiente más negativo de la fila "
                f"{t.etiqueta_z} ({texto(t.z[col])})."
            )

        razones = [(t.b[i] / t.A[i][col], i) for i in range(len(t.b)) if t.A[i][col] > 0]
        if not razones:
            return "no_acotado", col
        minr = min(r for r, _ in razones)
        empatadas = [i for r, i in razones if r == minr]
        fila = min(empatadas, key=lambda i: t.base[i])
        sale = t.nombres[t.base[fila]]
        pivote = t.A[fila][col]

        detalle = "; ".join(
            f"{t.nombres[t.base[i]]}: {texto(t.b[i])} ÷ {texto(t.A[i][col])} = {texto(r)}" for r, i in razones
        )
        explicacion = (
            f"{regla}\n\nRazones mínimas (LD ÷ columna de {t.nombres[col]}): {detalle}.\n\n"
            f"La menor razón es {texto(minr)}, por eso sale {sale}. Elemento pivote: {texto(pivote)}."
        )
        if len(empatadas) > 1:
            explicacion += "\n\n⚠ Hay empate en la razón mínima: la siguiente solución será degenerada."
        titulo = f"{prefijo}Iteración {it}" + (" (tabla inicial)" if it == 1 else "")
        res.pasos.append(
            Paso(
                titulo=titulo,
                explicacion=explicacion,
                tabla=_a_tabla(t, pivote=(fila, col + 1), razones={i: r for r, i in razones}),
            )
        )
        _pivotear(t, fila, col)
        degenerados_seguidos = degenerados_seguidos + 1 if minr == 0 else 0
        if degenerados_seguidos >= UMBRAL_BLAND:
            usar_bland = True
    return "limite", None


def _expulsar_artificiales(t: _Tabla, n_real: int, res: Resultado) -> None:
    """Saca de la base las artificiales que quedaron en nivel cero (o elimina filas redundantes)."""
    eliminar = []
    for i in range(len(t.base)):
        if t.base[i] >= n_real:
            col = next((j for j in range(n_real) if t.A[i][j] != 0), None)
            if col is None:
                eliminar.append(i)
            else:
                _pivotear(t, i, col)
    for i in sorted(eliminar, reverse=True):
        del t.A[i], t.b[i], t.base[i]
    if eliminar:
        res.advertir(
            f"Se eliminó {len(eliminar)} restricción(es) redundante(s) detectada(s) al terminar la fase 1.",
            nivel="info",
        )


def _quitar_artificiales(t: _Tabla, n_real: int) -> _Tabla:
    return _Tabla(
        t.nombres[:n_real],
        [fila[:n_real] for fila in t.A],
        list(t.b),
        [Fraction(0)] * n_real,
        Fraction(0),
        list(t.base),
    )


# --------------------------------------------------------------------------- #
# Utilidades de presentación
# --------------------------------------------------------------------------- #
def _par(x: Fraction) -> str:
    return f"({latex(x)})" if x < 0 else latex(x)


def _vector(items: list[str]) -> str:
    return "(" + ",\\ ".join(items) + ")"


def _sustitucion_objetivo(p: ProblemaPL, x: list[Fraction]) -> str:
    terminos = [
        f"{_par(a_fraccion(c))} \\cdot {_par(xi)}" for c, xi in zip(p.coef_objetivo, x) if a_fraccion(c) != 0
    ]
    return "Z = " + " + ".join(terminos)


def _terminar_limite(res: Resultado) -> Resultado:
    res.estado = Estado.NO_SOPORTADO
    res.resumen = "No se llegó al óptimo dentro del límite de iteraciones."
    res.advertir(
        f"Se alcanzó el límite de {MAX_ITERACIONES} iteraciones sin llegar al óptimo; el problema es "
        "demasiado grande o presenta ciclos.",
        nivel="error",
    )
    return res


# --------------------------------------------------------------------------- #
# Resolución
# --------------------------------------------------------------------------- #
def resolver(p: ProblemaPL) -> Resultado:
    res = Resultado(modulo="simplex", estado=Estado.OPTIMO, titulo="Método simplex")
    n = p.n
    nombres = p.variables
    es_max = p.objetivo == "max"
    etiqueta_z = "Z" if es_max else "Z'"

    res.pasos.append(mod.paso_modelo(p))
    t, c_max, n_real, notas = _forma_estandar(p)
    n_art = len(t.nombres) - n_real
    res.pasos.append(_paso_forma_estandar(p, t, c_max, n_real, notas))
    for nota in notas:
        res.advertir(nota, nivel="info")

    # ---- Fase 1 (solo si hay artificiales) -------------------------------------
    if n_art:
        t.etiqueta_z = "W"
        _normalizar_z(t, [Fraction(0)] * n_real + [Fraction(-1)] * n_art)
        art_nombres = t.nombres[n_real:]
        res.pasos.append(
            Paso(
                titulo="Fase 1: buscar una solución factible",
                explicacion=(
                    "Se minimiza la suma de las variables artificiales W (equivale a maximizar −W). "
                    "Si el mínimo es 0, el problema tiene solución factible y se pasa a la fase 2; "
                    "si es mayor que 0, las restricciones son incompatibles."
                ),
                lineas=["W = " + " + ".join(var_latex(a) for a in art_nombres)],
            )
        )
        estado1, _ = _optimizar(t, res, "Fase 1 · ")
        if estado1 == "limite":
            return _terminar_limite(res)
        res.pasos.append(
            Paso(
                titulo="Fase 1 · Tabla final",
                explicacion=f"Fin de la fase 1: el valor de W es {texto(-t.zval)}.",
                tabla=_a_tabla(t),
            )
        )
        if t.zval < 0:
            res.estado = Estado.INFACTIBLE
            res.resumen = "El problema es infactible: no existe ninguna solución que cumpla todas las restricciones."
            res.pasos.append(
                Paso(
                    titulo="Problema infactible",
                    explicacion=(
                        f"Al terminar la fase 1 todavía queda W = {texto(-t.zval)} > 0: las variables artificiales "
                        "no pueden eliminarse. Las restricciones son incompatibles entre sí, así que no existe "
                        "un punto que las cumpla todas a la vez."
                    ),
                )
            )
            return res
        _expulsar_artificiales(t, n_real, res)
        t = _quitar_artificiales(t, n_real)
        t.etiqueta_z = etiqueta_z
        _normalizar_z(t, c_max)
        res.pasos.append(
            Paso(
                titulo="Fase 2: optimizar la función objetivo",
                explicacion=(
                    "Como W = 0 existe una solución factible. Se eliminan las variables artificiales y se "
                    "restituye la función objetivo original, expresada en función de las variables no básicas."
                ),
            )
        )
        prefijo = "Fase 2 · "
    else:
        t.etiqueta_z = etiqueta_z
        _normalizar_z(t, c_max)
        prefijo = ""

    # ---- Fase de optimización ------------------------------------------------------
    estado, col_libre = _optimizar(t, res, prefijo)
    if estado == "limite":
        return _terminar_limite(res)
    if estado == "no_acotado":
        nombre = t.nombres[col_libre]
        res.estado = Estado.NO_ACOTADO
        res.resumen = "El problema no tiene solución óptima finita (es no acotado)."
        mejora = "crecer" if es_max else "decrecer"
        res.pasos.append(
            Paso(
                titulo="Problema no acotado",
                explicacion=(
                    f"La variable {nombre} puede aumentar sin límite: todos los elementos de su columna son ≤ 0, "
                    f"así que ninguna restricción la frena. Como mejora la función objetivo, Z puede {mejora} "
                    "indefinidamente y no existe un óptimo finito."
                ),
                tabla=_a_tabla(t),
            )
        )
        return res

    res.pasos.append(
        Paso(
            titulo=f"{prefijo}Tabla final (óptima)",
            explicacion=(
                f"Todos los coeficientes de la fila {t.etiqueta_z} son ≥ 0: no se puede mejorar más, "
                "se alcanzó el óptimo."
            ),
            tabla=_a_tabla(t),
        )
    )

    vals = _valores(t)
    x = vals[:n]
    z = mod.valor_objetivo(p, x)
    esperado = t.zval if es_max else -t.zval
    if z != esperado:
        raise RuntimeError("Inconsistencia interna: el valor de Z de la tabla no coincide con Z evaluado.")

    basicas = [t.nombres[k] for k in t.base]
    no_basicas = [nom for j, nom in enumerate(t.nombres) if j not in t.base]
    res.pasos.append(
        Paso(
            titulo="Solución óptima",
            explicacion=(
                f"Variables básicas: {', '.join(basicas)}. Variables no básicas (valen 0): "
                f"{', '.join(no_basicas) if no_basicas else 'ninguna'}."
                + (" Se invierte el signo porque se minimizó." if not es_max else "")
            ),
            formula="Z = " + expresion_latex(p.coef_objetivo, nombres),
            sustitucion=_sustitucion_objetivo(p, x),
            resultado=f"Z = {latex(z)}",
            lineas=[f"{var_latex(nom)} = {latex(v)}" for nom, v in zip(nombres, x)],
        )
    )

    if any(t.b[i] == 0 for i in range(len(t.b))):
        res.advertir(
            "La solución óptima es degenerada: alguna variable básica vale 0 "
            "(hay más restricciones activas que las necesarias en ese vértice).",
            nivel="info",
        )

    # ---- Óptimos alternativos --------------------------------------------------------------
    alterno = None
    hay_rayo = False
    for j in [j for j in range(len(t.nombres)) if j not in t.base and t.z[j] == 0]:
        razones = [(t.b[i] / t.A[i][j], i) for i in range(len(t.b)) if t.A[i][j] > 0]
        if not razones:
            hay_rayo = True
            continue
        minr = min(r for r, _ in razones)
        fila = min((i for r, i in razones if r == minr), key=lambda i: t.base[i])
        t2 = t.copia()
        _pivotear(t2, fila, j)
        x2 = _valores(t2)[:n]
        if x2 != x:
            alterno = (t2, fila, j, razones, x2)
            break

    if alterno is not None:
        t2, fila, j, razones, x2 = alterno
        res.estado = Estado.MULTIPLES_OPTIMOS
        res.pasos.append(
            Paso(
                titulo="Óptimos alternativos",
                explicacion=(
                    f"En la tabla óptima la variable no básica {t.nombres[j]} tiene coeficiente 0 en la fila "
                    f"{t.etiqueta_z}: hacerla entrar a la base no cambia Z y produce otro vértice óptimo. "
                    "Por eso existen **infinitas soluciones óptimas**: todas las combinaciones convexas de los "
                    "vértices óptimos."
                ),
                tabla=_a_tabla(t, pivote=(fila, j + 1), razones={i: r for r, i in razones}),
            )
        )
        res.pasos.append(
            Paso(
                titulo="Segundo vértice óptimo",
                explicacion=f"Tras pivotear, el otro vértice óptimo es {', '.join(f'{n_} = {texto(v)}' for n_, v in zip(nombres, x2))} (mismo Z).",
                formula=_vector([var_latex(v) for v in nombres])
                + r" = \lambda\," + _vector([latex(v) for v in x])
                + r" + (1-\lambda)\," + _vector([latex(v) for v in x2])
                + r",\quad 0 \le \lambda \le 1",
                tabla=_a_tabla(t2),
            )
        )
        for nom, v in zip(nombres, x2):
            res.fijar(f"alt_{nom}", v)
        res.advertir("El problema tiene múltiples soluciones óptimas (todas con el mismo valor de Z).", nivel="info")
    elif hay_rayo:
        res.estado = Estado.MULTIPLES_OPTIMOS
        res.advertir(
            "Hay infinitas soluciones óptimas: una variable no básica con coeficiente 0 en la fila Z puede "
            "crecer sin límite sin cambiar Z.",
            nivel="info",
        )

    # ---- Verificación e interpretación ----------------------------------------------------------
    res.pasos.append(
        Paso(
            titulo="Verificación en las restricciones",
            explicacion="Se evalúa la solución en cada restricción para comprobar que se cumplen todas.",
            tabla=mod.tabla_restricciones(p, x),
        )
    )

    for nom, v in zip(nombres, x):
        res.fijar(nom, v)
    res.fijar("Z", z)
    tipo = "máximo" if es_max else "mínimo"
    sol = ", ".join(f"{nom} = {texto(v)}" for nom, v in zip(nombres, x))
    res.resumen = f"Solución óptima: {sol}; Z = {texto(z)} ({tipo})."
    if res.estado == Estado.MULTIPLES_OPTIMOS:
        res.resumen += " Existen infinitas soluciones óptimas."
    res.interpretacion = mod.interpretar(p, x, z)
    return res


def resolver_datos(datos) -> Resultado:
    """Valida y resuelve; nunca lanza excepciones (ver ``core.validador.ejecutar``)."""
    return ejecutar(ProblemaPL, datos, resolver, "simplex", "Método simplex")
