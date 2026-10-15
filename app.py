#ici on importe rechercher et generer pour pouvoir créer l'app streamlite.

# app.py
from my_package.generation import generer_reponse
from my_package.recherche import rechercher

import streamlit as st

st.title("Programmes présidentielle 2022")

question = st.text_input("Posez votre question")

if question:
    mesures = rechercher(question)
    reponse = generer_reponse(question, mesures)
    st.markdown(reponse)
