"""Modelación de programación lineal y utilidades compartidas.

Contiene lo que necesitan en común el método gráfico y el simplex:
presentación del modelo (variables, función objetivo, restricciones),
verificación de restricciones y la interpretación de la solución óptima
(generada por plantilla en Python: la IA nunca escribe resultados).
"""
from __future__ import annotations

from fractions import Fraction

from core.esquemas import ProblemaPL
from core.formato import (
    SIGNO_LATEX,
    SIGNO_TEXTO,
    a_fraccion,
    expresion_latex,
    latex,
    lista_es,
    texto,
    var_latex,
)
from core.resultado import Estado, Paso, Resultado, Tabla
from core.validador import ejecutar


def coeficientes_objetivo(p: ProblemaPL) -> list[Fraction]:
    return [a_fraccion(c) for c in p.coef_objetivo]


def valor_objetivo(p: ProblemaPL, x: list[Fraction]) -> Fraction:
    return sum((c * xi for c, xi in zip(coeficientes_objetivo(p), x)), Fraction(0))


def lineas_modelo(p: ProblemaPL) -> list[str]:
    """Líneas LaTeX del modelo: objetivo, restricciones y no negatividad."""
    nombres = p.variables
    opt = r"\max" if p.objetivo == "max" else r"\min"
    lineas = [f"{opt}\\; Z = {expresion_latex(p.coef_objetivo, nombres)}", r"\text{sujeto a:}"]
    for r in p.restricciones:
        lineas.append(f"{expresion_latex(r.coeficientes, nombres)} {SIGNO_LATEX[r.signo]} {latex(r.rhs)}")
    lineas.append(", ".join(var_latex(v) for v in nombres) + r" \geq 0")
    return lineas


def paso_modelo(p: ProblemaPL) -> Paso:
    """Paso 'Modelo': identifica variables, función objetivo y restricciones."""
    nombres = p.variables
    partes = []
    if p.descripciones_variables:
        partes.append("**Variables de decisión:**")
        for nom, desc in zip(nombres, p.descripciones_variables):
            partes.append(f"- `{nom}`: {desc}")
    else:
        partes.append("**Variables de decisión:** " + ", ".join(f"`{v}`" for v in nombres) + ".")
    objetivo = "maximizar" if p.objetivo == "max" else "minimizar"
    partes.append(f"**Función objetivo:** {objetivo} Z.")
    partes.append(f"**Restricciones:** {p.m}, además de la no negatividad de las variables.")
    return Paso(titulo="Modelo del problema", explicacion="\n".join(partes), lineas=lineas_modelo(p))


def evaluar_restricciones(p: ProblemaPL, x: list[Fraction]) -> list[tuple[Fraction, Fraction, bool]]:
    """Para cada restricción: (lado izquierdo, holgura/exceso, ¿cumple?)."""
    salida = []
    for r in p.restricciones:
        lhs = sum((a_fraccion(c) * xi for c, xi in zip(r.coeficientes, x)), Fraction(0))
        rhs = a_fraccion(r.rhs)
        if r.signo == "<=":
            holgura = rhs - lhs
        elif r.signo == ">=":
            holgura = lhs - rhs
        else:
            holgura = lhs - rhs
        cumple = holgura == 0 if r.signo == "=" else holgura >= 0
        salida.append((lhs, holgura, cumple))
    return salida


def tabla_restricciones(p: ProblemaPL, x: list[Fraction]) -> Tabla:
    """Tabla de verificación de la solución en cada restricción."""
    filas = []
    for i, (lhs, holgura, cumple) in enumerate(evaluar_restricciones(p, x)):
        r = p.restricciones[i]
        if not cumple:
            estado = "No se cumple"
        elif holgura == 0:
            estado = "Activa (igualdad)"
        else:
            estado = "Con holgura" if r.signo == "<=" else "Con exceso"
        filas.append(
            [
                p.etiqueta_restriccion(i),
                texto(lhs),
                SIGNO_TEXTO[r.signo],
                texto(a_fraccion(r.rhs)),
                texto(holgura) if r.signo != "=" else "0",
                estado,
            ]
        )
    return Tabla(
        titulo="Verificación de la solución en las restricciones",
        columnas=["Restricción", "Lado izquierdo", "Signo", "Lado derecho", "Holgura / exceso", "Estado"],
        filas=filas,
    )


def interpretar(p: ProblemaPL, x: list[Fraction], z: Fraction) -> str:
    """Interpretación de la solución óptima en lenguaje del problema."""
    nombres = p.variables
    solucion = ", ".join(f"{nom} = {texto(v)}" for nom, v in zip(nombres, x))
    tipo = "máximo" if p.objetivo == "max" else "mínimo"
    partes = [f"La solución óptima es {solucion}, con un valor {tipo} de Z = {texto(z)}."]

    if p.descripciones_variables:
        detalle = "; ".join(
            f"{desc}: {texto(v)}" for desc, v in zip(p.descripciones_variables, x)
        )
        partes.append(f"En términos del problema: {detalle}.")

    activas, con_holgura = [], []
    for i, (_, holgura, cumple) in enumerate(evaluar_restricciones(p, x)):
        etiqueta = p.etiqueta_restriccion(i)
        if cumple and holgura == 0:
            activas.append(etiqueta)
        elif cumple:
            if p.restricciones[i].signo == "<=":
                con_holgura.append(f"{etiqueta} (sobran {texto(holgura)})")
            else:
                con_holgura.append(f"{etiqueta} (se excede en {texto(holgura)})")
    if activas:
        verbo = "se cumple" if len(activas) == 1 else "se cumplen"
        partes.append(f"Con igualdad {verbo} {lista_es(activas)}: están activas y limitan la solución.")
    if con_holgura:
        partes.append(f"Con margen: {lista_es(con_holgura)}.")
    return " ".join(partes)


def formular(p: ProblemaPL) -> Resultado:
    """Módulo de modelación: presenta variables, función objetivo y restricciones."""
    res = Resultado(modulo="modelacion", estado=Estado.OPTIMO, titulo="Modelación del problema")
    res.pasos.append(paso_modelo(p))
    tipo = "maximizar" if p.objetivo == "max" else "minimizar"
    res.resumen = f"Modelo formulado: {p.n} variable(s), función objetivo a {tipo} y {p.m} restricción(es)."
    return res


def formular_datos(datos) -> Resultado:
    """Valida y formula el modelo; nunca lanza excepciones."""
    return ejecutar(ProblemaPL, datos, formular, "modelacion", "Modelación del problema")
