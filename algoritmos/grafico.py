"""Método gráfico para problemas de programación lineal con 2 variables.

Procedimiento (todo con ``Fraction``):
1. Se escriben las rectas frontera de las restricciones y de x, y >= 0.
2. Los vértices candidatos son las intersecciones de pares de rectas; se
   conservan los que cumplen todas las restricciones.
3. Se evalúa Z en cada vértice y se elige el mejor.
4. Se detectan región vacía, región no acotada, objetivo no acotado y óptimos
   alternativos (arista o semirrecta óptima).

No dibuja: devuelve una ``Figura`` declarativa que la interfaz convierte en
gráfico con matplotlib.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations

from algoritmos import modelacion as mod
from core.esquemas import ProblemaPL
from core.formato import SIGNO_LATEX, SIGNO_TEXTO, a_fraccion, expresion_latex, expresion_texto, latex, texto
from core.resultado import Estado, Figura, Paso, Resultado, Tabla
from core.validador import ejecutar

Punto = tuple[Fraction, Fraction]
# Recta: (a, b, signo, rhs, etiqueta) que representa a·x + b·y (signo) rhs
Recta = tuple[Fraction, Fraction, str, Fraction, str]


def _cumple(a: Fraction, b: Fraction, signo: str, rhs: Fraction, p: Punto) -> bool:
    v = a * p[0] + b * p[1]
    if signo == "<=":
        return v <= rhs
    if signo == ">=":
        return v >= rhs
    return v == rhs


def _interseccion(r1: Recta, r2: Recta) -> Punto | None:
    a1, b1, _, c1, _ = r1
    a2, b2, _, c2, _ = r2
    det = a1 * b2 - a2 * b1
    if det == 0:
        return None
    return ((c1 * b2 - c2 * b1) / det, (a1 * c2 - a2 * c1) / det)


def _recortar(poligono: list[tuple[float, float]], a: float, b: float, signo: str, rhs: float):
    """Recorta un polígono con el semiplano de una restricción (Sutherland–Hodgman)."""

    def valor(p):
        return a * p[0] + b * p[1] - rhs

    def dentro(p):
        v = valor(p)
        return v <= 1e-9 if signo == "<=" else v >= -1e-9

    def cruce(p, q):
        vp, vq = valor(p), valor(q)
        t = vp / (vp - vq)
        return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

    salida = []
    for i, actual in enumerate(poligono):
        previo = poligono[i - 1]
        if dentro(actual):
            if not dentro(previo):
                salida.append(cruce(previo, actual))
            salida.append(actual)
        elif dentro(previo):
            salida.append(cruce(previo, actual))
    return salida


def _letra(i: int) -> str:
    return chr(ord("A") + i) if i < 26 else f"V{i + 1}"


def resolver(p: ProblemaPL) -> Resultado:
    res = Resultado(modulo="grafico", estado=Estado.OPTIMO, titulo="Método gráfico")

    if p.n != 2:
        res.estado = Estado.NO_SOPORTADO
        res.resumen = "El método gráfico solo se puede aplicar a problemas con 2 variables."
        res.advertir(
            f"El problema tiene {p.n} variables. El método gráfico solo aplica con 2; "
            "usa el método simplex para este problema.",
            nivel="error",
        )
        return res

    nx, ny = p.variables
    es_max = p.objetivo == "max"
    c = mod.coeficientes_objetivo(p)
    res.pasos.append(mod.paso_modelo(p))

    # ---- Rectas frontera --------------------------------------------------------
    restr: list[Recta] = []
    for i, r in enumerate(p.restricciones):
        a, b = (a_fraccion(v) for v in r.coeficientes)
        restr.append((a, b, r.signo, a_fraccion(r.rhs), p.etiqueta_restriccion(i)))

    # Restricciones triviales (0·x + 0·y ? rhs)
    utiles: list[Recta] = []
    for a, b, signo, rhs, etq in restr:
        if a == 0 and b == 0:
            if not _cumple(a, b, signo, rhs, (Fraction(0), Fraction(0))):
                res.estado = Estado.INFACTIBLE
                res.resumen = f"El problema es infactible: la restricción {etq} no se puede cumplir."
                res.pasos.append(
                    Paso(
                        titulo="Problema infactible",
                        explicacion=f"La restricción {etq} tiene coeficientes 0 y no se cumple: región factible vacía.",
                    )
                )
                return res
            res.advertir(f"La restricción {etq} tiene coeficientes 0 y se cumple siempre; se ignora.", nivel="info")
        else:
            utiles.append((a, b, signo, rhs, etq))

    ejes: list[Recta] = [
        (Fraction(1), Fraction(0), ">=", Fraction(0), f"{nx} ≥ 0"),
        (Fraction(0), Fraction(1), ">=", Fraction(0), f"{ny} ≥ 0"),
    ]
    todas = utiles + ejes

    explic = []
    for a, b, signo, rhs, etq in utiles:
        partes = []
        if a != 0:
            partes.append(f"corta el eje {nx} en ({texto(rhs / a)}, 0)" if rhs / a >= 0 else f"corta el eje {nx} fuera del primer cuadrante")
        else:
            partes.append(f"es paralela al eje {nx}")
        if b != 0:
            partes.append(f"el eje {ny} en (0, {texto(rhs / b)})" if rhs / b >= 0 else f"el eje {ny} fuera del primer cuadrante")
        else:
            partes.append(f"es paralela al eje {ny}")
        explic.append(f"- **{etq}**: {expresion_texto([a, b], [nx, ny])} = {texto(rhs)}; " + " y ".join(partes) + ".")
    res.pasos.append(
        Paso(
            titulo="Rectas frontera",
            explicacion=(
                "Cada desigualdad se convierte en igualdad para trazar su recta frontera; la región factible "
                "queda del lado que cumple la desigualdad, dentro del primer cuadrante.\n" + "\n".join(explic)
            ),
            lineas=[f"{expresion_latex([a, b], [nx, ny])} = {latex(rhs)}" for a, b, _, rhs, _ in utiles],
        )
    )

    # ---- Vértices factibles ----------------------------------------------------------
    vertices: dict[Punto, list[str]] = {}
    for r1, r2 in combinations(todas, 2):
        pt = _interseccion(r1, r2)
        if pt is None or pt in vertices:
            continue
        if all(_cumple(a, b, s, rhs, pt) for a, b, s, rhs, _ in todas):
            vertices[pt] = [etq for a, b, _, rhs, etq in todas if a * pt[0] + b * pt[1] == rhs]

    if not vertices:
        res.estado = Estado.INFACTIBLE
        res.resumen = "El problema es infactible: no existe una región factible."
        res.pasos.append(
            Paso(
                titulo="Problema infactible",
                explicacion=(
                    "Ningún punto cumple todas las restricciones a la vez: la región factible es vacía. "
                    "Revisa los signos y los valores de las restricciones."
                ),
            )
        )
        res.figuras.append(_figura(p, utiles, {}, [], None, False, c))
        return res

    ordenados = sorted(vertices, key=lambda pt: (pt[0], pt[1]))
    letras = {pt: _letra(i) for i, pt in enumerate(ordenados)}
    res.pasos.append(
        Paso(
            titulo="Vértices de la región factible",
            explicacion=(
                "Los vértices son las intersecciones de pares de rectas frontera (incluidos los ejes) que "
                "cumplen **todas** las restricciones. Las demás intersecciones quedan fuera de la región."
            ),
            tabla=Tabla(
                columnas=["Vértice", nx, ny, "Rectas que se cruzan"],
                filas=[[letras[pt], texto(pt[0]), texto(pt[1]), ", ".join(vertices[pt])] for pt in ordenados],
            ),
        )
    )

    # ---- Direcciones de recesión (región no acotada) --------------------------------------
    candidatos = [(Fraction(1), Fraction(0)), (Fraction(0), Fraction(1))]
    for a, b, _, _, _ in utiles:
        candidatos += [(b, -a), (-b, a)]

    def es_rayo(d: Punto) -> bool:
        if d == (0, 0) or d[0] < 0 or d[1] < 0:
            return False
        for a, b, signo, _, _ in utiles:
            v = a * d[0] + b * d[1]
            if (signo == "<=" and v > 0) or (signo == ">=" and v < 0) or (signo == "=" and v != 0):
                return False
        return True

    rayos = [d for d in dict.fromkeys(candidatos) if es_rayo(d)]
    region_no_acotada = bool(rayos)

    # ---- Evaluación de Z -----------------------------------------------------------------------
    z_vert = {pt: c[0] * pt[0] + c[1] * pt[1] for pt in ordenados}
    mejor = max(z_vert.values()) if es_max else min(z_vert.values())
    optimos = [pt for pt in ordenados if z_vert[pt] == mejor]
    lineas_eval = [
        f"Z({letras[pt]}) = {latex(c[0])}\\cdot {_par(pt[0])} + {latex(c[1])}\\cdot {_par(pt[1])} = {latex(z_vert[pt])}"
        for pt in ordenados
    ]
    res.pasos.append(
        Paso(
            titulo="Evaluación de la función objetivo en los vértices",
            explicacion=f"La solución óptima está en el vértice con el {'mayor' if es_max else 'menor'} valor de Z.",
            formula="Z = " + expresion_latex(c, [nx, ny]),
            lineas=lineas_eval,
            tabla=Tabla(
                columnas=["Vértice", f"({nx}, {ny})", "Z"],
                filas=[[letras[pt], f"({texto(pt[0])}, {texto(pt[1])})", texto(z_vert[pt])] for pt in ordenados],
                filas_resaltadas=[ordenados.index(pt) for pt in optimos],
            ),
        )
    )

    # ---- ¿No acotado? ----------------------------------------------------------------------------------
    mejora = [d for d in rayos if (c[0] * d[0] + c[1] * d[1] > 0 if es_max else c[0] * d[0] + c[1] * d[1] < 0)]
    if mejora:
        res.estado = Estado.NO_ACOTADO
        res.resumen = "El problema no tiene solución óptima finita (la región es no acotada y Z mejora sin límite)."
        d = mejora[0]
        res.pasos.append(
            Paso(
                titulo="Problema no acotado",
                explicacion=(
                    f"La región factible no está acotada y, al avanzar en la dirección ({texto(d[0])}, {texto(d[1])}), "
                    f"todas las restricciones se siguen cumpliendo mientras Z {'crece' if es_max else 'decrece'} sin límite."
                ),
            )
        )
        res.figuras.append(_figura(p, utiles, z_vert, [], letras, True, c))
        return res

    # ---- Solución óptima ------------------------------------------------------------------------------------
    x = list(optimos[0])
    z = mejor
    rayo_optimo = [d for d in rayos if c[0] * d[0] + c[1] * d[1] == 0]
    if len(optimos) > 1 or rayo_optimo:
        res.estado = Estado.MULTIPLES_OPTIMOS

    nombres_opt = ", ".join(letras[pt] for pt in optimos)
    explicacion = f"El óptimo se alcanza en {'el vértice' if len(optimos) == 1 else 'los vértices'} {nombres_opt}."
    if len(optimos) > 1:
        explicacion += (
            " Hay **dos o más vértices óptimos**: la recta de Z es paralela a una arista de la región, "
            "así que todos los puntos del segmento que los une también son óptimos."
        )
    elif rayo_optimo:
        explicacion += (
            " Además, desde ese vértice parte una semirrecta de la región sobre la que Z no cambia: "
            "hay infinitas soluciones óptimas."
        )
    res.pasos.append(
        Paso(
            titulo="Solución óptima",
            explicacion=explicacion,
            sustitucion=f"Z = {latex(c[0])}\\cdot {_par(x[0])} + {latex(c[1])}\\cdot {_par(x[1])}",
            resultado=f"Z = {latex(z)}",
            lineas=[f"{nx} = {latex(x[0])}", f"{ny} = {latex(x[1])}"],
        )
    )
    res.pasos.append(
        Paso(
            titulo="Verificación en las restricciones",
            explicacion="Se evalúa el vértice óptimo en cada restricción.",
            tabla=mod.tabla_restricciones(p, x),
        )
    )
    if region_no_acotada:
        res.advertir("La región factible no está acotada, pero el óptimo es finito.", nivel="info")
    if res.estado == Estado.MULTIPLES_OPTIMOS:
        res.advertir("El problema tiene múltiples soluciones óptimas (todas con el mismo valor de Z).", nivel="info")

    res.figuras.append(_figura(p, utiles, z_vert, optimos, letras, region_no_acotada, c, z))
    res.fijar(nx, x[0])
    res.fijar(ny, x[1])
    res.fijar("Z", z)
    if len(optimos) > 1:
        res.fijar(f"alt_{nx}", optimos[-1][0])
        res.fijar(f"alt_{ny}", optimos[-1][1])
    tipo = "máximo" if es_max else "mínimo"
    res.resumen = f"Solución óptima: {nx} = {texto(x[0])}, {ny} = {texto(x[1])}; Z = {texto(z)} ({tipo})."
    if res.estado == Estado.MULTIPLES_OPTIMOS:
        res.resumen += " Existen infinitas soluciones óptimas."
    res.interpretacion = mod.interpretar(p, x, z)
    return res


def _par(x: Fraction) -> str:
    return f"({latex(x)})" if x < 0 else latex(x)


def _figura(p, utiles, z_vert, optimos, letras, no_acotada, c, z=None) -> Figura:
    """Especificación declarativa del gráfico (la dibuja la interfaz con matplotlib)."""
    nx, ny = p.variables
    xs = [float(pt[0]) for pt in z_vert]
    ys = [float(pt[1]) for pt in z_vert]
    for a, b, _, rhs, _ in utiles:
        if a != 0 and rhs / a > 0:
            xs.append(float(rhs / a))
        if b != 0 and rhs / b > 0:
            ys.append(float(rhs / b))
    xmax = (max(xs) if xs and max(xs) > 0 else 10.0) * 1.25
    ymax = (max(ys) if ys and max(ys) > 0 else 10.0) * 1.25
    if no_acotada:
        xmax, ymax = xmax * 1.3, ymax * 1.3

    poligono = [(0.0, 0.0), (xmax, 0.0), (xmax, ymax), (0.0, ymax)]
    hay_igualdad = any(s == "=" for _, _, s, _, _ in utiles)
    if hay_igualdad:
        poligono = [(float(pt[0]), float(pt[1])) for pt in sorted(z_vert)]
    else:
        for a, b, signo, rhs, _ in utiles:
            poligono = _recortar(poligono, float(a), float(b), signo, float(rhs))
            if not poligono:
                break
    if not z_vert:
        poligono = []

    return Figura(
        tipo="region_factible",
        titulo="Región factible y solución óptima",
        datos={
            "variables": [nx, ny],
            "rectas": [
                {
                    "a": float(a),
                    "b": float(b),
                    "signo": SIGNO_TEXTO[s],
                    "rhs": float(rhs),
                    "etiqueta": f"{etq}: {expresion_texto([a, b], [nx, ny])} {SIGNO_TEXTO[s]} {texto(rhs)}",
                }
                for a, b, s, rhs, etq in utiles
            ],
            "vertices": [
                {
                    "x": float(pt[0]),
                    "y": float(pt[1]),
                    "z": float(zv),
                    "etiqueta": letras[pt] if letras else "",
                    "optimo": pt in optimos,
                }
                for pt, zv in z_vert.items()
            ],
            "poligono": [[x, y] for x, y in poligono],
            "no_acotada": no_acotada,
            "limites": [xmax, ymax],
            "recta_objetivo": (
                {"c1": float(c[0]), "c2": float(c[1]), "valor": float(z)} if z is not None else None
            ),
            "objetivo": p.objetivo,
        },
    )


def resolver_datos(datos) -> Resultado:
    """Valida y resuelve; nunca lanza excepciones (ver ``core.validador.ejecutar``)."""
    return ejecutar(ProblemaPL, datos, resolver, "grafico", "Método gráfico")
