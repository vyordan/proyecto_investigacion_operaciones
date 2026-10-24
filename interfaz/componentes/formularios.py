"""Formularios de entrada de cada módulo. Devuelven ``dict`` listos para el motor.

Los formularios no validan: solo arman el diccionario. La validación (y los
mensajes de error en español) la hace ``core.validador``.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

SIGNOS = ["≤", "≥", "="]


# --------------------------------------------------------------------------- #
# Programación lineal (gráfico y simplex)
# --------------------------------------------------------------------------- #
def _nombres_por_defecto(n: int) -> list[str]:
    return ["x", "y"] if n == 2 else [f"x{i}" for i in range(1, n + 1)]


def _pad(valores: list, n: int) -> list:
    """Recorta o completa con celdas vacías (NaN) hasta tener n valores."""
    valores = list(valores)[:n]
    return valores + [float("nan")] * (n - len(valores))


def cargar_ejemplo_pl(clave: str, ejemplo: dict) -> None:
    """Callback: carga un ejemplo y reinicia los editores (cambia la versión de sus claves)."""
    st.session_state[f"{clave}_base"] = ejemplo
    st.session_state[f"{clave}_ver"] = st.session_state.get(f"{clave}_ver", 0) + 1


def formulario_pl(clave: str, con_descripciones: bool = False) -> dict:
    ver = st.session_state.setdefault(f"{clave}_ver", 0)
    base = st.session_state.get(f"{clave}_base") or {
        "objetivo": "max", "coef_objetivo": [float("nan")] * 2, "restricciones": [{}, {}],
    }

    c1, c2, c3 = st.columns([1.3, 1, 1])
    objetivo = c1.radio(
        "Objetivo", ["Maximizar", "Minimizar"], horizontal=True,
        index=0 if base.get("objetivo", "max") == "max" else 1, key=f"{clave}_obj_{ver}",
    )
    n = int(c2.number_input("Variables", 1, 10, value=len(base["coef_objetivo"]), key=f"{clave}_n_{ver}"))
    m = int(c3.number_input("Restricciones", 1, 15, value=len(base["restricciones"]), key=f"{clave}_m_{ver}"))

    nombres_base = base.get("nombres_variables")
    nombres_ini = nombres_base if nombres_base and len(nombres_base) == n else _nombres_por_defecto(n)
    texto_nombres = st.text_input(
        "Nombres de las variables (separados por coma)", value=", ".join(nombres_ini),
        key=f"{clave}_nom_{ver}_{n}",
    )
    nombres = [s.strip() for s in texto_nombres.split(",") if s.strip()]
    etiquetas = nombres if len(nombres) == n and len(set(nombres)) == n else _nombres_por_defecto(n)
    descripciones = None
    if con_descripciones:
        desc_base = base.get("descripciones_variables") or []
        texto_desc = st.text_input(
            "¿Qué representa cada variable? (separadas por coma, mismo orden)",
            value=", ".join(desc_base) if len(desc_base) == n else "", key=f"{clave}_desc_{ver}_{n}",
            placeholder="p. ej., Unidades de mesas, Unidades de sillas",
        )
        descripciones = [s.strip() for s in texto_desc.split(",") if s.strip()] or None

    cols = {f"c{i}": st.column_config.NumberColumn(etiquetas[i], format="%g", required=False) for i in range(n)}

    st.markdown("**Función objetivo**  \nCoeficiente de cada variable en Z.")
    df_obj = pd.DataFrame([_pad(base["coef_objetivo"], n)], columns=[f"c{i}" for i in range(n)], index=["Z"])
    obj_editado = st.data_editor(df_obj, column_config=cols, key=f"{clave}_objtab_{ver}_{n}", width="stretch")

    st.markdown("**Restricciones**  \nCoeficientes, signo y lado derecho (LD) de cada restricción.")
    filas = []
    for i in range(m):
        r = base["restricciones"][i] if i < len(base["restricciones"]) else {}
        signo = {"<=": "≤", ">=": "≥", "=": "="}.get(r.get("signo", "<="), "≤")
        filas.append(_pad(r.get("coeficientes", []), n) + [signo, r.get("rhs", float("nan"))])
    df_res = pd.DataFrame(filas, columns=[f"c{i}" for i in range(n)] + ["signo", "ld"],
                          index=[f"R{i + 1}" for i in range(m)])
    cols_res = dict(cols)
    cols_res["signo"] = st.column_config.SelectboxColumn("Signo", options=SIGNOS, required=True)
    cols_res["ld"] = st.column_config.NumberColumn("LD", format="%g", required=False)
    res_editado = st.data_editor(df_res, column_config=cols_res, key=f"{clave}_restab_{ver}_{n}_{m}",
                                 width="stretch")

    restricciones = []
    for _, fila in res_editado.iterrows():
        restricciones.append(
            {
                "coeficientes": [_num(fila[f"c{i}"]) for i in range(n)],
                "signo": fila["signo"],
                "rhs": _num(fila["ld"]),
                "nombre": (base["restricciones"][len(restricciones)].get("nombre", "")
                           if len(restricciones) < len(base["restricciones"]) else ""),
            }
        )
    return {
        "titulo": base.get("titulo", "Problema de programación lineal"),
        "objetivo": "max" if objetivo == "Maximizar" else "min",
        "coef_objetivo": [_num(obj_editado.iloc[0][f"c{i}"]) for i in range(n)],
        "restricciones": restricciones,
        "nombres_variables": nombres,
        "descripciones_variables": descripciones,
    }


def _num(v) -> float:
    return float("nan") if v is None or pd.isna(v) else float(v)


# --------------------------------------------------------------------------- #
# Inventarios (EOQ)
# --------------------------------------------------------------------------- #
_PERIODOS = {"Anual": "anual", "Mensual": "mensual", "Semanal": "semanal", "Diaria": "diario"}
_UNIDADES_PLAZO = {"Días": "dias", "Semanas": "semanas", "Meses": "meses"}
_MODOS = {"Valor por unidad y por año (H)": "unitario", "Porcentaje del costo unitario (i)": "porcentaje"}


def _f(v):
    return None if v is None else float(v)


def cargar_ejemplo_eoq(ejemplo: dict) -> None:
    """Callback o función previa al formulario: coloca en los campos los valores de un ejemplo o de la IA.

    Solo se rellenan los datos presentes; los que faltan quedan vacíos.
    """
    inv_periodo = {v: k for k, v in _PERIODOS.items()}
    inv_unidad = {v: k for k, v in _UNIDADES_PLAZO.items()}
    inv_modo = {v: k for k, v in _MODOS.items()}
    s = st.session_state
    s["eoq_articulo"] = ejemplo.get("nombre_articulo", "")
    s["eoq_demanda"] = _f(ejemplo.get("demanda"))
    s["eoq_periodo"] = inv_periodo.get(ejemplo.get("periodo_demanda", "anual"), "Anual")
    s["eoq_S"] = _f(ejemplo.get("costo_pedido"))
    s["eoq_modo"] = inv_modo.get(ejemplo.get("modo_mantener", "unitario"), list(_MODOS)[0])
    s["eoq_H"] = _f(ejemplo.get("costo_mantener"))
    s["eoq_i"] = _f(ejemplo.get("porcentaje_mantener"))
    s["eoq_C"] = _f(ejemplo.get("costo_unitario"))
    s["eoq_L"] = _f(ejemplo.get("plazo_entrega"))
    s["eoq_unidad"] = inv_unidad.get(ejemplo.get("unidad_plazo", "dias"), "Días")
    s["eoq_dias"] = int(ejemplo.get("dias_laborales_anio") or 365)
    s["eoq_ss"] = float(ejemplo.get("stock_seguridad") or 0)


def formulario_eoq() -> dict:
    articulo = st.text_input("Artículo (opcional)", key="eoq_articulo", placeholder="p. ej., cajas de tornillos")

    c1, c2 = st.columns(2)
    demanda = c1.number_input("Demanda (D)", min_value=0.0, value=None, key="eoq_demanda", placeholder="Ingresa D")
    periodo = c2.selectbox("Período de la demanda", list(_PERIODOS), key="eoq_periodo")

    S = st.number_input("Costo de hacer un pedido (S)", min_value=0.0, value=None, key="eoq_S",
                        placeholder="Costo por pedido")

    modo = st.radio("Costo de mantener inventario", list(_MODOS), horizontal=True, key="eoq_modo")
    H = i = C = None
    if _MODOS[modo] == "unitario":
        H = st.number_input("Costo de mantener una unidad por año (H)", min_value=0.0, value=None, key="eoq_H")
        C = st.number_input("Costo unitario del artículo (C) — opcional, para el costo total con compra",
                            min_value=0.0, value=None, key="eoq_C")
    else:
        d1, d2 = st.columns(2)
        i = d1.number_input("Porcentaje de mantener (i, en %)", min_value=0.0, value=None, key="eoq_i")
        C = d2.number_input("Costo unitario del artículo (C)", min_value=0.0, value=None, key="eoq_C")

    st.markdown("**Punto de reorden** (opcional)")
    e1, e2, e3 = st.columns(3)
    L = e1.number_input("Plazo de entrega (L)", min_value=0.0, value=None, key="eoq_L")
    unidad = e2.selectbox("Unidad del plazo", list(_UNIDADES_PLAZO), key="eoq_unidad")
    st.session_state.setdefault("eoq_ss", 0.0)  # valores iniciales vía session_state (evita el aviso de Streamlit)
    st.session_state.setdefault("eoq_dias", 365)
    ss = e3.number_input("Stock de seguridad", min_value=0.0, key="eoq_ss")
    dias = st.number_input("Días laborales al año", min_value=1, max_value=366, step=1, key="eoq_dias")

    datos = {
        "nombre_articulo": articulo,
        "demanda": demanda,
        "periodo_demanda": _PERIODOS[periodo],
        "costo_pedido": S,
        "modo_mantener": _MODOS[modo],
        "costo_mantener": H,
        "porcentaje_mantener": i,
        "costo_unitario": C,
        "plazo_entrega": L,
        "unidad_plazo": _UNIDADES_PLAZO[unidad],
        "dias_laborales_anio": int(dias),
        "stock_seguridad": ss,
    }
    # Los campos vacíos se omiten: así el validador responde «Falta el dato …».
    return {k: v for k, v in datos.items() if v is not None and v != ""}


# --------------------------------------------------------------------------- #
# Transporte y asignación
# --------------------------------------------------------------------------- #
cargar_ejemplo = cargar_ejemplo_pl  # mismo mecanismo: guarda el ejemplo y cambia la versión de los editores

_METODOS_INICIALES = {
    "Aproximación de Vogel": "vogel",
    "Costo mínimo": "costo_minimo",
    "Esquina noroeste": "esquina_noroeste",
}


def _lista_nombres(texto: str) -> list[str]:
    return [s.strip() for s in texto.split(",") if s.strip()]


def _cabeceras(nombres: list[str], n: int, prefijo: str) -> list[str]:
    """Nombres para mostrar en las tablas (si no son utilizables, se usan los genéricos)."""
    if len(nombres) == n and len(set(nombres)) == n:
        return nombres
    return [f"{prefijo}{i + 1}" for i in range(n)]


def _matriz_base(base: dict, clave: str, m: int, n: int) -> list[list[float]]:
    original = base.get(clave) or []
    return [_pad(original[i] if i < len(original) else [], n) for i in range(m)]


def formulario_transporte(clave: str) -> dict:
    ver = st.session_state.setdefault(f"{clave}_ver", 0)
    base = st.session_state.get(f"{clave}_base") or {
        "objetivo": "min", "oferta": [float("nan")] * 2, "demanda": [float("nan")] * 2, "costos": [[], []],
    }

    c1, c2 = st.columns(2)
    objetivo = c1.radio("Objetivo", ["Minimizar costo", "Maximizar beneficio"], horizontal=True,
                        index=0 if base.get("objetivo", "min") == "min" else 1, key=f"{clave}_obj_{ver}")
    metodo = c2.selectbox("Método para la solución inicial", list(_METODOS_INICIALES),
                          index=list(_METODOS_INICIALES.values()).index(base.get("metodo_inicial", "vogel")),
                          key=f"{clave}_met_{ver}")

    c3, c4 = st.columns(2)
    m = int(c3.number_input("Orígenes", 1, 8, value=len(base["oferta"]), key=f"{clave}_m_{ver}"))
    n = int(c4.number_input("Destinos", 1, 8, value=len(base["demanda"]), key=f"{clave}_n_{ver}"))

    ini_o = base.get("nombres_origenes")
    ini_d = base.get("nombres_destinos")
    ini_o = ini_o if ini_o and len(ini_o) == m else [f"O{i + 1}" for i in range(m)]
    ini_d = ini_d if ini_d and len(ini_d) == n else [f"D{j + 1}" for j in range(n)]
    n1, n2 = st.columns(2)
    txt_o = n1.text_input("Nombres de los orígenes (separados por coma)", value=", ".join(ini_o),
                          key=f"{clave}_no_{ver}_{m}")
    txt_d = n2.text_input("Nombres de los destinos (separados por coma)", value=", ".join(ini_d),
                          key=f"{clave}_nd_{ver}_{n}")
    nom_o, nom_d = _lista_nombres(txt_o), _lista_nombres(txt_d)
    et_o, et_d = _cabeceras(nom_o, m, "O"), _cabeceras(nom_d, n, "D")

    st.markdown("**Costos unitarios y oferta**  \nCosto de enviar una unidad de cada origen a cada destino, y la oferta de cada origen.")
    costos_ini = _matriz_base(base, "costos", m, n)
    oferta_ini = _pad(base["oferta"], m)
    df = pd.DataFrame(
        [costos_ini[i] + [oferta_ini[i]] for i in range(m)],
        columns=[f"d{j}" for j in range(n)] + ["oferta"], index=et_o,
    )
    cols = {f"d{j}": st.column_config.NumberColumn(et_d[j], format="%g", required=False) for j in range(n)}
    cols["oferta"] = st.column_config.NumberColumn("Oferta", format="%g", required=False)
    editado = st.data_editor(df, column_config=cols, key=f"{clave}_costos_{ver}_{m}_{n}", width="stretch")

    st.markdown("**Demanda**  \nUnidades que requiere cada destino.")
    df_dem = pd.DataFrame([_pad(base["demanda"], n)], columns=[f"d{j}" for j in range(n)], index=["Demanda"])
    cols_dem = {f"d{j}": st.column_config.NumberColumn(et_d[j], format="%g", required=False) for j in range(n)}
    dem_editada = st.data_editor(df_dem, column_config=cols_dem, key=f"{clave}_dem_{ver}_{n}", width="stretch")

    return {
        "titulo": base.get("titulo", "Problema de transporte"),
        "objetivo": "min" if objetivo.startswith("Min") else "max",
        "metodo_inicial": _METODOS_INICIALES[metodo],
        "oferta": [_num(editado.iloc[i]["oferta"]) for i in range(m)],
        "demanda": [_num(dem_editada.iloc[0][f"d{j}"]) for j in range(n)],
        "costos": [[_num(editado.iloc[i][f"d{j}"]) for j in range(n)] for i in range(m)],
        "nombres_origenes": nom_o,
        "nombres_destinos": nom_d,
    }


def formulario_asignacion(clave: str) -> dict:
    ver = st.session_state.setdefault(f"{clave}_ver", 0)
    base = st.session_state.get(f"{clave}_base") or {"objetivo": "min", "costos": [[], []]}
    costos_base = base.get("costos") or [[], []]

    c1, c2, c3 = st.columns([1.4, 1, 1])
    objetivo = c1.radio("Objetivo", ["Minimizar costo", "Maximizar beneficio"], horizontal=True,
                        index=0 if base.get("objetivo", "min") == "min" else 1, key=f"{clave}_obj_{ver}")
    m = int(c2.number_input("Filas (agentes)", 1, 10, value=len(costos_base), key=f"{clave}_m_{ver}"))
    n = int(c3.number_input("Columnas (tareas)", 1, 10, value=max(len(f) for f in costos_base) or 2,
                            key=f"{clave}_n_{ver}"))

    ini_f = base.get("nombres_filas")
    ini_c = base.get("nombres_columnas")
    ini_f = ini_f if ini_f and len(ini_f) == m else [f"A{i + 1}" for i in range(m)]
    ini_c = ini_c if ini_c and len(ini_c) == n else [f"T{j + 1}" for j in range(n)]
    n1, n2 = st.columns(2)
    txt_f = n1.text_input("Nombres de las filas (separados por coma)", value=", ".join(ini_f), key=f"{clave}_nf_{ver}_{m}")
    txt_c = n2.text_input("Nombres de las columnas (separados por coma)", value=", ".join(ini_c), key=f"{clave}_nc_{ver}_{n}")
    nom_f, nom_c = _lista_nombres(txt_f), _lista_nombres(txt_c)
    et_f, et_c = _cabeceras(nom_f, m, "A"), _cabeceras(nom_c, n, "T")

    st.markdown("**Matriz de costos**  \nCosto (o beneficio) de asignar cada fila a cada columna.")
    df = pd.DataFrame(_matriz_base(base, "costos", m, n), columns=[f"c{j}" for j in range(n)], index=et_f)
    cols = {f"c{j}": st.column_config.NumberColumn(et_c[j], format="%g", required=False) for j in range(n)}
    editado = st.data_editor(df, column_config=cols, key=f"{clave}_mat_{ver}_{m}_{n}", width="stretch")

    return {
        "titulo": base.get("titulo", "Problema de asignación"),
        "objetivo": "min" if objetivo.startswith("Min") else "max",
        "costos": [[_num(editado.iloc[i][f"c{j}"]) for j in range(n)] for i in range(m)],
        "nombres_filas": nom_f,
        "nombres_columnas": nom_c,
    }
