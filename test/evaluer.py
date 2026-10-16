"""Évalue rechercher() sur les questions de test/questions.csv.

Lancement depuis la racine du projet :
    uv run python test/evaluer.py                    (réglages par défaut de rechercher)
    uv run python test/evaluer.py -v                 (tous les résultats de chaque question)
    uv run python test/evaluer.py --sans-equilibre   (les N meilleures toutes confondues)
    uv run python test/evaluer.py --sans-seuil       (pas de score minimum)
    uv run python test/evaluer.py --n 6              (nombre de mesures demandées)
Les options se combinent, par exemple : --sans-equilibre --sans-seuil = l'ancienne version.

Format de questions.csv :
    question, candidat_filtre, fragments_attendus, candidats_attendus
    - fragments_attendus : un fragment par bonne mesure, séparés par "|"
    - candidats_attendus : les candidats qui ont une position, séparés par "|"
    - les deux vides = question hors sujet

Mesures calculées :
    - Top         : au moins une bonne mesure dans les résultats
    - 1re position et MRR : rang de la première bonne mesure
    - Rappel      : part des bonnes mesures retrouvées (sur max N attendues)
    - Couverture  : part des candidats concernés présents parmi les bonnes mesures
                    (questions où plusieurs candidats ont une position)
    - Hors sujet  : questions rejetées (aucun résultat au-dessus du seuil)
                    et meilleur score brut, pour régler le seuil
"""

import sys
from pathlib import Path

import pandas as pd

from my_package.recherche import SCORE_MIN, rechercher

CHEMIN_QUESTIONS = Path(__file__).resolve().parent / "questions.csv"
VERBEUX = "-v" in sys.argv
EQUILIBRER = "--sans-equilibre" not in sys.argv
SEUIL = None if "--sans-seuil" in sys.argv else SCORE_MIN
N = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 9


def decouper(valeur: str) -> list[str]:
    """'a|b|c' -> ['a', 'b', 'c'] (sans les morceaux vides)."""
    return [x.strip() for x in valeur.split("|") if x.strip()]


def fragments_trouves(mesure: dict, fragments: list[str]) -> list[str]:
    """Fragments attendus présents dans le texte de cette mesure."""
    texte = mesure["mesure"].lower()
    return [f for f in fragments if f.lower() in texte]


def afficher_resultats(resultats: list[dict], fragments: list[str]) -> None:
    """Affiche les résultats ; les bonnes mesures sont marquées d'une flèche."""
    if not resultats:
        print("     (aucun résultat au-dessus du seuil)")
    for rang, m in enumerate(resultats, start=1):
        fleche = "->" if fragments_trouves(m, fragments) else "  "
        print(f"  {fleche} {rang}. ({m['score']}) {m['candidat']} | {m['mesure'][:90]}")


def main() -> None:
    df = pd.read_csv(CHEMIN_QUESTIONS, dtype=str, encoding="utf-8-sig").fillna("")

    print(
        f"Réglages : n={N}, équilibre par candidat={'oui' if EQUILIBRER else 'non'}, "
        f"seuil={SEUIL if SEUIL is not None else 'aucun'}"
    )

    nb_attendues, trouves, rejets_a_tort = 0, 0, 0
    rangs, scores_bons, rappels, couvertures, nb_resultats = [], [], [], [], []
    hors_sujet, rates = [], []

    for _, q in df.iterrows():
        question = q["question"].strip()
        if not question:
            continue
        candidat = q["candidat_filtre"].strip() or None
        fragments = decouper(q["fragments_attendus"])
        candidats = decouper(q["candidats_attendus"])

        resultats = rechercher(
            question, candidat=candidat, n=N, equilibrer=EQUILIBRER, score_min=SEUIL
        )

        # --- Question hors sujet : rejetée ou non, et meilleur score brut (sans seuil)
        if not fragments:
            bruts = rechercher(question, candidat=candidat, n=N, equilibrer=EQUILIBRER, score_min=None)
            meilleur = bruts[0]["score"] if bruts else 0
            rejetee = not resultats
            hors_sujet.append((question, meilleur, rejetee))
            if VERBEUX:
                etat = "REJETÉE" if rejetee else f"{len(resultats)} résultat(s) renvoyé(s)"
                print(f"\n[HORS SUJET | {etat}] {question} -> meilleur score brut {meilleur}")
                afficher_resultats(resultats, [])
            continue

        nb_attendues += 1
        nb_resultats.append(len(resultats))
        if not resultats:
            rejets_a_tort += 1

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

        # Rappel : sur au plus N mesures attendues
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
    print(f"Au moins une bonne mesure dans les résultats : {trouves}/{nb_attendues}")
    print(f"Bonne mesure en 1re position : {rangs.count(1)}/{nb_attendues}")
    print(f"MRR (1 = toujours premier) : {sum(1 / r for r in rangs) / nb_attendues:.2f}")
    print(f"Rappel moyen (part des bonnes mesures retrouvées) : {sum(rappels) / len(rappels):.0%}")
    if couvertures:
        print(
            f"Couverture candidats ({len(couvertures)} questions à plusieurs candidats) : "
            f"{sum(couvertures) / len(couvertures):.0%}"
        )
    print(f"Nombre moyen de mesures renvoyées : {sum(nb_resultats) / len(nb_resultats):.1f}")
    print(f"Questions normales rejetées à tort (aucun résultat) : {rejets_a_tort}/{nb_attendues}")
    if scores_bons:
        print(
            f"Score de la 1re bonne mesure : min {min(scores_bons)}, "
            f"moyen {sum(scores_bons) / len(scores_bons):.3f}"
        )
    if hors_sujet:
        nb_rejetees = sum(r for _, _, r in hors_sujet)
        print(f"\nHors sujet rejetés : {nb_rejetees}/{len(hors_sujet)}")
        for question, score, rejetee in sorted(hors_sujet, key=lambda x: -x[1]):
            etat = "rejetée" if rejetee else "PASSE  "
            print(f"  [{etat}] ({score}) {question}")

    if rates and not VERBEUX:
        print("\nQuestions ratées (relancer avec -v pour tout voir) :")
        for question, resultats, fragments in rates:
            print(f"\n  {question}")
            afficher_resultats(resultats[:3], fragments)


if __name__ == "__main__":
    main()