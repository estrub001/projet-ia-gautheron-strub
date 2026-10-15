"""Évalue rechercher() sur les questions de test/questions.csv.

Lancement depuis la racine du projet :
    uv run python test/evaluer.py
    uv run python test/evaluer.py -v   (détail de chaque question)

Pour chaque question avec une réponse attendue, on regarde si une mesure
contenant un des fragments attendus sort dans le top N, et à quel rang.
Pour les questions hors sujet, on affiche le meilleur score obtenu
(utile pour choisir un éventuel seuil).
"""

import sys
from pathlib import Path

import pandas as pd

from my_package.recherche import rechercher

CHEMIN_QUESTIONS = Path(__file__).resolve().parent / "questions.csv"
N = 5
VERBEUX = "-v" in sys.argv


def trouver_rang(resultats: list[dict], fragments: list[str]) -> int | None:
    """Rang (1 = premier) de la première mesure contenant un fragment attendu."""
    for rang, mesure in enumerate(resultats, start=1):
        texte = mesure["texte"].lower()
        if any(f.lower() in texte for f in fragments):
            return rang
    return None


def main() -> None:
    df = pd.read_csv(CHEMIN_QUESTIONS, dtype=str).fillna("")

    trouves, rangs, scores_bons, scores_hors_sujet = 0, [], [], []
    rates = []
    nb_attendues = 0

    for _, q in df.iterrows():
        question = q["question"].strip()
        if not question:
            continue
        candidat = q["candidat_filtre"].strip() or None
        fragments = [f.strip() for f in q["fragments_attendus"].split("|") if f.strip()]

        resultats = rechercher(question, candidat=candidat, n=N)

        # Question hors sujet : on note juste le meilleur score
        if not fragments:
            meilleur = resultats[0]["score"] if resultats else 0
            scores_hors_sujet.append(meilleur)
            if VERBEUX:
                print(f"[HORS SUJET] {question} -> meilleur score {meilleur}")
            continue

        nb_attendues += 1
        rang = trouver_rang(resultats, fragments)
        if rang:
            trouves += 1
            rangs.append(rang)
            scores_bons.append(resultats[rang - 1]["score"])
            statut = f"OK (rang {rang})"
        else:
            rates.append((question, resultats))
            statut = "RATÉ"

        if VERBEUX:
            print(f"[{statut}] {question}")

    # Résumé
    print("\n" + "=" * 60)
    print(f"Bonne mesure dans le top {N} : {trouves}/{nb_attendues}")
    if rangs:
        print(f"Bonne mesure en 1re position : {rangs.count(1)}/{nb_attendues}")
        mrr = sum(1 / r for r in rangs) / nb_attendues
        print(f"MRR (1 = toujours premier) : {mrr:.2f}")
    if scores_bons:
        print(f"Score des bonnes mesures : min {min(scores_bons)}, moyen {sum(scores_bons) / len(scores_bons):.3f}")
    if scores_hors_sujet:
        print(f"Meilleur score hors sujet : max {max(scores_hors_sujet)}")

    if rates:
        print("\nQuestions ratées (top 3 obtenu) :")
        for question, resultats in rates:
            print(f"\n  {question}")
            for m in resultats[:3]:
                print(f"    ({m['score']}) {m['candidat']} | {m['texte'][:90]}")


if __name__ == "__main__":
    main()
