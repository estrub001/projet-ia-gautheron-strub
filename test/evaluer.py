"""Évalue rechercher() sur les questions de test/questions.csv.

Lancement depuis la racine du projet :
    uv run python test/evaluer.py
    uv run python test/evaluer.py -v   (les 5 résultats de chaque question)

Format de questions.csv :
    question, candidat_filtre, fragments_attendus, candidats_attendus
    - fragments_attendus : un fragment par bonne mesure, séparés par "|"
    - candidats_attendus : les candidats qui ont une position, séparés par "|"
    - les deux vides = question hors sujet

Mesures calculées :
    - Top N       : au moins une bonne mesure dans les N premiers résultats
    - 1re position et MRR : rang de la première bonne mesure
    - Rappel@N    : part des bonnes mesures retrouvées (sur max N attendues)
    - Couverture  : part des candidats concernés présents dans le top N
                    (questions où plusieurs candidats ont une position)
    - Hors sujet  : meilleur score obtenu, pour choisir un seuil
"""

import sys
from pathlib import Path

import pandas as pd

from my_package.recherche import rechercher

CHEMIN_QUESTIONS = Path(__file__).resolve().parent / "questions.csv"
N = 5
VERBEUX = "-v" in sys.argv


def decouper(valeur: str) -> list[str]:
    """'a|b|c' -> ['a', 'b', 'c'] (sans les morceaux vides)."""
    return [x.strip() for x in valeur.split("|") if x.strip()]


def fragments_trouves(mesure: dict, fragments: list[str]) -> list[str]:
    """Fragments attendus présents dans le texte de cette mesure."""
    texte = mesure["mesure"].lower()
    return [f for f in fragments if f.lower() in texte]


def afficher_resultats(resultats: list[dict], fragments: list[str]) -> None:
    """Affiche les résultats ; les bonnes mesures sont marquées d'une flèche."""
    for rang, m in enumerate(resultats, start=1):
        fleche = "->" if fragments_trouves(m, fragments) else "  "
        print(f"  {fleche} {rang}. ({m['score']}) {m['candidat']} | {m['mesure'][:90]}")


def main() -> None:
    df = pd.read_csv(CHEMIN_QUESTIONS, dtype=str, encoding="utf-8-sig").fillna("")

    nb_attendues, trouves = 0, 0
    rangs, scores_bons, rappels, couvertures = [], [], [], []
    hors_sujet, rates = [], []

    for _, q in df.iterrows():
        question = q["question"].strip()
        if not question:
            continue
        candidat = q["candidat_filtre"].strip() or None
        fragments = decouper(q["fragments_attendus"])
        candidats = decouper(q["candidats_attendus"])

        resultats = rechercher(question, candidat=candidat, n=N)

        # --- Question hors sujet : on note le meilleur score
        if not fragments:
            meilleur = resultats[0]["score"] if resultats else 0
            hors_sujet.append((question, meilleur))
            if VERBEUX:
                print(f"\n[HORS SUJET] {question} -> meilleur score {meilleur}")
                afficher_resultats(resultats, [])
            continue

        nb_attendues += 1

        # Rang de la première bonne mesure + fragments retrouvés
        rang, retrouves = None, set()
        for i, m in enumerate(resultats, start=1):
            f = fragments_trouves(m, fragments)
            if f:
                retrouves.update(f)
                if rang is None:
                    rang = i
                    scores_bons.append(m["score"])

        if rang:
            trouves += 1
            rangs.append(rang)
        else:
            rates.append((question, resultats, fragments))

        # Rappel : sur au plus N mesures attendues (le top N ne peut pas en contenir plus)
        rappel = len(retrouves) / min(len(fragments), N)
        rappels.append(rappel)

        # Couverture des candidats : seulement quand plusieurs candidats ont une position
        couverture = None
        if len(candidats) > 1 and not candidat:
            presents = {m["candidat"] for m in resultats if fragments_trouves(m, fragments)}
            couverture = len(presents & set(candidats)) / len(candidats)
            couvertures.append(couverture)

        if VERBEUX:
            statut = f"OK rang {rang}" if rang else "RATÉ"
            filtre = f" [filtre : {candidat}]" if candidat else ""
            details = f"rappel {len(retrouves)}/{min(len(fragments), N)}"
            if couverture is not None:
                details += f", candidats {couverture:.0%}"
            print(f"\n[{statut} | {details}] {question}{filtre}")
            afficher_resultats(resultats, fragments)

    # --- Résumé
    print("\n" + "=" * 60)
    print(f"Au moins une bonne mesure dans le top {N} : {trouves}/{nb_attendues}")
    print(f"Bonne mesure en 1re position : {rangs.count(1)}/{nb_attendues}")
    print(f"MRR (1 = toujours premier) : {sum(1 / r for r in rangs) / nb_attendues:.2f}")
    print(f"Rappel@{N} moyen (part des bonnes mesures retrouvées) : {sum(rappels) / len(rappels):.0%}")
    if couvertures:
        print(
            f"Couverture candidats ({len(couvertures)} questions à plusieurs candidats) : "
            f"{sum(couvertures) / len(couvertures):.0%}"
        )
    if scores_bons:
        print(
            f"Score de la 1re bonne mesure : min {min(scores_bons)}, "
            f"moyen {sum(scores_bons) / len(scores_bons):.3f}"
        )
    if hors_sujet:
        print("\nHors sujet (meilleur score, du plus haut au plus bas) :")
        for question, score in sorted(hors_sujet, key=lambda x: -x[1]):
            print(f"  ({score}) {question}")

    if rates and not VERBEUX:
        print("\nQuestions ratées (relancer avec -v pour tout voir) :")
        for question, resultats, fragments in rates:
            print(f"\n  {question}")
            afficher_resultats(resultats[:3], fragments)


if __name__ == "__main__":
    main()