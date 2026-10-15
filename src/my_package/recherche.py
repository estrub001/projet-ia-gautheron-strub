"""Recherche des mesures les plus pertinentes pour une question."""

K_MAX = 9               # nombre maximum de mesures renvoyées
MAX_PAR_CANDIDAT = 3    # nombre maximum de mesures par candidat

# Correspondance entre les colonnes du CSV et les clés utilisées dans le code
COLONNES = {
    "Thème": "theme",
    "Thème secondaire": "theme_secondaire",
    "Candidat": "candidat",
    "Mesure": "mesure",
    "Type de source": "type_source",
    "Source": "source",
    "Date": "date",
}


def rechercher(question: str, candidat: str | None = None) -> list[dict]:
    """
    Renvoie au maximum 9 mesures, dont 3 au maximum par candidat,
    la plus pertinente en premier.

    question : la question du citoyen, telle quelle.
    candidat : filtre optionnel, orthographe identique à la colonne 'Candidat' du CSV
               (ex. "Marine Le Pen"). Si un candidat est choisi, 3 mesures au maximum.

    Renvoie [] si rien ne correspond.
    Chaque élément est un dictionnaire :
        {"theme", "theme_secondaire", "candidat", "mesure",
         "type_source", "source", "date", "score"}
    theme_secondaire vaut "" s'il n'y en a pas.
    score : entre 0 et 1, plus c'est grand plus c'est pertinent.
    """
    # VERSION TEMPORAIRE : fausses données, remplacées plus tard par la recherche ChromaDB
    resultats = [
        {"theme": "Energie", "theme_secondaire": "Ecologie et climat",
         "candidat": "Marine Le Pen",
         "mesure": "Prononcer un moratoire sur l'éolien et le solaire...",
         "type_source": "Programme officiel",
         "source": "projet-lecologie.pdf ; projet-le-patrimoine.pdf",
         "date": "2022", "score": 0.91},
        {"theme": "Energie", "theme_secondaire": "",
         "candidat": "Marine Le Pen",
         "mesure": "Développer l'hydroélectricité et la géothermie...",
         "type_source": "Programme officiel", "source": "projet-lecologie.pdf",
         "date": "2022", "score": 0.85},
        {"theme": "Energie", "theme_secondaire": "",
         "candidat": "Candidat fictif",
         "mesure": "Mesure fictive sur l'énergie",
         "type_source": "Site web", "source": "https://exemple.fr",
         "date": "2022", "score": 0.80},
    ]
    if candidat:
        resultats = [r for r in resultats if r["candidat"] == candidat]
    return limiter_par_candidat(resultats)


def limiter_par_candidat(resultats: list[dict]) -> list[dict]:
    """
    Garde au maximum MAX_PAR_CANDIDAT mesures par candidat et K_MAX au total.
    Les résultats doivent arriver déjà triés du plus pertinent au moins pertinent.
    """
    compteur = {}
    gardes = []
    for r in resultats:
        nb = compteur.get(r["candidat"], 0)
        if nb < MAX_PAR_CANDIDAT:
            gardes.append(r)
            compteur[r["candidat"]] = nb + 1
        if len(gardes) == K_MAX:
            break
    return gardes