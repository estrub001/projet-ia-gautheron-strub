"""Génération de la réponse à partir des mesures trouvées par rechercher().

Répartition du travail :
- le modèle ne fait qu'une chose : classer chaque mesure ("pour", "contre" ou "hors_sujet") ;
- le code construit la réponse affichée à partir des mesures d'origine.
Le texte et la source affichés viennent donc toujours des données, jamais du modèle :
il ne peut ni inventer une mesure, ni en raccourcir une, ni inventer une source.
"""

import json
import os
import time

import requests

# Service d'inférence ILaaS (API compatible OpenAI), clé fournie par l'école
URL_API = "https://llm.ilaas.fr/v1"
MODELE = "mistral-small-4-119b"  # liste des modèles disponibles : GET {URL_API}/models
NB_ESSAIS = 4  # le serveur coupe parfois ou répond "occupé" : on réessaie

# True = fausse réponse sans appeler le modèle (pratique pour tester l'interface hors ligne)
MODE_FACTICE = False

# Le modèle reçoit plusieurs mesures par candidat, on n'affiche que les plus pertinentes
MESURES_AFFICHEES_PAR_CANDIDAT = 2

# Consignes données au modèle : il classe les mesures, il ne rédige rien
CONSIGNES = """Tu aides un citoyen à savoir ce que proposent les candidats à l'élection
présidentielle française de 2022. On te donne une question et une liste de mesures numérotées.

Pour CHAQUE mesure, indépendamment des autres, choisis un verdict :
- "pour" : la mesure répond directement à ce que demande la question, dans le sens demandé ;
- "contre" : la mesure fait l'inverse de la même chose précise que demande la question
  (ex. question "Qui veut développer le nucléaire ?", mesure "Sortir du nucléaire").
  Une mesure sur un sujet voisin n'est PAS "contre", même si elle semble aller dans une
  autre direction (ex. question "Qui veut supprimer la redevance télé ?", mesure
  "Augmenter le budget de la culture" : hors sujet, pas contre). En cas de doute,
  choisis "hors_sujet" ;
- "hors_sujet" : dans tous les autres cas. Une mesure qui partage seulement un mot avec la
  question (ex. "taxe", "prix", "aide") sans viser la même chose est hors sujet.
Si la question porte sur une personne ou un sujet dont les mesures ne parlent pas,
toutes les mesures sont hors sujet.

Réponds uniquement avec ce JSON, une entrée par mesure, la raison AVANT le verdict :
{"mesures": [{"id": 1, "raison": "une phrase courte", "verdict": "pour"}]}"""

MESSAGE_AUCUNE_MESURE = (
    "Je n'ai trouvé aucune mesure correspondant à votre question "
    "dans les programmes de 2022."
)
MESSAGE_CANDIDAT_SANS_MESURE = "*Aucune mesure de ce candidat ne répond à cette question.*"
PREFIXE_CONTRE = "À l'inverse : "  # devant une mesure qui va dans le sens opposé


def formater_mesures(mesures: list[dict]) -> str:
    """Liste numérotée des mesures, telle que le modèle la lit (le numéro sert d'identifiant)."""
    return "\n".join(
        f"{i}. [{m['candidat']}] {m['mesure']}" for i, m in enumerate(mesures, start=1)
    )


def generer_reponse(
    question: str, mesures: list[dict], candidats: list[str] | None = None
) -> str:
    """
    Répond à la question à partir des mesures renvoyées par rechercher().

    question  : la question du citoyen.
    mesures   : la liste renvoyée par rechercher(), la plus pertinente en premier (peut être vide).
    candidats : les candidats cochés. Un candidat coché sans aucune mesure (ex. toutes
                retirées par le seuil de la recherche) apparaît quand même, avec
                "aucune mesure". Si None, on prend les candidats présents dans les mesures.
    """
    # Pas de mesure : inutile d'appeler le modèle
    if not mesures:
        return MESSAGE_AUCUNE_MESURE

    if candidats is None:
        candidats = list(dict.fromkeys(m["candidat"] for m in mesures))

    if MODE_FACTICE:
        verdicts = ["pour"] * len(mesures)
    else:
        verdicts = classer_mesures(question, mesures)
    return construire_reponse(mesures, verdicts, candidats)


def classer_mesures(question: str, mesures: list[dict]) -> list[str]:
    """Demande au modèle un verdict ("pour", "contre", "hors_sujet") pour chaque mesure."""
    messages = [
        {"role": "system", "content": CONSIGNES},
        {"role": "user", "content": f"Question : {question}\n\nMesures :\n{formater_mesures(mesures)}"},
    ]
    try:
        resultat = json.loads(appeler_modele(messages))
    except json.JSONDecodeError as erreur:
        raise RuntimeError("Le modèle a renvoyé une réponse illisible, réessayez.") from erreur

    # Par défaut "hors_sujet" : une mesure oubliée par le modèle n'est jamais affichée
    verdicts = ["hors_sujet"] * len(mesures)
    for element in resultat.get("mesures", []):
        indice = element.get("id", 0) - 1
        verdict = element.get("verdict")
        if 0 <= indice < len(mesures) and verdict in ("pour", "contre"):
            verdicts[indice] = verdict
    return verdicts


def construire_reponse(mesures: list[dict], verdicts: list[str], candidats: list[str]) -> str:
    """
    Construit la réponse affichée, à partir des mesures d'origine et des verdicts du modèle :
    - par candidat, d'abord les mesures "pour", puis les "contre", 2 au maximum ;
    - les candidats qui ont des mesures en premier, ceux qui n'en ont pas à la fin
      (y compris un candidat coché pour qui la recherche n'a renvoyé aucune mesure) ;
    - si aucun candidat n'a de mesure, le message général.
    """
    retenues = {}
    for verdict_voulu in ("pour", "contre"):
        for m, verdict in zip(mesures, verdicts):  # mesures déjà triées par pertinence
            if m["candidat"] not in candidats:
                continue  # sécurité : on n'affiche que les candidats cochés
            puces = retenues.setdefault(m["candidat"], [])
            if verdict == verdict_voulu and len(puces) < MESURES_AFFICHEES_PAR_CANDIDAT:
                prefixe = PREFIXE_CONTRE if verdict == "contre" else ""
                puces.append(f"- {prefixe}{m['mesure']} [{m['source']}]")

    avec_mesures = {candidat: puces for candidat, puces in retenues.items() if puces}
    if not avec_mesures:
        return MESSAGE_AUCUNE_MESURE

    # "####" = titre markdown : en gras et un peu plus gros que le texte
    blocs = [f"#### {candidat}\n" + "\n".join(puces) for candidat, puces in avec_mesures.items()]
    # Tous les candidats cochés sans mesure, même ceux absents de la liste des mesures
    blocs += [
        f"#### {candidat}\n{MESSAGE_CANDIDAT_SANS_MESURE}"
        for candidat in candidats
        if candidat not in avec_mesures
    ]
    return "\n\n".join(blocs)


def appeler_modele(messages: list[dict]) -> str:
    """Envoie les messages au modèle ILaaS et renvoie sa réponse (un texte JSON)."""
    entetes = {
        # La clé est lue dans une variable d'environnement, jamais écrite dans le code
        "Authorization": f"Bearer {os.environ['ILAAS_API_KEY']}",
        "Content-Type": "application/json",
    }
    donnees = {
        "model": MODELE,
        "messages": messages,
        "temperature": 0,  # 0 = pas de hasard : même question -> même réponse
        "response_format": {"type": "json_object"},  # oblige le modèle à répondre en JSON
        "stream": False,
    }

    for essai in range(1, NB_ESSAIS + 1):
        try:
            reponse = requests.post(
                f"{URL_API}/chat/completions", headers=entetes, json=donnees, timeout=60
            )
            # 503 = modèle occupé : on réessaie un peu plus tard
            if reponse.status_code != 503:
                reponse.raise_for_status()  # erreur claire si 401 (clé), 404 (modèle)...
                return reponse.json()["choices"][0]["message"]["content"]
        except (requests.ConnectionError, requests.Timeout):
            # Connexion coupée ou trop longue : on réessaie, sauf au dernier essai
            if essai == NB_ESSAIS:
                raise
        if essai < NB_ESSAIS:
            time.sleep(3 * essai)  # attentes de plus en plus longues : 3 s, 6 s, 9 s

    raise RuntimeError(f"Le modèle {MODELE} est occupé, réessayez dans un instant.")


if __name__ == "__main__":
    from my_package.recherche import rechercher

    question = "Que proposent les candidats sur l'énergie ?"
    print(generer_reponse(question, rechercher(question)))
