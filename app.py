#ici on importe rechercher et generer pour pouvoir créer l'app streamlite.

# app.py
import re

import streamlit as st

from my_package.generation import generer_reponse
from my_package.recherche import rechercher

# Noms écrits exactement comme dans la colonne "Candidat" du CSV
CANDIDATS = ["Emmanuel Macron", "Jean-Luc Mélenchon", "Marine Le Pen"]
# Mesures envoyées au modèle par candidat : plus il en voit, moins il risque de rater la bonne.
# Il n'en affiche ensuite que 2 maximum (voir MESURES_AFFICHEES_PAR_CANDIDAT dans generation.py)
MESURES_ENVOYEES_PAR_CANDIDAT = 4

# Source écrite entre crochets à la fin d'une ligne, ex. "... [projet-lecologie.pdf]"
# (le point final éventuel après le crochet est toléré, le modèle en met parfois un)
SOURCE_EN_FIN_DE_LIGNE = re.compile(r" ?\[([^\]]+)\]\.?$", re.MULTILINE)


def rechercher_candidats(question: str, candidats: list[str]) -> list[dict]:
    """Cherche les mesures des candidats sélectionnés, la plus pertinente en premier."""
    # Une recherche par candidat coché : chacun a le même nombre de mesures,
    # donc aucun candidat ne peut prendre toute la place
    mesures = []
    for candidat in candidats:
        mesures += rechercher(question, candidat=candidat, n=MESURES_ENVOYEES_PAR_CANDIDAT)
    return sorted(mesures, key=lambda m: m["score"], reverse=True)


def mettre_en_forme_sources(reponse: str) -> str:
    """Passe chaque source à la ligne, en italique et en petit, sous sa mesure."""
    return SOURCE_EN_FIN_DE_LIGNE.sub(
        r'  \n  <span style="font-size: 0.75em; opacity: 0.8;"><em>\1</em></span>',
        reponse,
    )


def afficher_filtre() -> list[str]:
    """Encadré de filtre façon e-commerce : une case par candidat, toutes cochées par défaut."""
    with st.container(border=True):
        st.markdown("**Candidats**")
        # La clé garde l'état de chaque case d'une recherche à l'autre
        return [c for c in CANDIDATS if st.checkbox(c, value=True, key=f"filtre_{c}")]


# Page large pour avoir de la place pour la colonne du filtre à gauche
st.set_page_config(page_title="Programmes 2022", layout="wide")

# Largeurs des 3 colonnes : filtre | contenu centré | vide (pour garder le contenu au centre)
LARGEURS = [1, 2, 1]

# Titre centré
st.markdown(
    "<h1 style='text-align: center;'>Programmes présidentielle 2022</h1>",
    unsafe_allow_html=True,
)

# 1re ligne : barre de recherche dans la colonne du milieu
_, centre, _ = st.columns(LARGEURS, gap="large")
with centre:
    question = st.text_input("Posez votre question")

# 2e ligne : filtre à gauche, sous la barre de recherche ; réponse au centre
gauche, centre, _ = st.columns(LARGEURS, gap="large")

# Le filtre n'apparaît qu'après la 1re recherche, puis reste affiché
if question:
    st.session_state["a_cherche"] = True

candidats_choisis = CANDIDATS
if st.session_state.get("a_cherche"):
    with gauche:
        candidats_choisis = afficher_filtre()

if question:
    with centre:
        if not candidats_choisis:
            st.warning("Cochez au moins un candidat.")
        else:
            # La 1re recherche est lente (chargement du modèle) : on affiche un message d'attente
            with st.spinner("Recherche dans les programmes..."):
                mesures = rechercher_candidats(question, candidats_choisis)
                # On passe les candidats cochés : un candidat sans aucune mesure trouvée
                # apparaît quand même, avec "aucune mesure"
                reponse = generer_reponse(question, mesures, candidats_choisis)
            # unsafe_allow_html : nécessaire pour la petite taille des sources
            st.markdown(mettre_en_forme_sources(reponse), unsafe_allow_html=True)
