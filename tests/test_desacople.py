"""El motor (core/ y algoritmos/) no debe depender de la interfaz ni de librerías pesadas."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROHIBIDOS = {"streamlit", "matplotlib", "scipy", "pulp", "google", "pandas", "numpy"}


def _importaciones(ruta: Path) -> set[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(a.name.split(".")[0] for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            nombres.add(nodo.module.split(".")[0])
    return nombres


def test_motor_no_importa_interfaz_ni_librerias_pesadas():
    for carpeta in ("core", "algoritmos"):
        for archivo in (RAIZ / carpeta).glob("*.py"):
            usados = _importaciones(archivo) & PROHIBIDOS
            assert not usados, f"{archivo.relative_to(RAIZ)} importa {sorted(usados)}"


def test_motor_no_importa_interfaz_propia():
    for carpeta in ("core", "algoritmos"):
        for archivo in (RAIZ / carpeta).glob("*.py"):
            usados = _importaciones(archivo) & {"interfaz", "llm", "main"}
            assert not usados, f"{archivo.relative_to(RAIZ)} importa {sorted(usados)}"
