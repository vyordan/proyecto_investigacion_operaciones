"""Problema de asignación: método húngaro con aritmética exacta (``Fraction``).

1. Si la matriz no es cuadrada se completan filas o columnas ficticias (costo 0).
2. Maximizar se convierte a minimizar con c' = M - c (M = mayor valor).
3. Reducción por filas y por columnas.
4. Se cubren los ceros con el mínimo de líneas (emparejamiento máximo +
   teorema de König). Si hacen falta N líneas hay asignación óptima; si no,
   se resta el menor elemento no cubierto y se repite.
"""
from __future__ import annotations

from fractions import Fraction

from core.esquemas import DatosAsignacion
from core.formato import a_fraccion, celda, lista_es, texto
from core.resultado import Estado, Paso, Resultado, Tabla
from core.validador import ejecutar

MAX_ITERACIONES = 200


# --------------------------------------------------------------------------- #
# Emparejamiento y cobertura mínima
# --------------------------------------------------------------------------- #
def _emparejar(N: int, ady: list[list[int]]) -> dict[int, int]:
    """Emparejamiento máximo (fila -> columna) entre filas y columnas con cero (Kuhn)."""
    col_fila = [-1] * N

    def intentar(i: int, vistos: set[int]) -> bool:
        for j in ady[i]:
            if j in vistos:
                continue
            vistos.add(j)
            if col_fila[j] == -1 or intentar(col_fila[j], vistos):
                col_fila[j] = i
                return True
        return False

    for i in range(N):
        intentar(i, set())
    return {col_fila[j]: j for j in range(N) if col_fila[j] != -1}


def _cobertura(N: int, ady: list[list[int]], emp: dict[int, int]) -> tuple[list[int], list[int]]:
    """Mínimas filas y columnas que cubren todos los ceros (teorema de König)."""
    col_fila = {j: i for i, j in emp.items()}
    z_filas = {i for i in range(N) if i not in emp}
    z_cols: set[int] = set()
    pila = list(z_filas)
    while pila:
        i = pila.pop()
        for j in ady[i]:
            if j not in z_cols:
                z_cols.add(j)
                r = col_fila.get(j)
                if r is not None and r not in z_filas:
                    z_filas.add(r)
                    pila.append(r)
    filas_cub = [i for i in range(N) if i not in z_filas]
    return filas_cub, sorted(z_cols)


def _hay_alternativa(N: int, ady: list[list[int]], emp: dict[int, int]) -> bool:
    """¿Existe otra asignación óptima distinta? (se prohíbe cada celda asignada y se reintenta)."""
    for i, j in emp.items():
        ady2 = [[x for x in fila if not (a == i and x == j)] for a, fila in enumerate(ady)]
        if len(_emparejar(N, ady2)) == N:
            return True
    return False


# --------------------------------------------------------------------------- #
# Tablas
# --------------------------------------------------------------------------- #
def _tabla(titulo, w, nom_f, nom_c, **extra) -> Tabla:
    return Tabla(
        titulo=titulo,
        columnas=[""] + list(nom_c),
        filas=[[nom_f[i]] + [celda(x) for x in w[i]] for i in range(len(w))],
        **extra,
    )


# --------------------------------------------------------------------------- #
# Resolución
# --------------------------------------------------------------------------- #
def resolver(p: DatosAsignacion) -> Resultado:
    res = Resultado(modulo="asignacion", estado=Estado.OPTIMO, titulo="Problema de asignación")
    es_max = p.objetivo == "max"

    c_orig = [[a_fraccion(x) for x in fila] for fila in p.costos]
    m_real, n_real = len(c_orig), len(c_orig[0])
    nom_f = list(p.nombres_filas or [f"A{i + 1}" for i in range(m_real)])
    nom_c = list(p.nombres_columnas or [f"T{j + 1}" for j in range(n_real)])

    res.pasos.append(
        Paso(
            titulo="Matriz de datos",
            explicacion=(
                f"{m_real} fila(s) y {n_real} columna(s). Se busca la asignación uno a uno que "
                f"**{'maximice' if es_max else 'minimice'}** el {'beneficio' if es_max else 'costo'} total."
            ),
            tabla=_tabla("Matriz original", c_orig, nom_f, nom_c),
        )
    )

    # ---- Matriz cuadrada -------------------------------------------------------------
    N = max(m_real, n_real)
    if m_real != n_real:
        for i in range(m_real, N):
            nom_f.append("Ficticia")
            c_orig.append([Fraction(0)] * N)
        for fila in c_orig[:m_real]:
            fila.extend([Fraction(0)] * (N - n_real))
        for j in range(n_real, N):
            nom_c.append("Ficticia")
        quien = "filas" if m_real < n_real else "columnas"
        res.pasos.append(
            Paso(
                titulo="Matriz cuadrada",
                explicacion=(
                    f"La matriz no es cuadrada: se agregan {N - min(m_real, n_real)} {quien} ficticias con costo 0. "
                    "Quien quede asignado a una ficticia queda sin asignación real."
                ),
                tabla=_tabla("Matriz cuadrada", c_orig, nom_f, nom_c),
            )
        )
        res.advertir("La matriz no era cuadrada: se completó con filas o columnas ficticias.", "info")

    # ---- Maximización ------------------------------------------------------------------
    if es_max:
        M = max(x for fila in c_orig for x in fila)
        w = [[M - x for x in fila] for fila in c_orig]
        res.pasos.append(
            Paso(
                titulo="Conversión a minimización",
                explicacion=(
                    f"Para maximizar se trabaja con c' = M − c, con M = {texto(M)} (el mayor valor de la matriz)."
                ),
                formula=r"c'_{ij} = M - c_{ij}",
                tabla=_tabla("Matriz transformada c'", w, nom_f, nom_c),
            )
        )
    else:
        w = [list(fila) for fila in c_orig]

    # ---- Reducciones ----------------------------------------------------------------------
    minimos_f = [min(fila) for fila in w]
    w = [[x - minimos_f[i] for x in fila] for i, fila in enumerate(w)]
    res.pasos.append(
        Paso(
            titulo="Reducción por filas",
            explicacion="A cada fila se le resta su menor elemento: "
            + ", ".join(f"{nom_f[i]}: {texto(minimos_f[i])}" for i in range(N)) + ".",
            tabla=_tabla("Matriz tras restar el mínimo de cada fila", w, nom_f, nom_c),
        )
    )
    minimos_c = [min(w[i][j] for i in range(N)) for j in range(N)]
    w = [[w[i][j] - minimos_c[j] for j in range(N)] for i in range(N)]
    res.pasos.append(
        Paso(
            titulo="Reducción por columnas",
            explicacion="A cada columna se le resta su menor elemento: "
            + ", ".join(f"{nom_c[j]}: {texto(minimos_c[j])}" for j in range(N)) + ".",
            tabla=_tabla("Matriz tras restar el mínimo de cada columna", w, nom_f, nom_c),
        )
    )

    # ---- Cobertura de ceros ---------------------------------------------------------------------
    emp: dict[int, int] = {}
    ady: list[list[int]] = []
    for it in range(1, MAX_ITERACIONES + 1):
        ady = [[j for j in range(N) if w[i][j] == 0] for i in range(N)]
        emp = _emparejar(N, ady)
        if len(emp) == N:
            res.pasos.append(
                Paso(
                    titulo=f"Iteración {it}: prueba de optimalidad",
                    explicacion=(
                        f"Se necesitan {N} líneas para cubrir todos los ceros (igual al tamaño de la matriz N = {N}): "
                        "existe una asignación completa sobre ceros. **Es la asignación óptima.**"
                    ),
                    tabla=_tabla("Ceros de la matriz", w, nom_f, nom_c,
                                 celdas_resaltadas=[(i, j + 1) for i, j in sorted(emp.items())]),
                )
            )
            break
        filas_cub, cols_cub = _cobertura(N, ady, emp)
        libres = [w[i][j] for i in range(N) for j in range(N) if i not in filas_cub and j not in cols_cub]
        k = min(libres)
        res.pasos.append(
            Paso(
                titulo=f"Iteración {it}: cubrir los ceros",
                explicacion=(
                    f"Los ceros se cubren con {len(emp)} líneas (< N = {N}), todavía no hay asignación completa. "
                    f"El menor elemento no cubierto es k = {texto(k)}: se resta a los elementos no cubiertos y se "
                    "suma a los que están en la intersección de dos líneas."
                ),
                tabla=_tabla(
                    "Cobertura mínima de ceros", w, nom_f, nom_c,
                    filas_cubiertas=filas_cub, columnas_cubiertas=[j + 1 for j in cols_cub],
                ),
            )
        )
        w = [
            [
                w[i][j] - k if (i not in filas_cub and j not in cols_cub)
                else w[i][j] + k if (i in filas_cub and j in cols_cub)
                else w[i][j]
                for j in range(N)
            ]
            for i in range(N)
        ]
    else:
        res.estado = Estado.NO_SOPORTADO
        res.resumen = "No se llegó a una asignación completa dentro del límite de iteraciones."
        res.advertir(f"Se alcanzó el límite de {MAX_ITERACIONES} iteraciones.", "error")
        return res

    # ---- Resultado --------------------------------------------------------------------------------------
    pares = sorted(emp.items())
    total = sum((c_orig[i][j] for i, j in pares if i < m_real and j < n_real), Fraction(0))
    lineas = []
    interp = []
    for i, j in pares:
        if i < m_real and j < n_real:
            lineas.append(f"{nom_f[i]} → {nom_c[j]}: costo {texto(c_orig[i][j])}")
            interp.append(f"{nom_f[i]} con {nom_c[j]} ({texto(c_orig[i][j])})")
            res.fijar(f"x{i + 1}_{j + 1}", Fraction(1))
        elif i < m_real:
            lineas.append(f"{nom_f[i]} → sin asignación")
            interp.append(f"{nom_f[i]} queda sin asignación")
        else:
            lineas.append(f"{nom_c[j]} → sin asignación")
            interp.append(f"{nom_c[j]} queda sin asignación")
    res.fijar("Z", total)
    sustitucion = " + ".join(
        celda(c_orig[i][j]) for i, j in pares if i < m_real and j < n_real
    ) or "0"
    res.pasos.append(
        Paso(
            titulo="Asignación óptima",
            explicacion="\n".join(f"- {t}" for t in lineas),
            sustitucion=f"Z = {sustitucion}",
            resultado=f"Z = {celda(total)}",
            tabla=_tabla(
                "Asignación (celdas verdes) sobre la matriz original", c_orig, nom_f, nom_c,
                celdas_resaltadas=[(i, j + 1) for i, j in pares],
            ),
        )
    )

    tipo = "beneficio máximo" if es_max else "costo mínimo"
    res.interpretacion = f"La asignación óptima es: {lista_es(interp)}. El {tipo} total es {texto(total)}."
    res.resumen = f"{tipo.capitalize()} total Z = {texto(total)}."
    if _hay_alternativa(N, ady, emp):
        res.estado = Estado.MULTIPLES_OPTIMOS
        res.advertir("Existen otras asignaciones óptimas con el mismo valor total.", "info")
        res.resumen += " Existen otras asignaciones óptimas."
    return res


def resolver_datos(datos) -> Resultado:
    """Valida y resuelve; nunca lanza excepciones (ver ``core.validador.ejecutar``)."""
    return ejecutar(DatosAsignacion, datos, resolver, "asignacion", "Problema de asignación")
