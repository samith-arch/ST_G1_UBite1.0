# calendario academico 2026 de la cafeteria: lo usa el ETL para la dimension fecha
from datetime import date

INICIOS_SEMESTRE = (date(2026, 2, 2), date(2026, 8, 31))

FESTIVOS = {date(2026, 1, 1), date(2026, 1, 12), date(2026, 3, 23), date(2026, 4, 2), date(2026, 4, 3),
            date(2026, 5, 1), date(2026, 5, 18), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 29),
            date(2026, 7, 20), date(2026, 8, 7), date(2026, 8, 17), date(2026, 10, 12), date(2026, 11, 2),
            date(2026, 11, 16), date(2026, 12, 8), date(2026, 12, 25)}

# (desde, hasta, periodo); lo que no cae en ninguno es "clases" o "vacaciones"
PERIODOS = [
    (date(2026, 3, 16), date(2026, 3, 21), "parciales"),
    (date(2026, 3, 30), date(2026, 4, 4), "semana santa"),
    (date(2026, 5, 25), date(2026, 5, 30), "finales"),
    (date(2026, 6, 15), date(2026, 8, 29), "intersemestral"),
    (date(2026, 9, 21), date(2026, 9, 26), "parciales"),
    (date(2026, 11, 23), date(2026, 11, 28), "finales"),
]
FIN_CLASES = (date(2026, 6, 13), date(2026, 12, 5))


def periodo(dia):
    for desde, hasta, nombre in PERIODOS:
        if desde <= dia <= hasta:
            return nombre
    for inicio, fin in zip(INICIOS_SEMESTRE, FIN_CLASES):
        if inicio <= dia <= fin:
            return "clases"
    return "vacaciones"


def semana_semestre(dia):
    # 1 en la primera semana de clases; 0 si el dia no esta dentro de un semestre
    for inicio, fin in zip(INICIOS_SEMESTRE, FIN_CLASES):
        if inicio <= dia <= fin:
            return (dia - inicio).days // 7 + 1
    return 0