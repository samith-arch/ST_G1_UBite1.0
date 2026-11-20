# tarea de cada noche: carga lo del dia en el almacen y deja lista la estimacion del
# siguiente dia para Power BI. Los domingos ademas vuelve a entrenar la red.
#
#   python bi/cierre_diario.py              lo que hace la tarea programada
#   python bi/cierre_diario.py --entrenar   fuerza el entrenamiento completo
import os
import subprocess
import sys
from datetime import date, datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IA = os.path.join(RAIZ, "ia")
LOG = os.path.join(RAIZ, "bi", "cierre_diario.log")


def buscar_python(carpeta, nombres):
    # el python del entorno virtual de esa carpeta; si no hay, el que este corriendo este script
    for nombre in nombres:
        for ruta in (os.path.join(carpeta, nombre, "Scripts", "python.exe"), os.path.join(carpeta, nombre, "bin", "python")):
            if os.path.exists(ruta):
                return ruta
    return sys.executable


def python_app():
    return buscar_python(RAIZ, ("venv", ".venv", "env"))


def python_ia():
    # la red usa su propio entorno (TensorFlow)
    return buscar_python(IA, (".venv", "venv", "env"))


def anotar(texto):
    linea = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {texto}"
    print(linea)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def paso(nombre, comando, carpeta):
    anotar(f"inicia {nombre}")
    r = subprocess.run(comando, cwd=carpeta, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "TF_CPP_MIN_LOG_LEVEL": "3", "PYTHONIOENCODING": "utf-8"})
    salida = [l for l in (r.stdout + r.stderr).splitlines()
              if l.strip() and not any(x in l for x in ("WARNING", "oneDNN", "I0000", "W0000"))]
    for l in salida[-4:]:
        anotar(f"   {l.strip()}")
    if r.returncode != 0:
        anotar(f"FALLÓ {nombre} (código {r.returncode})")
        sys.exit(r.returncode)


if __name__ == "__main__":
    entrenar = "--entrenar" in sys.argv or date.today().weekday() == 6
    anotar(f"python de la app: {python_app()} | python de la IA: {python_ia()}")
    paso("ETL", [python_app(), "-m", "flask", "--app", "run", "etl"], RAIZ)
    if entrenar:
        paso("entrenamiento semanal", [python_ia(), "entrenar_modelo.py"], IA)
    else:
        paso("predicción del siguiente día", [python_ia(), "entrenar_modelo.py", "--solo-predecir"], IA)
    anotar("cierre terminado")
