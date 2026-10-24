"""Ejercicios de ejemplo (solo DATOS DE ENTRADA).

Las respuestas nunca están escritas aquí: el motor resuelve cada ejemplo al
cargarlo (requisito 3 del enunciado). 12 ejemplos repartidos por módulo.
"""

RUBRICA = {
    "titulo": "Maximización (ejemplo de prueba)",
    "objetivo": "max",
    "coef_objetivo": [40, 30],
    "nombres_variables": ["x", "y"],
    "restricciones": [
        {"coeficientes": [2, 1], "signo": "<=", "rhs": 100},
        {"coeficientes": [1, 2], "signo": "<=", "rhs": 80},
    ],
}

DIETA = {
    "titulo": "Minimización con restricciones ≥ (dos fases)",
    "objetivo": "min",
    "coef_objetivo": [3, 2],
    "nombres_variables": ["x", "y"],
    "restricciones": [
        {"coeficientes": [1, 1], "signo": ">=", "rhs": 4},
        {"coeficientes": [1, 3], "signo": ">=", "rhs": 6},
    ],
}

MEZCLA = {
    "titulo": "Tres variables (simplex)",
    "objetivo": "max",
    "coef_objetivo": [5, 4, 3],
    "nombres_variables": ["x1", "x2", "x3"],
    "restricciones": [
        {"coeficientes": [2, 3, 1], "signo": "<=", "rhs": 5},
        {"coeficientes": [4, 1, 2], "signo": "<=", "rhs": 11},
        {"coeficientes": [3, 4, 2], "signo": "<=", "rhs": 8},
    ],
}

ALTERNATIVOS = {
    "titulo": "Óptimos alternativos (infinitas soluciones)",
    "objetivo": "max",
    "coef_objetivo": [1, 1],
    "nombres_variables": ["x", "y"],
    "restricciones": [
        {"coeficientes": [1, 1], "signo": "<=", "rhs": 4},
        {"coeficientes": [1, 0], "signo": "<=", "rhs": 3},
    ],
}

NO_ACOTADO = {
    "titulo": "Problema no acotado",
    "objetivo": "max",
    "coef_objetivo": [1, 1],
    "nombres_variables": ["x", "y"],
    "restricciones": [
        {"coeficientes": [1, -1], "signo": "<=", "rhs": 2},
    ],
}

EOQ_BASE = {
    "titulo": "EOQ y punto de reorden",
    "nombre_articulo": "unidades",
    "demanda": 1000,
    "periodo_demanda": "anual",
    "costo_pedido": 10,
    "modo_mantener": "unitario",
    "costo_mantener": 2.5,
    "plazo_entrega": 7,
    "unidad_plazo": "dias",
    "dias_laborales_anio": 365,
    "stock_seguridad": 0,
}

EOQ_MENSUAL = {
    "titulo": "EOQ con demanda mensual, costo de mantener en % y plazo en semanas",
    "nombre_articulo": "cajas",
    "demanda": 150,
    "periodo_demanda": "mensual",
    "costo_pedido": 45,
    "modo_mantener": "porcentaje",
    "porcentaje_mantener": 25,
    "costo_unitario": 12,
    "plazo_entrega": 2,
    "unidad_plazo": "semanas",
    "dias_laborales_anio": 365,
    "stock_seguridad": 20,
}

TRANSPORTE_BALANCEADO = {
    "titulo": "Transporte balanceado (3 plantas, 4 ciudades)",
    "objetivo": "min",
    "metodo_inicial": "vogel",
    "nombres_origenes": ["Planta A", "Planta B", "Planta C"],
    "nombres_destinos": ["Ciudad 1", "Ciudad 2", "Ciudad 3", "Ciudad 4"],
    "oferta": [20, 30, 25],
    "demanda": [10, 15, 20, 30],
    "costos": [[8, 6, 10, 9], [9, 12, 13, 7], [14, 9, 16, 5]],
}

TRANSPORTE_DESBALANCEADO = {
    "titulo": "Transporte desbalanceado (oferta mayor que demanda)",
    "objetivo": "min",
    "metodo_inicial": "costo_minimo",
    "nombres_origenes": ["Bodega 1", "Bodega 2"],
    "nombres_destinos": ["Tienda 1", "Tienda 2", "Tienda 3"],
    "oferta": [40, 50],
    "demanda": [20, 25, 30],
    "costos": [[4, 6, 8], [5, 3, 7]],
}

TRANSPORTE_MAXIMIZAR = {
    "titulo": "Transporte maximizando beneficio",
    "objetivo": "max",
    "metodo_inicial": "esquina_noroeste",
    "oferta": [30, 20],
    "demanda": [25, 25],
    "costos": [[10, 6], [7, 9]],
}

ASIGNACION_CUADRADA = {
    "titulo": "Asignación 4×4 (minimizar costo)",
    "objetivo": "min",
    "nombres_filas": ["Ana", "Beto", "Carla", "Diego"],
    "nombres_columnas": ["Tarea 1", "Tarea 2", "Tarea 3", "Tarea 4"],
    "costos": [[9, 2, 7, 8], [6, 4, 3, 7], [5, 8, 1, 8], [7, 6, 9, 4]],
}

ASIGNACION_NO_CUADRADA = {
    "titulo": "Asignación 2×3 (matriz no cuadrada)",
    "objetivo": "min",
    "nombres_filas": ["Operario 1", "Operario 2"],
    "nombres_columnas": ["Máquina A", "Máquina B", "Máquina C"],
    "costos": [[4, 2, 8], [3, 5, 6]],
}

EJEMPLOS = {
    "pl": [RUBRICA, DIETA, MEZCLA, ALTERNATIVOS, NO_ACOTADO],
    "eoq": [EOQ_BASE, EOQ_MENSUAL],
    "transporte": [TRANSPORTE_BALANCEADO, TRANSPORTE_DESBALANCEADO, TRANSPORTE_MAXIMIZAR],
    "asignacion": [ASIGNACION_CUADRADA, ASIGNACION_NO_CUADRADA],
}

TOTAL_EJEMPLOS = sum(len(v) for v in EJEMPLOS.values())
