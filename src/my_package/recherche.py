"""Recherche sémantique dans les mesures des programmes des candidats.

Étapes 1 et 2 : chargement, nettoyage du CSV et assemblage du texte à vectoriser.
"""

from pathlib import Path

import pandas as pd

# src/my_package/recherche.py -> racine du projet = 2 dossiers au-dessus de my_package
RACINE = Path(__file__).resolve().parents[2]
CHEMIN_CSV = RACINE / "data" / "mesures_programmes_2022.csv"

# Noms de colonnes du CSV -> noms simples, sans accents ni espaces
COLONNES = {
    "Thème": "theme",
    "Thème secondaire": "theme_secondaire",
    "Candidat": "candidat",
    "Mesure": "mesure",
    "Type de source": "type_source",
    "Source": "source",
    "Date": "date",
}

# Variantes d'orthographe -> nom unique.
# À compléter en regardant le value_counts() des candidats.
NOMS_CANDIDATS = {
    "Le Pen": "Marine Le Pen",
    "Mélenchon": "Jean-Luc Mélenchon",
}


def charger_mesures(chemin: Path = CHEMIN_CSV) -> pd.DataFrame:
    """Charge le CSV et renvoie un DataFrame propre."""
    df = pd.read_csv(chemin, dtype=str, encoding="utf-8")

    # Colonnes bien nommées
    df = df.rename(columns=lambda c: c.strip()).rename(columns=COLONNES)

    # Cases vides -> "" et espaces en trop retirés partout
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].str.strip()

    # Noms de candidats uniformes (espaces multiples, variantes)
    df["candidat"] = (
        df["candidat"].str.replace(r"\s+", " ", regex=True).replace(NOMS_CANDIDATS)
    )

    # Pas de lignes vides ou incomplètes, pas de doublons
    df = df[(df["mesure"] != "") & (df["candidat"] != "")]
    df = df.drop_duplicates(subset=["candidat", "mesure"]).reset_index(drop=True)

    return df


def construire_texte(ligne: pd.Series) -> str:
    """Assemble le texte à vectoriser (le texte d'origine n'est pas modifié)."""
    theme = ligne["theme"]
    if ligne["theme_secondaire"]:
        theme += f", {ligne['theme_secondaire']}"
    return f"Candidat : {ligne['candidat']}. Thème : {theme}. Mesure : {ligne['mesure']}"


if __name__ == "__main__":
    df = charger_mesures()
    df["texte_embed"] = df.apply(construire_texte, axis=1)

    print("Taille :", df.shape)
    print("\nCandidats :\n", df["candidat"].value_counts())
    print("\nThèmes :\n", df["theme"].value_counts())
    print("\nExemple de texte :\n", df["texte_embed"].iloc[0])