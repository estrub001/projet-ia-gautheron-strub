"""Recherche sémantique dans les mesures des programmes des candidats.

1. Chargement et nettoyage du CSV
2. Assemblage du texte à vectoriser
3. Embeddings en local avec sentence-transformers
4. Stockage dans ChromaDB
5. Reranker : relit question et mesure ensemble pour reclasser les résultats
6. Fonction rechercher() : équilibre entre candidats + seuil de score
7. Tests dans le terminal
"""

import math
import sys
from functools import lru_cache
from pathlib import Path

import chromadb
import pandas as pd
from sentence_transformers import CrossEncoder, SentenceTransformer

from my_package.glossaire import enrichir

# src/my_package/recherche.py -> racine du projet = 2 dossiers au-dessus de my_package
RACINE = Path(__file__).resolve().parents[2]
CHEMIN_CSV = RACINE / "data" / "mesures_programmes_2022.csv"
CHEMIN_CHROMA = RACINE / "chroma_db"
NOM_COLLECTION = "mesures"

MODELE = "BAAI/bge-m3"
PREFIXE_PASSAGE = ""  # "passage: " pour e5, rien pour bge-m3
PREFIXE_QUESTION = ""  # "query: " pour e5, rien pour bge-m3
# MODELE = "intfloat/multilingual-e5-base"

# En dessous de ce score, une mesure est jugée hors sujet (valable pour bge-m3 :
# à recalibrer si on change de modèle, chaque modèle a sa propre échelle)
SCORE_MIN = 0.45

# --- Reranker ---
MODELE_RERANKER = "BAAI/bge-reranker-v2-m3"
RERANKER_ACTIF = True  # False = recherche par embeddings seule (version précédente)
N_AVANT_RERANK = 10  # mesures récupérées par candidat avant reclassement
# Filet plus large que SCORE_MIN : on laisse passer plus de mesures,
# c'est le reranker qui fait le tri ensuite
SCORE_MIN_AVANT_RERANK = 0.35
# Seuil sur le score du reranker (entre 0 et 1). None = pas de coupure.
# À calibrer avec test/evaluer.py (pire bonne réponse / meilleur hors sujet)
SEUIL_RERANK = None
# True = le reranker relit la mesure enrichie par le glossaire (à tester)
RERANK_AVEC_GLOSSAIRE = False

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
    return enrichir(ligne["mesure"])  # mesure + définition des sigles qu'elle contient
    # Versions testées :
    # return ligne["mesure"]
    # return f"{theme}. {ligne['mesure']}"
    # return f"Candidat : {ligne['candidat']}. Thème : {theme}. Mesure : {ligne['mesure']}"


# ---------------------------------------------------------------------------
# 3. Modèle d'embedding (chargé une seule fois)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_modele() -> SentenceTransformer:
    return SentenceTransformer(MODELE)


def embedder(textes: list[str], prefixe: str) -> list[list[float]]:
    """Transforme des textes en vecteurs (normalisés, pour la distance cosinus)."""
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
    vecteurs = embedder(df["texte_embed"].tolist(), prefixe=PREFIXE_PASSAGE)

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
    get_candidats.cache_clear()  # la liste des candidats a pu changer
    print(f"{collection.count()} mesures indexées dans {CHEMIN_CHROMA}")


@lru_cache(maxsize=1)
def get_candidats() -> tuple[str, ...]:
    """Liste des candidats présents dans la base (lue une seule fois)."""
    metas = get_collection().get(include=["metadatas"])["metadatas"]
    return tuple(sorted({m["candidat"] for m in metas}))


# ---------------------------------------------------------------------------
# 5. Reranker (chargé une seule fois)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_reranker() -> CrossEncoder:
    return CrossEncoder(MODELE_RERANKER, max_length=512)


def reclasser(question: str, mesures: list[dict]) -> list[dict]:
    """Donne à chaque mesure un score du reranker, qui lit question et mesure ensemble.

    Le score des embeddings est conservé dans "score_embedding" pour comparer,
    et "score" devient le score du reranker (entre 0 et 1, 1 = très pertinent).
    """
    if not mesures:
        return []
    paires = [
        (question, enrichir(m["mesure"]) if RERANK_AVEC_GLOSSAIRE else m["mesure"])
        for m in mesures
    ]
    scores = get_reranker().predict(paires, batch_size=16, show_progress_bar=False)
    for m, s in zip(mesures, scores):
        m["score_embedding"] = m["score"]
        m["score"] = round(float(s), 3)
    return mesures


# ---------------------------------------------------------------------------
# 6. Recherche
# ---------------------------------------------------------------------------
def _interroger(collection, vecteur, n: int, filtre: dict | None) -> list[dict]:
    """Une requête ChromaDB, mise au format de sortie."""
    resultats = collection.query(query_embeddings=[vecteur], n_results=n, where=filtre)
    mesures = []
    for texte, meta, distance in zip(
        resultats["documents"][0],
        resultats["metadatas"][0],
        resultats["distances"][0],
    ):
        mesures.append(
            {
                "mesure": texte,
                "candidat": meta["candidat"],
                "theme": meta["theme"],
                "theme_secondaire": meta["theme_secondaire"],
                "type_source": meta["type_source"],
                "source": meta["source"],
                "date": meta["date"],
                "score": round(1 - distance, 3),  # 1 = très proche
            }
        )
    return mesures


def _meilleures(mesures: list[dict], n: int) -> list[dict]:
    return sorted(mesures, key=lambda m: -m["score"])[:n]


def rechercher(
    question: str,
    candidat: str | None = None,
    n: int = 9,
    equilibrer: bool = True,
    score_min: float | None = SCORE_MIN,
    reranker: bool = RERANKER_ACTIF,
    seuil_rerank: float | None = SEUIL_RERANK,
) -> list[dict]:
    """Renvoie les mesures les plus pertinentes, de la plus pertinente à la moins pertinente.

    - candidat donné : les n meilleures mesures de ce candidat.
    - sans candidat et equilibrer=True : les meilleures mesures de CHAQUE candidat
      (n réparti entre eux, arrondi au-dessus : n=9 et 3 candidats -> 3 chacun),
      pour qu'aucun candidat ne disparaisse parce que son programme est plus court.
    - sans candidat et equilibrer=False : les n meilleures toutes confondues.

    Sans reranker : score = score des embeddings, filtré par score_min.
    Avec reranker : on récupère d'abord plus de mesures (N_AVANT_RERANK par candidat,
      filet SCORE_MIN_AVANT_RERANK), le reranker les reclasse, puis on garde les
      meilleures. score = score du reranker, filtré par seuil_rerank ;
      l'ancien score reste dans "score_embedding".

    La liste peut être vide : la question est alors hors sujet (décidé avec le score
    des embeddings : aucune mesure ne dépasse score_min, même avec le reranker).

    Format de sortie : liste de dicts
    {"mesure", "candidat", "theme", "theme_secondaire", "type_source",
     "source", "date", "score"} (+ "score_embedding" avec le reranker)
    """
    collection = get_collection()
    if collection.count() == 0:
        indexer(charger_mesures())
        collection = get_collection()  # la collection a été recréée par indexer()

    vecteur = embedder([question], prefixe=PREFIXE_QUESTION)[0]

    # Groupes de recherche : un par candidat (équilibre), ou un seul
    if candidat:
        groupes = [{"candidat": NOMS_CANDIDATS.get(candidat, candidat)}]
        n_par_groupe = n
    elif equilibrer:
        candidats = get_candidats()
        groupes = [{"candidat": nom} for nom in candidats]
        n_par_groupe = math.ceil(n / len(candidats))
    else:
        groupes = [None]
        n_par_groupe = n

    # 1. Récupération par embeddings (plus large si on reclasse ensuite)
    if reranker:
        n_recup = max(n_par_groupe, N_AVANT_RERANK * (1 if groupes[0] else len(get_candidats())))
        seuil_embedding = SCORE_MIN_AVANT_RERANK
    else:
        n_recup = n_par_groupe
        seuil_embedding = score_min

    par_groupe = []
    for filtre in groupes:
        mesures = _interroger(collection, vecteur, n_recup, filtre)
        if seuil_embedding is not None:
            mesures = [m for m in mesures if m["score"] >= seuil_embedding]
        par_groupe.append(mesures)

    # Hors sujet : on décide avec les embeddings (seuil SCORE_MIN), le reranker
    # ne sert qu'à reclasser. Si aucune mesure n'atteint le seuil, liste vide.
    meilleur_score = max((m["score"] for mesures in par_groupe for m in mesures), default=0)
    if reranker and score_min is not None and meilleur_score < score_min:
        return []

    # 2. Reclassement : un seul appel au reranker pour toutes les mesures (plus rapide)
    if reranker:
        reclasser(question, [m for mesures in par_groupe for m in mesures])
        if seuil_rerank is not None:
            par_groupe = [
                [m for m in mesures if m["score"] >= seuil_rerank]
                for mesures in par_groupe
            ]

    # 3. Les meilleures de chaque groupe
    resultats = []
    for mesures in par_groupe:
        resultats += _meilleures(mesures, n_par_groupe)

    return sorted(resultats, key=lambda m: -m["score"])


# ---------------------------------------------------------------------------
# 7. Tests rapides : uv run python -m my_package.recherche [--reindexer] [--sans-reranker]
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--reindexer" in sys.argv or get_collection().count() == 0:
        indexer(charger_mesures())

    avec_reranker = "--sans-reranker" not in sys.argv

    questions = [
        ("Que propose-t-on sur les éoliennes ?", None),
        ("Quel âge de départ à la retraite ?", None),
        ("Que veut faire Macron pour l'école ?", "Macron"),
        ("Quelles mesures pour baisser le prix de l'essence ?", "Le Pen"),
        ("Quels candidats veulent taxer davantage les riches ?", None),
        ("Quelle est la recette de la tarte tatin ?", None),  # hors sujet
    ]

    for question, candidat in questions:
        filtre = f" [filtre : {candidat}]" if candidat else ""
        print(f"\n=== {question}{filtre}")
        resultats = rechercher(question, candidat=candidat, reranker=avec_reranker)
        if not resultats:
            print("  (aucune mesure au-dessus du seuil : hors sujet)")
        for m in resultats:
            embed = f" / emb {m['score_embedding']}" if "score_embedding" in m else ""
            print(
                f"  ({m['score']}{embed}) {m['candidat']} | {m['theme']} | {m['mesure'][:100]}"
            )