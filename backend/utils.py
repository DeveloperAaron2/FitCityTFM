"""
utils.py — Lógica compartida de niveles y títulos.
Importar desde cualquier router para evitar duplicación.
"""

XP_PER_LEVEL = 5000  # XP necesario para subir de nivel (umbral por nivel)

# Mapa nivel → título
_TITLES = {
    1: "Principiante", 2: "Aprendiz",  3: "Atleta",
    4: "Guerrero",     5: "Campeón",   6: "Élite",
    7: "Maestro",      8: "Gran Maestro", 9: "Leyenda", 10: "FitGod",
}


def compute_level(total_xp: int) -> int:
    """Devuelve el nivel a partir del XP total."""
    return (total_xp // XP_PER_LEVEL) + 1


def get_title(level: int) -> str:
    bucket = min((level - 1) // 3 + 1, 10)
    return _TITLES.get(bucket, "FitMaster")


def level_info(total_xp: int) -> dict:
    """
    Devuelve level, max_xp y title.
    - total_xp: siempre se muestra tal cual en la UI.
    - max_xp: umbral de XP total para subir al siguiente nivel.
    - level: nivel actual del usuario.
    """
    lv = compute_level(total_xp)
    return {
        "level": lv,
        "max_xp": XP_PER_LEVEL * lv,   # XP total necesario para alcanzar el nivel siguiente
        "title": get_title(lv),
    }
