"""Inventarios: cantidad económica de pedido (EOQ) y punto de reorden.

Fórmulas:
    Q* = sqrt(2·D·S / H)           cantidad económica de pedido
    N  = D / Q*                    pedidos por año
    T  = Q* / D                    tiempo entre pedidos (años)
    CT = (D/Q)·S + (Q/2)·H [+ D·C] costo total anual
    R  = d·L [+ SS]               punto de reorden (d = D / días laborales)
"""
from __future__ import annotations

import math
from fractions import Fraction

from core.esquemas import DatosEOQ
from core.formato import a_fraccion, decimal, latex, texto
from core.resultado import Estado, Figura, Paso, Resultado, Tabla
from core.validador import ejecutar

_PERIODOS = {"anual": 1, "mensual": 12, "semanal": 52}
_NOMBRE_PERIODO = {"anual": "anual", "mensual": "mensual", "semanal": "semanal", "diario": "diaria"}


def _d(x: float, dec: int = 2) -> str:
    """Decimal para explicaciones."""
    return decimal(x, dec)


def _costo_total(D: Fraction, S: Fraction, H: Fraction, q: float) -> float:
    return float(D) / q * float(S) + q / 2 * float(H)


def resolver(d: DatosEOQ) -> Resultado:
    res = Resultado(modulo="inventarios", estado=Estado.OPTIMO, titulo="Inventarios: EOQ y punto de reorden")
    dias = d.dias_laborales_anio
    articulo = d.nombre_articulo.strip()
    de_articulo = f" de {articulo}" if articulo else ""

    # ---- 1. Demanda anual -------------------------------------------------
    D_ingresada = a_fraccion(d.demanda)
    if d.periodo_demanda == "anual":
        D = D_ingresada
        res.pasos.append(
            Paso(
                titulo="Datos del problema",
                explicacion="La demanda ya está expresada por año, así que no hace falta convertirla.",
                resultado=f"D = {latex(D)}\\ \\text{{unidades/año}}",
            )
        )
    else:
        if d.periodo_demanda == "diario":
            k = Fraction(dias)
            explic = f"La demanda es diaria; se multiplica por los {dias} días laborales del año."
        else:
            k = Fraction(_PERIODOS[d.periodo_demanda])
            explic = f"La demanda es {d.periodo_demanda}; se convierte a demanda anual multiplicando por {k}."
        D = D_ingresada * k
        res.pasos.append(
            Paso(
                titulo="Conversión de la demanda a demanda anual",
                explicacion=explic,
                formula=r"D = D_{\text{" + _NOMBRE_PERIODO[d.periodo_demanda] + r"}} \cdot k",
                sustitucion=f"D = {latex(D_ingresada)} \\cdot {latex(k)}",
                resultado=f"D = {latex(D)}\\ \\text{{unidades/año}}",
            )
        )

    S = a_fraccion(d.costo_pedido)

    # ---- 2. Costo de mantener --------------------------------------------
    if d.modo_mantener == "porcentaje":
        i = a_fraccion(d.porcentaje_mantener) / 100
        C = a_fraccion(d.costo_unitario)
        H = i * C
        res.pasos.append(
            Paso(
                titulo="Costo de mantener una unidad por año (H)",
                explicacion="El costo de mantener se obtiene como un porcentaje del costo unitario del artículo.",
                formula=r"H = i \cdot C",
                sustitucion=f"H = {latex(i)} \\cdot {latex(C)}",
                resultado=f"H = {latex(H)}",
            )
        )
    else:
        H = a_fraccion(d.costo_mantener)
        C = a_fraccion(d.costo_unitario) if d.costo_unitario is not None else None

    if d.porcentaje_mantener is not None and d.modo_mantener == "porcentaje" and d.porcentaje_mantener > 100:
        res.advertir("El porcentaje de costo de mantener es mayor que 100 %; revisa que esté expresado en %.")
    if C is not None and H > C and d.modo_mantener == "unitario":
        res.advertir("El costo de mantener por unidad es mayor que el costo unitario; verifica los datos.")

    # ---- 3. EOQ ----------------------------------------------------------
    radicando = 2 * D * S / H
    q = math.sqrt(float(radicando))
    Df, Sf, Hf = float(D), float(S), float(H)
    res.pasos.append(
        Paso(
            titulo="Cantidad económica de pedido (EOQ)",
            explicacion="Es la cantidad que minimiza la suma del costo de ordenar y el costo de mantener.",
            formula=r"Q^{*} = \sqrt{\dfrac{2\,D\,S}{H}}",
            sustitucion=f"Q^{{*}} = \\sqrt{{\\dfrac{{2 \\cdot {latex(D)} \\cdot {latex(S)}}}{{{latex(H)}}}}}",
            resultado=f"Q^{{*}} = \\sqrt{{{_d(float(radicando), 4)}}} \\approx {_d(q)}\\ \\text{{unidades}}",
        )
    )

    # ---- 4. Redondeo a unidades enteras ----------------------------------
    pedido_practico = q
    if abs(q - round(q)) > 1e-9 and math.floor(q) >= 1:
        candidatos = [("Q* (teórico)", q), ("Entero inferior", float(math.floor(q))), ("Entero superior", float(math.ceil(q)))]
        costos = [_costo_total(D, S, H, c) for _, c in candidatos]
        mejor = 1 if costos[1] <= costos[2] else 2
        pedido_practico = candidatos[mejor][1]
        res.pasos.append(
            Paso(
                titulo="Redondeo a unidades enteras",
                explicacion=(
                    "Como no se pueden pedir fracciones de unidad, se comparan los enteros vecinos de Q*. "
                    f"Conviene pedir **{_d(pedido_practico, 0)}** unidades (menor costo anual de ordenar y mantener)."
                ),
                formula=r"CT(Q) = \dfrac{D}{Q}\,S + \dfrac{Q}{2}\,H",
                tabla=Tabla(
                    columnas=["Opción", "Q", "CT(Q)"],
                    filas=[[nom, _d(c), _d(ct)] for (nom, c), ct in zip(candidatos, costos)],
                    filas_resaltadas=[mejor],
                    notas="CT(Q) incluye solo costo de ordenar y de mantener.",
                ),
            )
        )

    # ---- 5. Pedidos por año y tiempo de ciclo -----------------------------
    N = Df / q
    T_anios = q / Df
    T_dias = T_anios * dias
    res.pasos.append(
        Paso(
            titulo="Número de pedidos y tiempo entre pedidos",
            formula=r"N = \dfrac{D}{Q^{*}} \qquad T = \dfrac{Q^{*}}{D}\cdot \text{días laborales}",
            sustitucion=f"N = \\dfrac{{{latex(D)}}}{{{_d(q)}}} \\qquad T = \\dfrac{{{_d(q)}}}{{{latex(D)}}} \\cdot {dias}",
            resultado=f"N \\approx {_d(N)}\\ \\text{{pedidos/año}} \\qquad T \\approx {_d(T_dias)}\\ \\text{{días}}",
        )
    )

    # ---- 6. Costo total anual ---------------------------------------------
    costo_pedidos = Df / q * Sf
    costo_mantener = q / 2 * Hf
    CT = costo_pedidos + costo_mantener
    sust = f"CT = \\dfrac{{{latex(D)}}}{{{_d(q)}}}\\cdot {latex(S)} + \\dfrac{{{_d(q)}}}{{2}}\\cdot {latex(H)}"
    formula = r"CT = \dfrac{D}{Q^{*}}\,S + \dfrac{Q^{*}}{2}\,H"
    CT_total = CT
    if C is not None:
        CT_total = CT + Df * float(C)
        formula += r" + D\,C"
        sust += f" + {latex(D)}\\cdot {latex(C)}"
    res.pasos.append(
        Paso(
            titulo="Costo total anual",
            explicacion=(
                f"En el óptimo el costo anual de ordenar ({_d(costo_pedidos)}) "
                f"es igual al costo anual de mantener ({_d(costo_mantener)})."
            ),
            formula=formula,
            sustitucion=sust,
            resultado=f"CT \\approx {_d(CT_total)}",
        )
    )

    # ---- 7. Punto de reorden -----------------------------------------------
    rop = None
    L_dias = None
    ss = float(a_fraccion(d.stock_seguridad))
    if d.plazo_entrega is None:
        res.advertir(
            "No se calculó el punto de reorden porque falta el plazo de entrega (L).", nivel="aviso"
        )
    else:
        L = a_fraccion(d.plazo_entrega)
        if d.unidad_plazo == "dias":
            L_dias_f = L
            conv = "El plazo ya está en días."
        elif d.unidad_plazo == "semanas":
            L_dias_f = L * Fraction(dias, 52)
            conv = f"Las semanas se pasan a días laborales: {dias}/52 días por semana."
        else:
            L_dias_f = L * Fraction(dias, 12)
            conv = f"Los meses se pasan a días laborales: {dias}/12 días por mes."
        L_dias = float(L_dias_f)
        d_diaria = Df / dias
        rop = d_diaria * L_dias + ss
        formula = r"d = \dfrac{D}{\text{días laborales}} \qquad R = d \cdot L"
        sust = f"d = \\dfrac{{{latex(D)}}}{{{dias}}} \\qquad R = {_d(d_diaria, 4)} \\cdot {_d(L_dias)}"
        if ss > 0:
            formula += r" + SS"
            sust += f" + {_d(ss)}"
        res.pasos.append(
            Paso(
                titulo="Punto de reorden (R)",
                explicacion=(
                    f"{conv} El punto de reorden es la demanda durante el plazo de entrega"
                    + (" más el stock de seguridad." if ss > 0 else ".")
                    + f" Se pide un nuevo lote cuando el inventario baja a **{_d(rop)}** unidades "
                    f"(≈ {math.ceil(rop - 1e-9)} si se redondea hacia arriba)."
                ),
                formula=formula,
                sustitucion=sust,
                resultado=f"R \\approx {_d(rop)}\\ \\text{{unidades}}",
            )
        )
        if rop > q + ss + 1e-9:
            res.advertir(
                f"El punto de reorden ({_d(rop)}) supera la cantidad pedida ({_d(q)}): el plazo de entrega "
                "es mayor que el tiempo entre pedidos, así que habrá pedidos en tránsito. En ese caso R "
                "debe interpretarse sobre la posición de inventario (existencias + pedidos pendientes)."
            )

    # ---- Figuras -------------------------------------------------------------
    pasos_q = 60
    qs = [q * (0.2 + 2.3 * k / (pasos_q - 1)) for k in range(pasos_q)]
    res.figuras.append(
        Figura(
            tipo="curva_costos",
            titulo="Costos anuales según el tamaño de pedido",
            datos={
                "q": qs,
                "costo_pedido": [Df / x * Sf for x in qs],
                "costo_mantener": [x / 2 * Hf for x in qs],
                "costo_total": [_costo_total(D, S, H, x) for x in qs],
                "q_optimo": q,
                "ct_optimo": CT,
            },
        )
    )
    res.figuras.append(
        Figura(
            tipo="diente_sierra",
            titulo="Nivel de inventario en el tiempo",
            datos={
                "q": q,
                "t_ciclo_dias": T_dias,
                "rop": rop,
                "plazo_dias": L_dias,
                "stock_seguridad": ss,
                "ciclos": 3,
            },
        )
    )

    # ---- Resultado final -------------------------------------------------------
    res.fijar("D_anual", D)
    res.fijar("H", H)
    res.fijar("Q*", q)
    res.fijar("Q_practico", pedido_practico)
    res.fijar("N", N)
    res.fijar("T_dias", T_dias)
    res.fijar("CT", CT_total)
    if rop is not None:
        res.fijar("ROP", rop)

    resumen = f"Q* ≈ {_d(q)} unidades por pedido"
    if rop is not None:
        resumen += f"; punto de reorden R ≈ {_d(rop)} unidades"
    res.resumen = resumen + "."
    interpretacion = (
        f"Conviene pedir unas {_d(pedido_practico, 0)} unidades{de_articulo} cada vez, "
        f"lo que equivale a {_d(N)} pedidos al año (uno cada {_d(T_dias, 1)} días laborales aprox.). "
        f"El costo anual de ordenar y mantener es de {_d(CT)}."
    )
    if rop is not None:
        interpretacion += f" Cuando el inventario baje a {_d(rop)} unidades hay que emitir el siguiente pedido."
    res.interpretacion = interpretacion
    return res


def resolver_datos(datos) -> Resultado:
    """Valida y calcula; nunca lanza excepciones (ver ``core.validador.ejecutar``)."""
    return ejecutar(DatosEOQ, datos, resolver, "inventarios", "Inventarios: EOQ y punto de reorden")
