from pathlib import Path

import pandas as pd

# Racine du projet : src/my_package/donnees.py -> remonte de 3 niveaux
RACINE = Path(__file__).resolve().parents[2]
CHEMIN_MESURES = RACINE / "data" / "mesures_programmes_2022.csv"

COLONNES = {
    "Thème": "theme",
    "Thème secondaire": "theme_secondaire",
    "Candidat": "candidat",
    "Mesure": "mesure",
    "Type de source": "type_source",
    "Source": "source",
    "Date": "date",
}


def charger_mesures(chemin: Path = CHEMIN_MESURES) -> pd.DataFrame:
    """Charge le tableur des mesures des programmes 2022."""
    df = pd.read_csv(chemin, encoding="utf-8")
    df = df.rename(columns=COLONNES)
    df["theme_secondaire"] = df["theme_secondaire"].fillna("")
    return df


if __name__ == "__main__":
    mesures = charger_mesures()
    print(f"{len(mesures)} mesures chargées")
    print(mesures["candidat"].value_counts())
