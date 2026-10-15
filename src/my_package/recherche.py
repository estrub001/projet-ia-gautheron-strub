"""Recherche sémantique dans les mesures des programmes des candidats.

1. Chargement et nettoyage du CSV
2. Assemblage du texte à vectoriser
3. Embeddings en local avec sentence-transformers
4. Stockage dans ChromaDB
5. Fonction rechercher()
6. Tests dans le terminal
"""

import sys
from functools import lru_cache
from pathlib import Path

import chromadb
import pandas as pd
from sentence_transformers import SentenceTransformer

# src/my_package/recherche.py -> racine du projet = 2 dossiers au-dessus de my_package
RACINE = Path(__file__).resolve().parents[2]
CHEMIN_CSV = RACINE / "data" / "mesures_programmes_2022.csv"
CHEMIN_CHROMA = RACINE / "chroma_db"
NOM_COLLECTION = "mesures"
MODELE = "intfloat/multilingual-e5-base"

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

# Variantes -> nom unique (sert aussi pour le filtre de rechercher())
NOMS_CANDIDATS = {
    "Le Pen": "Marine Le Pen",
    "Mélenchon": "Jean-Luc Mélenchon",
    "Macron": "Emmanuel Macron",
}


# ---------------------------------------------------------------------------
# 1. Chargement et nettoyage
# ---------------------------------------------------------------------------
def charger_mesures(chemin: Path = CHEMIN_CSV) -> pd.DataFrame:
    """Charge le CSV et renvoie un DataFrame propre."""
    df = pd.read_csv(chemin, dtype=str, encoding="utf-8")

    df = df.rename(columns=lambda c: c.strip()).rename(columns=COLONNES)

    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].str.strip()

    df["candidat"] = (
        df["candidat"].str.replace(r"\s+", " ", regex=True).replace(NOMS_CANDIDATS)
    )

    df = df[(df["mesure"] != "") & (df["candidat"] != "")]
    df = df.drop_duplicates(subset=["candidat", "mesure"]).reset_index(drop=True)

    df["texte_embed"] = df.apply(construire_texte, axis=1)
    return df


# ---------------------------------------------------------------------------
# 2. Texte à vectoriser
# ---------------------------------------------------------------------------
def construire_texte(ligne: pd.Series) -> str:
    """Assemble le texte à vectoriser (le texte d'origine n'est pas modifié)."""
    theme = ligne["theme"]
    if ligne["theme_secondaire"]:
        theme += f", {ligne['theme_secondaire']}"
    return f"{theme}. {ligne['mesure']}"
#    return ligne["mesure"]
#    return f"Candidat : {ligne['candidat']}. Thème : {theme}. Mesure : {ligne['mesure']}"


# ---------------------------------------------------------------------------
# 3. Modèle d'embedding (chargé une seule fois)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_modele() -> SentenceTransformer:
    return SentenceTransformer(MODELE)


def embedder(textes: list[str], prefixe: str) -> list[list[float]]:
    """Le modèle e5 attend "passage: " pour les mesures et "query: " pour les questions."""
    vecteurs = get_modele().encode(
        [prefixe + t for t in textes],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=len(textes) > 1,
    )
    return vecteurs.tolist()


# ---------------------------------------------------------------------------
# 4. ChromaDB
# ---------------------------------------------------------------------------
def get_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=str(CHEMIN_CHROMA))


def get_collection():
    return get_client().get_or_create_collection(
        NOM_COLLECTION,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=None,  # on fournit nos propres vecteurs
    )


def indexer(df: pd.DataFrame, taille_paquet: int = 500) -> None:
    """(Re)construit la base vectorielle à partir du DataFrame."""
    client = get_client()
    if NOM_COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(NOM_COLLECTION)  # évite les doublons
    collection = get_collection()

    print(f"Calcul des embeddings pour {len(df)} mesures...")
    vecteurs = embedder(df["texte_embed"].tolist(), prefixe="passage: ")

    metadonnees = df[
        ["candidat", "theme", "theme_secondaire", "type_source", "source", "date"]
    ].to_dict(orient="records")

    for debut in range(0, len(df), taille_paquet):
        fin = debut + taille_paquet
        collection.add(
            ids=[f"mesure_{i}" for i in range(debut, min(fin, len(df)))],
            embeddings=vecteurs[debut:fin],
            documents=df["mesure"].iloc[debut:fin].tolist(),
            metadatas=metadonnees[debut:fin],
        )
    print(f"{collection.count()} mesures indexées dans {CHEMIN_CHROMA}")


# ---------------------------------------------------------------------------
# 5. Recherche
# ---------------------------------------------------------------------------
def rechercher(question: str, candidat: str | None = None, n: int = 5) -> list[dict]:
    """Renvoie les n mesures les plus proches de la question.

    Format de sortie (convenu avec Élise) : liste de dicts
    {"texte", "candidat", "theme", "source", "date", "score"}
    """
    collection = get_collection()
    if collection.count() == 0:
        indexer(charger_mesures())

    filtre = None
    if candidat:
        filtre = {"candidat": NOMS_CANDIDATS.get(candidat, candidat)}

    resultats = collection.query(
        query_embeddings=embedder([question], prefixe="query: "),
        n_results=n,
        where=filtre,
    )

    mesures = []
    for texte, meta, distance in zip(
        resultats["documents"][0],
        resultats["metadatas"][0],
        resultats["distances"][0],
    ):
        mesures.append(
            {
                "texte": texte,
                "candidat": meta["candidat"],
                "theme": meta["theme"],
                "source": meta["source"],
                "date": meta["date"],
                "score": round(1 - distance, 3),  # 1 = très proche
            }
        )
    return mesures


# ---------------------------------------------------------------------------
# 6. Tests rapides : uv run python -m my_package.recherche [--reindexer]
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--reindexer" in sys.argv or get_collection().count() == 0:
        indexer(charger_mesures())

    questions = [
        ("Que propose-t-on sur les éoliennes ?", None),
        ("Quel âge de départ à la retraite ?", None),
        ("Que veut faire Macron pour l'école ?", "Macron"),
        ("Quelles mesures pour baisser le prix de l'essence ?", "Le Pen"),
        ("Quelle est la recette de la tarte tatin ?", None),  # hors sujet
    ]

    for question, candidat in questions:
        filtre = f" [filtre : {candidat}]" if candidat else ""
        print(f"\n=== {question}{filtre}")
        for m in rechercher(question, candidat=candidat, n=3):
            print(f"  ({m['score']}) {m['candidat']} | {m['theme']} | {m['texte'][:110]}")