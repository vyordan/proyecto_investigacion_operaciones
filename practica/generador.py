"""Generador de prácticas con retroalimentación determinista.

- Cada práctica se genera a partir de una *semilla*: la misma semilla produce el
  mismo ejercicio (se puede reproducir y comentar con el docente).
- Los problemas se construyen para ser factibles, acotados y con solución
  única, y la solución la calcula siempre el motor (nunca está escrita).
- La corrección compara con el motor y, además, detecta errores típicos para
  dar pistas concretas («tu punto viola la restricción R2», «olvidaste el 2»...).
"""
from __future__ import annotations

import math
import random
from fractions import Fraction
from typing import Any, Callable

from pydantic import BaseModel, Field

from algoritmos import asignacion, inventarios, simplex, transporte
from algoritmos import modelacion as mod
from core.esquemas import DatosTransporte, ProblemaPL
from core.formato import decimal, lista_es
from core.resultado import Estado, Resultado
from core.validador import validar

MODULOS = {
    "pl": "Programación lineal (simplex / gráfico)",
    "transporte": "Transporte",
    "asignacion": "Asignación",
    "eoq": "Inventarios (EOQ)",
}
DIFICULTADES = {"facil": "Fácil", "medio": "Medio"}
INTENTOS_MAX = 300


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #
class Pregunta(BaseModel):
    id: str
    etiqueta: str


class Practica(BaseModel):
    modulo: str
    dificultad: str
    semilla: int
    titulo: str
    enunciado: str  # Markdown
    datos: dict[str, Any]  # entrada del motor (sin respuestas)
    preguntas: list[Pregunta]


class ItemFeedback(BaseModel):
    id: str
    etiqueta: str
    respuesta: float | None
    correcta: bool
    mensaje: str


class Retroalimentacion(BaseModel):
    puntaje: int
    total: int
    items: list[ItemFeedback]
    pistas: list[str] = Field(default_factory=list)
    resumen: str
    solucion: Resultado  # procedimiento completo, para «ver solución»


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _cerca(respuesta: float, esperado: float) -> bool:
    """Tolerancia: exacta para enteros; para decimales, redondeos razonables."""
    if abs(esperado - round(esperado)) < 1e-9:
        return abs(respuesta - esperado) < 1e-6
    return abs(respuesta - esperado) <= max(0.01, 0.002 * abs(esperado))


def _generar_valido(constructor: Callable[[], dict], motor, aceptar: Callable[[Resultado], bool]) -> dict:
    for _ in range(INTENTOS_MAX):
        datos = constructor()
        if aceptar(motor.resolver_datos(datos)):
            return datos
    raise RuntimeError("No se pudo generar un ejercicio válido; intenta con otra semilla.")


def _markdown_tabla(columnas: list[str], filas: list[list[str]]) -> str:
    enc = "| " + " | ".join(columnas) + " |"
    sep = "|" + "|".join([":--"] + ["--:"] * (len(columnas) - 1)) + "|"
    cuerpo = ["| " + " | ".join(f) + " |" for f in filas]
    return "\n".join([enc, sep, *cuerpo])


def _partir(rng: random.Random, total: int, partes: int, paso: int = 5) -> list[int]:
    unidades = total // paso
    cortes = sorted(rng.sample(range(1, unidades), partes - 1))
    return [(b - a) * paso for a, b in zip([0] + cortes, cortes + [unidades])]


def _valor(res: Resultado, clave: str) -> float:
    return res.valores[clave]


# --------------------------------------------------------------------------- #
# Programación lineal
# --------------------------------------------------------------------------- #
_FABRICAS = [
    {"productos": [("mesa", "mesas"), ("silla", "sillas"), ("cama", "camas")],
     "recursos": ["Carpintería (horas)", "Madera (kg)", "Pintura (horas)"]},
    {"productos": [("camisa", "camisas"), ("pantalón", "pantalones"), ("chaqueta", "chaquetas")],
     "recursos": ["Tela (metros)", "Costura (horas)", "Planchado (horas)"]},
    {"productos": [("pastel", "pasteles"), ("pan", "panes"), ("galleta", "galletas")],
     "recursos": ["Harina (kg)", "Horno (horas)", "Decoración (horas)"]},
]
_MEZCLAS = [
    {"productos": ["alimento A", "alimento B", "alimento C"], "requisitos": ["Proteínas", "Vitaminas", "Minerales"]},
    {"productos": ["fertilizante A", "fertilizante B", "fertilizante C"], "requisitos": ["Nitrógeno", "Fósforo", "Potasio"]},
]


def _pl_maximizar(rng: random.Random, n: int, m: int, ceros: bool) -> dict:
    fab = rng.choice(_FABRICAS)
    prod = fab["productos"][:n]
    x0 = [rng.randint(2, 12) for _ in range(n)]
    filas = []
    for _ in range(m):
        fila = [rng.randint(1, 6) for _ in range(n)]
        if ceros and rng.random() < 0.3:
            fila[rng.randrange(n)] = 0
        filas.append(fila)
    for j in range(n):  # cada variable debe consumir algún recurso (problema acotado)
        if all(f[j] == 0 for f in filas):
            filas[rng.randrange(m)][j] = rng.randint(1, 6)
    restr = [
        {"coeficientes": f, "signo": "<=", "rhs": sum(a * v for a, v in zip(f, x0)) + rng.randint(0, 15),
         "nombre": fab["recursos"][k]}
        for k, f in enumerate(filas)
    ]
    c = [rng.randint(2, 9) for _ in range(n)]
    nombres = ["x", "y"] if n == 2 else [f"x{j + 1}" for j in range(n)]
    enunciado = (
        f"Un taller fabrica {lista_es([p[1] for p in prod])}. La utilidad por unidad es "
        + lista_es([f"Q{c[j]} por cada {prod[j][0]}" for j in range(n)])
        + ". Los recursos disponibles y el consumo de cada producto son:\n\n"
    )
    for k, r in enumerate(restr):
        usos = [f"cada {prod[j][0]} usa {r['coeficientes'][j]}" for j in range(n) if r["coeficientes"][j] > 0]
        enunciado += f"- **{r['nombre']}**: {r['rhs']} disponibles; {lista_es(usos)}.\n"
    enunciado += "\nDetermina cuántas unidades fabricar de cada producto para **maximizar** la utilidad total Z."
    return {
        "titulo": "Maximizar utilidad", "objetivo": "max", "coef_objetivo": c, "restricciones": restr,
        "nombres_variables": nombres,
        "descripciones_variables": [f"Unidades de {p[1]}" for p in prod],
        "_enunciado": enunciado,
    }


def _pl_minimizar(rng: random.Random, n: int, m: int) -> dict:
    mezcla = rng.choice(_MEZCLAS)
    prod = mezcla["productos"][:n]
    x0 = [rng.randint(2, 10) for _ in range(n)]
    filas = [[rng.randint(1, 6) for _ in range(n)] for _ in range(m)]
    restr = [
        {"coeficientes": f, "signo": ">=", "rhs": max(1, sum(a * v for a, v in zip(f, x0)) - rng.randint(0, 12)),
         "nombre": mezcla["requisitos"][k]}
        for k, f in enumerate(filas)
    ]
    c = [rng.randint(2, 9) for _ in range(n)]
    enunciado = (
        f"Se mezclan {lista_es(prod)} para elaborar un producto al menor costo. El costo por kg es "
        + lista_es([f"Q{c[j]} para el {prod[j]}" for j in range(n)])
        + ". La mezcla debe cumplir estos requisitos mínimos:\n\n"
    )
    for r in restr:
        aportes = [f"cada kg de {prod[j]} aporta {r['coeficientes'][j]}" for j in range(n)]
        enunciado += f"- **{r['nombre']}**: al menos {r['rhs']}; {lista_es(aportes)}.\n"
    enunciado += "\nDetermina cuántos kg usar de cada uno para **minimizar** el costo total Z."
    return {
        "titulo": "Minimizar costo de una mezcla", "objetivo": "min", "coef_objetivo": c, "restricciones": restr,
        "nombres_variables": ["x", "y"] if n == 2 else [f"x{j + 1}" for j in range(n)],
        "descripciones_variables": [f"Kg de {p}" for p in prod],
        "_enunciado": enunciado,
    }


def _generar_pl(rng: random.Random, dificultad: str) -> Practica:
    def construir() -> dict:
        if dificultad == "facil":
            return _pl_maximizar(rng, 2, rng.choice([2, 3]), ceros=False)
        variante = rng.choice(["max3", "min2"])
        if variante == "max3":
            return _pl_maximizar(rng, 3, 3, ceros=True)
        return _pl_minimizar(rng, 2, rng.choice([2, 3]))

    datos = _generar_valido(
        construir, simplex, lambda r: r.estado == Estado.OPTIMO and any(v > 0 for k, v in r.valores.items() if k != "Z")
    )
    enunciado = datos.pop("_enunciado")
    titulo = datos["titulo"]
    nombres = datos["nombres_variables"]
    preguntas = [Pregunta(id=nom, etiqueta=f"Valor óptimo de {nom} ({desc.lower()})")
                 for nom, desc in zip(nombres, datos["descripciones_variables"])]
    preguntas.append(Pregunta(id="Z", etiqueta="Valor óptimo de Z (en Q)"))
    return Practica(modulo="pl", dificultad=dificultad, semilla=0, titulo=titulo, enunciado=enunciado,
                    datos=datos, preguntas=preguntas)


def _feedback_pl(p: Practica, resp: dict, sol: Resultado) -> tuple[list[ItemFeedback], list[str]]:
    items, pistas = _items(p, resp, sol)
    problema, _ = validar(ProblemaPL, p.datos)
    nombres = p.datos["nombres_variables"]
    if problema is None or any(resp.get(nom) is None for nom in nombres):
        return items, pistas
    # Se trabaja con decimales y una tolerancia que absorbe el redondeo a 2 decimales del estudiante.
    x = [float(resp[nom]) for nom in nombres]
    if any(v < -1e-9 for v in x):
        pistas.append("Los valores de las variables no pueden ser negativos.")
        return items, pistas

    violadas = []
    for i, r in enumerate(problema.restricciones):
        lhs = sum(c * xi for c, xi in zip(r.coeficientes, x))
        tol = 0.005 * sum(abs(c) for c in r.coeficientes) + 1e-9
        ok = (lhs <= r.rhs + tol) if r.signo == "<=" else (lhs >= r.rhs - tol) if r.signo == ">=" else abs(lhs - r.rhs) <= tol
        if not ok:
            violadas.append(problema.etiqueta_restriccion(i))
    if violadas:
        pistas.append(
            f"Con tus valores **no se cumple** {lista_es(violadas)}: tu punto está fuera de la región factible. "
            "Sustitúyelos en esa restricción para comprobarlo."
        )
        return items, pistas

    z_propio = sum(c * xi for c, xi in zip(problema.coef_objetivo, x))
    tol_z = 0.005 * sum(abs(c) for c in problema.coef_objetivo) + 1e-9
    if resp.get("Z") is not None and abs(float(resp["Z"]) - z_propio) > 0.01 + tol_z:
        pistas.append(
            f"Tu valor de Z no coincide con evaluar la función objetivo en tu solución (daría {decimal(z_propio)}). "
            "Revisa la sustitución."
        )
    z_opt = _valor(sol, "Z")
    peor = z_propio < z_opt - tol_z if problema.objetivo == "max" else z_propio > z_opt + tol_z
    if peor:
        pistas.append(
            f"Tu solución es **factible pero no óptima**: da Z = {decimal(z_propio)} y existe una solución "
            f"{'mejor' if problema.objetivo == 'max' else 'más barata'}. Revisa qué recursos aún sobran "
            "o aplica otra iteración del simplex."
        )
    return items, pistas


# --------------------------------------------------------------------------- #
# Transporte
# --------------------------------------------------------------------------- #
def _generar_transporte(rng: random.Random, dificultad: str) -> Practica:
    m = rng.choice([2, 3])
    n = 3
    metodo = "esquina_noroeste" if dificultad == "facil" else "costo_minimo"
    nom_o = [f"Planta {chr(65 + i)}" for i in range(m)]
    nom_d = [f"Ciudad {j + 1}" for j in range(n)]

    def construir() -> dict:
        oferta = [rng.choice([20, 25, 30, 35, 40]) for _ in range(m)]
        total = sum(oferta)
        if dificultad == "medio":
            total = max(15, total + rng.choice([-10, -5, 5, 10]))
        return {
            "objetivo": "min", "metodo_inicial": metodo, "oferta": oferta,
            "demanda": _partir(rng, total, n), "costos": [[rng.randint(2, 15) for _ in range(n)] for _ in range(m)],
            "nombres_origenes": nom_o, "nombres_destinos": nom_d,
        }

    datos = _generar_valido(construir, transporte, lambda r: r.estado in (Estado.OPTIMO, Estado.MULTIPLES_OPTIMOS))
    balance = sum(datos["oferta"]) == sum(datos["demanda"])
    tabla = _markdown_tabla(
        ["Origen"] + nom_d + ["Oferta"],
        [[nom_o[i]] + [f"Q{c}" for c in datos["costos"][i]] + [str(datos["oferta"][i])] for i in range(m)]
        + [["**Demanda**"] + [str(d) for d in datos["demanda"]] + [str(sum(datos["oferta"]))]],
    )
    enunciado = (
        f"Una empresa envía un producto desde {m} plantas a {n} ciudades. La tabla muestra el costo de enviar "
        f"una unidad, la oferta de cada planta y la demanda de cada ciudad.\n\n{tabla}\n\n"
        + ("El problema está balanceado." if balance else
           f"La oferta total ({sum(datos['oferta'])}) y la demanda total ({sum(datos['demanda'])}) "
           "no coinciden: balancea con un origen o destino ficticio.")
        + f"\n\nCalcula el costo de la solución inicial por el método de **{transporte.NOMBRES_METODO[metodo]}** "
        "(en una asignación con celdas básicas en orden estándar) y luego el costo **mínimo total**."
    )
    preguntas = [
        Pregunta(id="inicial", etiqueta=f"Costo de la solución inicial ({transporte.NOMBRES_METODO[metodo]}), en Q"),
        Pregunta(id="Z", etiqueta="Costo mínimo total (óptimo), en Q"),
    ]
    return Practica(modulo="transporte", dificultad=dificultad, semilla=0, titulo="Transporte", enunciado=enunciado,
                    datos=datos, preguntas=preguntas)


def _feedback_transporte(p: Practica, resp: dict, sol: Resultado) -> tuple[list[ItemFeedback], list[str]]:
    items, pistas = _items(p, resp, sol)
    optimo = _valor(sol, "Z")
    for clave, etiqueta in (("inicial", "El costo inicial"), ("Z", "El costo total")):
        v = resp.get(clave)
        if v is None:
            continue
        if v < optimo - 1e-6:
            pistas.append(
                f"{etiqueta} que indicas es **menor que el óptimo**, lo cual es imposible: revisa que se cumplan "
                "exactamente la oferta de cada origen y la demanda de cada destino (incluido el ficticio)."
            )
    z = resp.get("Z")
    if z is not None and z > optimo + 1e-6:
        pistas.append(
            "Tu costo total es **mayor que el óptimo**: todavía existe un costo reducido negativo. "
            "Calcula los multiplicadores uᵢ, vⱼ y los costos reducidos dᵢⱼ = cᵢⱼ − uᵢ − vⱼ (MODI)."
        )
    inicial = resp.get("inicial")
    if inicial is not None and z is not None and inicial < z - 1e-6:
        pistas.append("El costo de la solución inicial no puede ser menor que el costo óptimo que indicas.")
    return items, pistas


# --------------------------------------------------------------------------- #
# Asignación
# --------------------------------------------------------------------------- #
def _generar_asignacion(rng: random.Random, dificultad: str) -> Practica:
    n = 3 if dificultad == "facil" else 4
    nom_f = ["Ana", "Beto", "Carla", "Diego"][:n]
    nom_c = [f"Tarea {j + 1}" for j in range(n)]

    def construir() -> dict:
        return {
            "objetivo": "min", "costos": [[rng.randint(3, 25) for _ in range(n)] for _ in range(n)],
            "nombres_filas": nom_f, "nombres_columnas": nom_c,
        }

    datos = _generar_valido(construir, asignacion, lambda r: r.estado == Estado.OPTIMO)
    tabla = _markdown_tabla(["Persona"] + nom_c, [[nom_f[i]] + [f"Q{c}" for c in datos["costos"][i]] for i in range(n)])
    enunciado = (
        f"Se deben asignar {n} personas a {n} tareas (una tarea por persona y una persona por tarea). "
        f"La tabla muestra el costo de que cada persona haga cada tarea.\n\n{tabla}\n\n"
        "Aplica el **método húngaro**: indica cuánto se resta en total en la reducción por filas y el costo "
        "mínimo total de la asignación."
    )
    preguntas = [
        Pregunta(id="filas", etiqueta="Suma de los mínimos restados en la reducción por filas"),
        Pregunta(id="Z", etiqueta="Costo mínimo total de la asignación, en Q"),
    ]
    return Practica(modulo="asignacion", dificultad=dificultad, semilla=0, titulo="Asignación", enunciado=enunciado,
                    datos=datos, preguntas=preguntas)


def _feedback_asignacion(p: Practica, resp: dict, sol: Resultado) -> tuple[list[ItemFeedback], list[str]]:
    items, pistas = _items(p, resp, sol)
    costos = p.datos["costos"]
    n = len(costos)
    optimo = _valor(sol, "Z")
    suma_columnas = sum(min(costos[i][j] for i in range(n)) for j in range(n))
    f = resp.get("filas")
    if f is not None and not _cerca(f, _esperado(p, sol, "filas")) and abs(f - suma_columnas) < 1e-6:
        pistas.append("Ese valor corresponde a los mínimos de las **columnas**; en este paso se restan los de las filas.")
    z = resp.get("Z")
    if z is not None:
        if z < optimo - 1e-6:
            pistas.append("Tu costo es menor que el mínimo posible: revisa que no repitas persona ni tarea.")
        elif z > optimo + 1e-6:
            pistas.append("Tu costo no es el mínimo: aún existe una asignación más barata. Revisa que los ceros "
                          "cubran todas las filas y columnas con exactamente n líneas.")
    return items, pistas


# --------------------------------------------------------------------------- #
# Inventarios (EOQ)
# --------------------------------------------------------------------------- #
def _generar_eoq(rng: random.Random, dificultad: str) -> Practica:
    producto = rng.choice(["cajas de tornillos", "resmas de papel", "llantas", "sacos de cemento", "baterías"])
    S = rng.choice([20, 25, 40, 50, 60, 75])
    if dificultad == "facil":
        D = rng.choice([1200, 1800, 2400, 3600, 5000, 7200])
        H = rng.choice([1.5, 2, 2.5, 3, 4, 5])
        L = rng.randint(3, 15)
        datos = {"nombre_articulo": producto, "demanda": D, "periodo_demanda": "anual", "costo_pedido": S,
                 "modo_mantener": "unitario", "costo_mantener": H, "plazo_entrega": L, "unidad_plazo": "dias",
                 "dias_laborales_anio": 365, "stock_seguridad": 0}
        enunciado = (
            f"Una tienda vende {producto} con una demanda de **{D} unidades al año**. Hacer un pedido cuesta "
            f"**Q{S}** y mantener una unidad en inventario cuesta **Q{H:g} al año**. El proveedor tarda "
            f"**{L} días** en entregar y se consideran **365 días** al año."
        )
    else:
        D = rng.choice([100, 150, 200, 250, 300])
        i = rng.choice([15, 20, 25, 30])
        C = rng.choice([10, 12, 20, 40, 50, 80])
        L = rng.randint(1, 4)
        datos = {"nombre_articulo": producto, "demanda": D, "periodo_demanda": "mensual", "costo_pedido": S,
                 "modo_mantener": "porcentaje", "porcentaje_mantener": i, "costo_unitario": C, "plazo_entrega": L,
                 "unidad_plazo": "semanas", "dias_laborales_anio": 300, "stock_seguridad": 0}
        enunciado = (
            f"Una tienda vende {producto} con una demanda de **{D} unidades al mes**. Hacer un pedido cuesta "
            f"**Q{S}**; cada unidad cuesta **Q{C}** y mantenerla en inventario cuesta el **{i} %** de su costo por "
            f"año. El proveedor tarda **{L} semana(s)** en entregar y se trabajan **300 días** al año "
            "(52 semanas)."
        )
    enunciado += "\n\nCalcula la cantidad económica de pedido, el número de pedidos por año y el punto de reorden."
    preguntas = [
        Pregunta(id="Q", etiqueta="Cantidad económica de pedido Q* (2 decimales)"),
        Pregunta(id="N", etiqueta="Número de pedidos por año (2 decimales)"),
        Pregunta(id="ROP", etiqueta="Punto de reorden R, en unidades (2 decimales)"),
    ]
    return Practica(modulo="eoq", dificultad=dificultad, semilla=0, titulo="Inventarios: EOQ", enunciado=enunciado,
                    datos=datos, preguntas=preguntas)


def _errores_eoq(datos: dict, sol: Resultado) -> dict[str, list[tuple[float, str]]]:
    """Valores que producen los errores típicos y la pista asociada."""
    D = sol.valores["D_anual"]
    S = datos["costo_pedido"]
    H = sol.valores["H"]
    dias = datos["dias_laborales_anio"]
    errores: dict[str, list[tuple[float, str]]] = {"Q": [], "N": [], "ROP": []}
    errores["Q"].append((math.sqrt(D * S / H), "Parece que olvidaste el factor 2 en Q* = √(2DS/H)."))
    errores["Q"].append((math.sqrt(2 * D * S / (H * H)), "Parece que dividiste entre H al cuadrado: la fórmula divide entre H una sola vez."))
    if datos["periodo_demanda"] != "anual":
        D_crudo = datos["demanda"]
        errores["Q"].append((math.sqrt(2 * D_crudo * S / H), "Convierte primero la demanda a **anual** (D = demanda mensual × 12)."))
    if datos["modo_mantener"] == "porcentaje":
        i = datos["porcentaje_mantener"]
        errores["Q"].append((math.sqrt(2 * D * S / i), "Recuerda que H = i·C: multiplica el porcentaje (como decimal) por el costo unitario."))
    Q = sol.valores["Q*"]
    errores["N"].append((Q / D, "Invertiste la fracción: N = D / Q*, no Q* / D."))
    if "ROP" in sol.valores:
        L = datos["plazo_entrega"]
        if datos["unidad_plazo"] == "dias":
            errores["ROP"].append((D * L, "Falta convertir la demanda anual a **diaria** (dividir entre los días laborales) antes de multiplicar por L."))
        else:
            errores["ROP"].append((D / dias * L, "El plazo está en semanas: conviértelo a días (× días laborales / 52) o usa la demanda semanal."))
            errores["ROP"].append((D * L, "Falta convertir la demanda y el plazo a la misma unidad (por ejemplo, demanda semanal × semanas)."))
    return errores


def _feedback_eoq(p: Practica, resp: dict, sol: Resultado) -> tuple[list[ItemFeedback], list[str]]:
    items, pistas = _items(p, resp, sol)
    errores = _errores_eoq(p.datos, sol)
    for item in items:
        if item.correcta or item.respuesta is None:
            continue
        for valor, pista in errores.get(item.id, []):
            if abs(item.respuesta - valor) <= max(0.01, 0.002 * abs(valor)):
                pistas.append(f"**{item.etiqueta.split(' (')[0]}:** {pista}")
                break
    return items, pistas


# --------------------------------------------------------------------------- #
# Corrección
# --------------------------------------------------------------------------- #
def _esperado(p: Practica, sol: Resultado, pid: str) -> float:
    if p.modulo == "pl":
        return _valor(sol, pid)
    if p.modulo == "transporte":
        if pid == "inicial":
            datos = DatosTransporte.model_validate(p.datos)
            return float(transporte.costo_solucion_inicial(datos))
        return _valor(sol, "Z")
    if p.modulo == "asignacion":
        if pid == "filas":
            return float(sum(min(f) for f in p.datos["costos"]))
        return _valor(sol, "Z")
    return _valor(sol, {"Q": "Q*", "N": "N", "ROP": "ROP"}[pid])


def _items(p: Practica, resp: dict, sol: Resultado) -> tuple[list[ItemFeedback], list[str]]:
    items = []
    for q in p.preguntas:
        r = resp.get(q.id)
        if r is None:
            items.append(ItemFeedback(id=q.id, etiqueta=q.etiqueta, respuesta=None, correcta=False,
                                      mensaje="Sin responder."))
            continue
        ok = _cerca(float(r), _esperado(p, sol, q.id))
        items.append(ItemFeedback(id=q.id, etiqueta=q.etiqueta, respuesta=float(r), correcta=ok,
                                  mensaje="¡Correcto!" if ok else "No coincide con el resultado esperado."))
    return items, []


_GENERADORES = {"pl": _generar_pl, "transporte": _generar_transporte, "asignacion": _generar_asignacion, "eoq": _generar_eoq}
_MOTORES = {"pl": simplex, "transporte": transporte, "asignacion": asignacion, "eoq": inventarios}
_FEEDBACK = {"pl": _feedback_pl, "transporte": _feedback_transporte, "asignacion": _feedback_asignacion, "eoq": _feedback_eoq}


def generar(modulo: str, dificultad: str = "facil", semilla: int | None = None) -> Practica:
    """Genera una práctica reproducible a partir de ``semilla`` (si no se da, se elige una)."""
    if modulo not in _GENERADORES:
        raise ValueError(f"Módulo desconocido: {modulo}")
    if dificultad not in DIFICULTADES:
        raise ValueError(f"Dificultad desconocida: {dificultad}")
    if semilla is None:
        semilla = random.SystemRandom().randint(1000, 999999)
    rng = random.Random(f"{modulo}-{dificultad}-{semilla}")
    practica = _GENERADORES[modulo](rng, dificultad)
    practica.semilla = semilla
    return practica


def resolver(practica: Practica) -> Resultado:
    """Solución completa del ejercicio (paso a paso) calculada por el motor."""
    return _MOTORES[practica.modulo].resolver_datos(practica.datos)


def evaluar(practica: Practica, respuestas: dict[str, float | None]) -> Retroalimentacion:
    """Corrige las respuestas del estudiante y devuelve retroalimentación."""
    solucion = resolver(practica)
    items, pistas = _FEEDBACK[practica.modulo](practica, respuestas, solucion)
    puntaje = sum(1 for i in items if i.correcta)
    total = len(items)
    if puntaje == total:
        resumen = f"¡Excelente! {puntaje} de {total} respuestas correctas."
    elif puntaje == 0:
        resumen = f"0 de {total} respuestas correctas. Revisa las pistas y vuelve a intentarlo."
    else:
        resumen = f"{puntaje} de {total} respuestas correctas. Revisa las pistas para corregir el resto."
    return Retroalimentacion(puntaje=puntaje, total=total, items=items, pistas=pistas, resumen=resumen,
                             solucion=solucion)
