"""Problema de transporte con aritmética exacta (``Fraction``).

1. Balanceo: si oferta ≠ demanda se agrega un destino u origen ficticio (costo 0).
2. Solución básica inicial: esquina noroeste, costo mínimo o Vogel.
3. Optimización con MODI (método de los multiplicadores u_i, v_j) hasta que
   todos los costos reducidos sean >= 0.

Maximizar se resuelve minimizando c' = M - c (M = mayor costo).
Una celda básica con 0 unidades se muestra como ε (solución degenerada).
"""
from __future__ import annotations

from collections import defaultdict, deque
from fractions import Fraction

from core.esquemas import DatosTransporte
from core.formato import a_fraccion, celda, latex, lista_es, texto
from core.resultado import Estado, Paso, Resultado, Tabla
from core.validador import ejecutar

MAX_ITERACIONES = 100
NOMBRES_METODO = {
    "esquina_noroeste": "esquina noroeste",
    "costo_minimo": "costo mínimo",
    "vogel": "aproximación de Vogel",
}
EPS = "ε"


# --------------------------------------------------------------------------- #
# Soluciones iniciales
# --------------------------------------------------------------------------- #
def _tachar(i, j, s, d, filas, cols):
    """Tacha una fila o una columna. Si ambas se agotan a la vez, solo una (queda degenerada)."""
    if s[i] == 0 and d[j] == 0:
        if len(filas) > 1:
            filas.discard(i)
        else:
            cols.discard(j)
    elif s[i] == 0:
        filas.discard(i)
    else:
        cols.discard(j)


def _noroeste(c, S, D, nom_o, nom_d):
    m, n = len(S), len(D)
    s, d = list(S), list(D)
    asig: dict[tuple[int, int], Fraction] = {}
    notas = []
    i = j = 0
    while True:
        q = min(s[i], d[j])
        asig[(i, j)] = q
        notas.append(f"Celda ({nom_o[i]}, {nom_d[j]}): mín({texto(s[i])}, {texto(d[j])}) = {texto(q)}.")
        s[i] -= q
        d[j] -= q
        if i == m - 1 and j == n - 1:
            break
        if s[i] == 0 and d[j] == 0:
            if i < m - 1:
                i += 1
            else:
                j += 1
        elif s[i] == 0:
            i += 1
        else:
            j += 1
    return asig, notas


def _costo_minimo(c, S, D, nom_o, nom_d):
    m, n = len(S), len(D)
    s, d = list(S), list(D)
    filas, cols = set(range(m)), set(range(n))
    asig: dict[tuple[int, int], Fraction] = {}
    notas = []
    while filas and cols:
        _, i, j = min((c[i][j], i, j) for i in filas for j in cols)
        q = min(s[i], d[j])
        asig[(i, j)] = q
        notas.append(
            f"Menor costo disponible: {texto(c[i][j])} en ({nom_o[i]}, {nom_d[j]}); "
            f"se asigna mín({texto(s[i])}, {texto(d[j])}) = {texto(q)}."
        )
        s[i] -= q
        d[j] -= q
        if len(filas) == 1 and len(cols) == 1:
            break
        _tachar(i, j, s, d, filas, cols)
    return asig, notas


def _vogel(c, S, D, nom_o, nom_d):
    m, n = len(S), len(D)
    s, d = list(S), list(D)
    filas, cols = set(range(m)), set(range(n))
    asig: dict[tuple[int, int], Fraction] = {}
    notas = []

    def penal(valores):
        valores = sorted(valores)
        return valores[1] - valores[0] if len(valores) > 1 else valores[0]

    while filas and cols:
        if len(filas) == 1 and len(cols) == 1:
            i, j = next(iter(filas)), next(iter(cols))
            pen_txt = "queda una sola celda"
        else:
            pf = {i: penal([c[i][j] for j in cols]) for i in sorted(filas)}
            pc = {j: penal([c[i][j] for i in filas]) for j in sorted(cols)}
            candidatos = [(p, 0, i) for i, p in pf.items()] + [(p, 1, j) for j, p in pc.items()]
            mejor = max(candidatos, key=lambda t: (t[0], -t[1], -t[2]))
            if mejor[1] == 0:
                i = mejor[2]
                j = min(cols, key=lambda jj: (c[i][jj], jj))
            else:
                j = mejor[2]
                i = min(filas, key=lambda ii: (c[ii][j], ii))
            pen_f = ", ".join(f"{nom_o[k]}: {texto(v)}" for k, v in pf.items())
            pen_c = ", ".join(f"{nom_d[k]}: {texto(v)}" for k, v in pc.items())
            linea = f"fila {nom_o[mejor[2]]}" if mejor[1] == 0 else f"columna {nom_d[mejor[2]]}"
            pen_txt = (
                f"penalizaciones de filas ({pen_f}) y de columnas ({pen_c}); la mayor es {texto(mejor[0])} "
                f"en la {linea}"
            )
        q = min(s[i], d[j])
        asig[(i, j)] = q
        notas.append(
            f"{pen_txt[0].upper() + pen_txt[1:]}. Se elige la celda de menor costo de esa línea, "
            f"({nom_o[i]}, {nom_d[j]}) con costo {texto(c[i][j])}, y se asigna {texto(q)}."
        )
        s[i] -= q
        d[j] -= q
        if len(filas) == 1 and len(cols) == 1:
            break
        _tachar(i, j, s, d, filas, cols)
    return asig, notas


_INICIALES = {"esquina_noroeste": _noroeste, "costo_minimo": _costo_minimo, "vogel": _vogel}


# --------------------------------------------------------------------------- #
# MODI
# --------------------------------------------------------------------------- #
def _potenciales(c, basicas, m, n):
    u: list[Fraction | None] = [None] * m
    v: list[Fraction | None] = [None] * n
    u[0] = Fraction(0)
    cambio = True
    while cambio:
        cambio = False
        for (i, j) in sorted(basicas):
            if u[i] is not None and v[j] is None:
                v[j] = c[i][j] - u[i]
                cambio = True
            elif v[j] is not None and u[i] is None:
                u[i] = c[i][j] - v[j]
                cambio = True
    return u, v


def _ciclo(basicas, i, j):
    """Camino en el árbol de celdas básicas desde la columna j hasta la fila i."""
    ady = defaultdict(list)
    for (a, b) in basicas:
        ady[("f", a)].append((("c", b), (a, b)))
        ady[("c", b)].append((("f", a), (a, b)))
    inicio, fin = ("c", j), ("f", i)
    padre = {inicio: None}
    cola = deque([inicio])
    while cola:
        nodo = cola.popleft()
        if nodo == fin:
            break
        for vecino, cel in sorted(ady[nodo], key=lambda t: t[1]):
            if vecino not in padre:
                padre[vecino] = (nodo, cel)
                cola.append(vecino)
    camino = []
    nodo = fin
    while padre[nodo] is not None:
        previo, cel = padre[nodo]
        camino.append(cel)
        nodo = previo
    camino.reverse()
    return camino


# --------------------------------------------------------------------------- #
# Tablas de presentación
# --------------------------------------------------------------------------- #
def _tabla_datos(titulo, c_orig, S, D, nom_o, nom_d):
    columnas = ["Origen"] + nom_d + ["Oferta"]
    filas = [[nom_o[i]] + [celda(x) for x in c_orig[i]] + [celda(S[i])] for i in range(len(S))]
    filas.append(["Demanda"] + [celda(x) for x in D] + [celda(sum(S, Fraction(0)))])
    return Tabla(titulo=titulo, columnas=columnas, filas=filas)


def _tabla_asignacion(titulo, c_orig, asig, S, D, nom_o, nom_d, u=None, v=None, notas=""):
    m, n = len(S), len(D)
    columnas = ["Origen"] + nom_d + ["Oferta"] + (["uᵢ"] if u is not None else [])
    filas = []
    resaltadas = []
    for i in range(m):
        fila = [nom_o[i]]
        for j in range(n):
            if (i, j) in asig:
                x = asig[(i, j)]
                fila.append(f"{EPS} (c={celda(c_orig[i][j])})" if x == 0 else f"{celda(x)} (c={celda(c_orig[i][j])})")
                resaltadas.append((i, j + 1))
            else:
                fila.append(f"c={celda(c_orig[i][j])}")
        fila.append(celda(S[i]))
        if u is not None:
            fila.append(celda(u[i]))
        filas.append(fila)
    filas.append(["Demanda"] + [celda(x) for x in D] + [celda(sum(S, Fraction(0)))] + ([""] if u is not None else []))
    if v is not None:
        filas.append(["vⱼ"] + [celda(x) for x in v] + [""] + ([""] if u is not None else []))
    return Tabla(titulo=titulo, columnas=columnas, filas=filas, celdas_resaltadas=resaltadas, notas=notas)


def _costo_total(c_orig, asig):
    return sum((c_orig[i][j] * x for (i, j), x in asig.items()), Fraction(0))


def _nombre_var(i, j):
    return f"x{i + 1}_{j + 1}"


# --------------------------------------------------------------------------- #
# Resolución
# --------------------------------------------------------------------------- #
def resolver(p: DatosTransporte) -> Resultado:
    res = Resultado(modulo="transporte", estado=Estado.OPTIMO, titulo="Problema de transporte")
    es_max = p.objetivo == "max"

    S = [a_fraccion(v) for v in p.oferta]
    D = [a_fraccion(v) for v in p.demanda]
    c_orig = [[a_fraccion(x) for x in fila] for fila in p.costos]
    nom_o = list(p.nombres_origenes or [f"O{i + 1}" for i in range(len(S))])
    nom_d = list(p.nombres_destinos or [f"D{j + 1}" for j in range(len(D))])
    m_real, n_real = len(S), len(D)

    res.pasos.append(
        Paso(
            titulo="Datos del problema",
            explicacion=(
                f"{m_real} origen(es) y {n_real} destino(s). Se desea "
                f"**{'maximizar' if es_max else 'minimizar'}** el {'beneficio' if es_max else 'costo'} total de transporte."
            ),
            tabla=_tabla_datos("Costos unitarios, oferta y demanda", c_orig, S, D, nom_o, nom_d),
        )
    )

    # ---- Balanceo ----------------------------------------------------------------
    tot_s, tot_d = sum(S, Fraction(0)), sum(D, Fraction(0))
    if tot_s > tot_d:
        dif = tot_s - tot_d
        nom_d.append("Ficticio")
        D.append(dif)
        for fila in c_orig:
            fila.append(Fraction(0))
        res.pasos.append(
            Paso(
                titulo="Balanceo del problema",
                explicacion=(
                    f"La oferta total ({texto(tot_s)}) supera a la demanda total ({texto(tot_d)}). "
                    f"Se agrega un **destino ficticio** con demanda {texto(dif)} y costos 0: lo que se le asigne "
                    "representa unidades que quedan sin enviar."
                ),
                tabla=_tabla_datos("Problema balanceado", c_orig, S, D, nom_o, nom_d),
            )
        )
        res.advertir("El problema estaba desbalanceado (oferta > demanda): se agregó un destino ficticio.", "info")
    elif tot_d > tot_s:
        dif = tot_d - tot_s
        nom_o.append("Ficticio")
        S.append(dif)
        c_orig.append([Fraction(0)] * len(D))
        res.pasos.append(
            Paso(
                titulo="Balanceo del problema",
                explicacion=(
                    f"La demanda total ({texto(tot_d)}) supera a la oferta total ({texto(tot_s)}). "
                    f"Se agrega un **origen ficticio** con oferta {texto(dif)} y costos 0: lo que se le asigne "
                    "representa demanda que no se alcanza a cubrir."
                ),
                tabla=_tabla_datos("Problema balanceado", c_orig, S, D, nom_o, nom_d),
            )
        )
        res.advertir("El problema estaba desbalanceado (demanda > oferta): se agregó un origen ficticio.", "info")
    else:
        res.pasos.append(
            Paso(
                titulo="Verificación del balance",
                explicacion=f"Oferta total = demanda total = {texto(tot_s)}: el problema ya está balanceado.",
            )
        )

    m, n = len(S), len(D)

    # ---- Maximización -------------------------------------------------------------------
    if es_max:
        M = max(x for fila in c_orig for x in fila)
        c = [[M - x for x in fila] for fila in c_orig]
        res.pasos.append(
            Paso(
                titulo="Conversión a minimización",
                explicacion=(
                    f"Para maximizar se resuelve el problema equivalente de minimización con costos "
                    f"c' = M − c, donde M = {texto(M)} es el mayor valor de la matriz."
                ),
                formula=r"c'_{ij} = M - c_{ij}",
                tabla=_tabla_datos("Costos transformados c'", c, S, D, nom_o, nom_d),
            )
        )
    else:
        c = c_orig

    # ---- Solución inicial ------------------------------------------------------------------
    asig, notas = _INICIALES[p.metodo_inicial](c, S, D, nom_o, nom_d)
    res.pasos.append(
        Paso(
            titulo=f"Solución inicial por {NOMBRES_METODO[p.metodo_inicial]}",
            explicacion="\n".join(f"{k}. {t}" for k, t in enumerate(notas, 1))
            + f"\n\nSe obtienen {len(asig)} celdas básicas (m + n − 1 = {m + n - 1}). "
            + (f"Las celdas con {EPS} son básicas con 0 unidades (solución degenerada)." if any(v == 0 for v in asig.values()) else ""),
            tabla=_tabla_asignacion(
                "Asignación inicial", c_orig, asig, S, D, nom_o, nom_d,
                notas=f"Costo total = {texto(_costo_total(c_orig, asig))}",
            ),
        )
    )
    if any(v == 0 for v in asig.values()):
        res.advertir("La solución es degenerada: hay celdas básicas con 0 unidades (ε).", "info")

    # ---- MODI ----------------------------------------------------------------------------------
    alternativo = False
    for it in range(1, MAX_ITERACIONES + 1):
        basicas = set(asig)
        u, v = _potenciales(c, basicas, m, n)
        reducidos = {
            (i, j): c[i][j] - u[i] - v[j] for i in range(m) for j in range(n) if (i, j) not in basicas
        }
        ecuaciones = ", ".join(
            f"u{i + 1} + v{j + 1} = {texto(c[i][j])}" for (i, j) in sorted(basicas)
        )
        negativos = {k: x for k, x in reducidos.items() if x < 0}
        tabla_red = Tabla(
            titulo="Costos reducidos dᵢⱼ = cᵢⱼ − uᵢ − vⱼ (celdas no básicas)",
            columnas=["Origen"] + nom_d,
            filas=[
                [nom_o[i]] + [celda(reducidos[(i, j)]) if (i, j) in reducidos else "básica" for j in range(n)]
                for i in range(m)
            ],
        )
        tabla_actual = _tabla_asignacion(
            "Asignación actual con multiplicadores", c_orig, asig, S, D, nom_o, nom_d, u=u, v=v,
            notas=f"Costo total = {texto(_costo_total(c_orig, asig))}",
        )
        base_txt = (
            "Se fija u1 = 0 y, para cada celda básica, uᵢ + vⱼ = cᵢⱼ:\n\n"
            f"{ecuaciones}.\n\n"
            "Resultan " + ", ".join(f"u{i + 1} = {texto(u[i])}" for i in range(m)) + "; "
            + ", ".join(f"v{j + 1} = {texto(v[j])}" for j in range(n)) + "."
        )

        if not negativos:
            ceros = [k for k, x in reducidos.items() if x == 0]
            tabla_red.notas = "Todos los costos reducidos son ≥ 0."
            res.pasos.append(
                Paso(
                    titulo=f"MODI · Iteración {it} (prueba de optimalidad)",
                    explicacion=base_txt + "\n\nTodos los costos reducidos son ≥ 0: **la solución es óptima**.",
                    tablas=[tabla_actual, tabla_red],
                )
            )
            # ¿Óptimos alternativos? (celda no básica con d = 0 cuyo ciclo permite θ > 0)
            for (i, j) in ceros:
                camino = _ciclo(basicas, i, j)
                theta = min(asig[cel] for k, cel in enumerate(camino) if k % 2 == 0)
                if theta > 0:
                    alternativo = True
                    break
            break

        entra = min(negativos, key=lambda k: (negativos[k], k))
        camino = _ciclo(basicas, *entra)
        menos = [cel for k, cel in enumerate(camino) if k % 2 == 0]
        mas = [cel for k, cel in enumerate(camino) if k % 2 == 1]
        theta = min(asig[cel] for cel in menos)
        sale = min((cel for cel in menos if asig[cel] == theta))
        etiqueta_celda = lambda cel: f"({nom_o[cel[0]]}, {nom_d[cel[1]]})"
        ciclo_txt = (
            f"Ciclo: +{etiqueta_celda(entra)}; "
            + "; ".join(
                f"{'−' if k % 2 == 0 else '+'}{etiqueta_celda(cel)}" for k, cel in enumerate(camino)
            )
            + f". Se resta y suma θ = mín de las celdas con «−» = {texto(theta)}; sale {etiqueta_celda(sale)}."
        )
        tabla_red.pivote = (entra[0], entra[1] + 1)
        res.pasos.append(
            Paso(
                titulo=f"MODI · Iteración {it}",
                explicacion=(
                    base_txt
                    + f"\n\nEl costo reducido más negativo es d = {texto(negativos[entra])} en la celda "
                    f"{etiqueta_celda(entra)}, que entra a la base.\n\n{ciclo_txt}"
                ),
                tablas=[tabla_actual, tabla_red],
            )
        )
        asig[entra] = theta  # la celda que entra recibe +θ
        for cel in mas:
            asig[cel] += theta
        for cel in menos:
            asig[cel] -= theta
        del asig[sale]
    else:
        res.estado = Estado.NO_SOPORTADO
        res.resumen = "No se llegó al óptimo dentro del límite de iteraciones."
        res.advertir(f"Se alcanzó el límite de {MAX_ITERACIONES} iteraciones (posible ciclado).", "error")
        return res

    # ---- Resultado ---------------------------------------------------------------------------------
    total = _costo_total(c_orig, asig)
    reales = {k: x for k, x in asig.items() if k[0] < m_real and k[1] < n_real and x > 0}
    terminos = " + ".join(
        f"{latex(c_orig[i][j])}\\cdot {latex(x)}" for (i, j), x in sorted(asig.items()) if x > 0
    )
    res.pasos.append(
        Paso(
            titulo="Solución óptima y costo total",
            formula=r"Z = \sum c_{ij}\,x_{ij}",
            sustitucion=f"Z = {terminos or '0'}",
            resultado=f"Z = {latex(total)}",
            tabla=_tabla_asignacion("Plan de envíos óptimo", c_orig, asig, S, D, nom_o, nom_d,
                                    notas=f"Costo total = {texto(total)}"),
        )
    )

    envios = []
    for (i, j), x in sorted(reales.items()):
        envios.append(f"enviar {texto(x)} unidades de {nom_o[i]} a {nom_d[j]} (costo unitario {texto(c_orig[i][j])})")
        res.fijar(_nombre_var(i, j), x)
    res.fijar("Z", total)

    sin_enviar = [(nom_o[i], x) for (i, j), x in asig.items() if j >= n_real and i < m_real and x > 0]
    sin_cubrir = [(nom_d[j], x) for (i, j), x in asig.items() if i >= m_real and j < n_real and x > 0]
    interp = f"El plan óptimo es: {lista_es(envios)}." if envios else "No hay envíos."
    if sin_enviar:
        interp += " Quedan sin enviar: " + lista_es([f"{texto(x)} en {o}" for o, x in sin_enviar]) + "."
    if sin_cubrir:
        interp += " Demanda sin cubrir: " + lista_es([f"{texto(x)} en {d}" for d, x in sin_cubrir]) + "."
    interp += f" El {'beneficio máximo' if es_max else 'costo mínimo'} total es {texto(total)}."
    res.interpretacion = interp
    res.resumen = f"{'Beneficio máximo' if es_max else 'Costo mínimo'} total Z = {texto(total)}."

    if alternativo:
        res.estado = Estado.MULTIPLES_OPTIMOS
        res.advertir(
            "Existen soluciones óptimas alternativas: hay una celda no básica con costo reducido 0 que "
            "puede entrar a la base sin cambiar el costo total.",
            "info",
        )
        res.resumen += " Existen soluciones óptimas alternativas."
    return res


def costo_solucion_inicial(p: DatosTransporte, metodo: str | None = None) -> Fraction:
    """Costo de la solución básica inicial (sin optimizar) con el método indicado.

    Se usa para generar y corregir prácticas. Aplica el mismo balanceo (origen o
    destino ficticio con costo 0) que ``resolver``.
    """
    S = [a_fraccion(v) for v in p.oferta]
    D = [a_fraccion(v) for v in p.demanda]
    c = [[a_fraccion(x) for x in fila] for fila in p.costos]
    if sum(S, Fraction(0)) > sum(D, Fraction(0)):
        D.append(sum(S, Fraction(0)) - sum(D, Fraction(0)))
        for fila in c:
            fila.append(Fraction(0))
    elif sum(D, Fraction(0)) > sum(S, Fraction(0)):
        S.append(sum(D, Fraction(0)) - sum(S, Fraction(0)))
        c.append([Fraction(0)] * len(D))
    nom_o = [f"O{i + 1}" for i in range(len(S))]
    nom_d = [f"D{j + 1}" for j in range(len(D))]
    asig, _ = _INICIALES[metodo or p.metodo_inicial](c, S, D, nom_o, nom_d)
    return _costo_total(c, asig)


def resolver_datos(datos) -> Resultado:
    """Valida y resuelve; nunca lanza excepciones (ver ``core.validador.ejecutar``)."""
    return ejecutar(DatosTransporte, datos, resolver, "transporte", "Problema de transporte")
