"""Punto de entrada para Streamlit Cloud."""
import sys
from pathlib import Path

# Asegura que la raíz del repo esté en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from interfaz.app import main  # ajusta el nombre si tu archivo no es interfaz/app.py

if __name__ == "__main__":
    main()