"""Génération de la réponse à partir des mesures trouvées par rechercher()."""

import os
import time

import requests

# Service d'inférence ILaaS (API compatible OpenAI), clé fournie par l'école
URL_API = "https://llm.ilaas.fr/v1"
MODELE = "mistral-small-4-119b"  # liste des modèles disponibles : GET {URL_API}/models
NB_ESSAIS = 3  # le serveur coupe parfois ou répond "occupé" : on réessaie

# True = fausse réponse sans appeler le modèle (pratique pour tester l'interface hors ligne)
MODE_FACTICE = False

# Consignes données au modèle : il ne doit utiliser QUE les mesures fournies
CONSIGNES = """Tu es un assistant neutre qui aide les citoyens à comprendre
les programmes de l'élection présidentielle française de 2022.

Règles :
- Réponds uniquement à partir des mesures fournies. N'invente rien.
- Si les mesures ne permettent pas de répondre, dis-le simplement.
- Présente les propositions candidat par candidat, sans donner ton avis
  et sans juger quelle proposition est la meilleure.
- Format à respecter pour chaque candidat : une ligne "#### Nom du candidat",
  puis ses mesures sous forme de liste à puces ("- ...").
- Termine chaque puce par la "Source" de la mesure entre crochets, recopiée telle quelle,
  sans point après, ex. "- Baisser la TVA sur l'énergie. [projet-lecologie.pdf]".
- Réponds en français, de façon claire et concise."""

MESSAGE_AUCUNE_MESURE = (
    "Je n'ai trouvé aucune mesure correspondant à votre question "
    "dans les programmes de 2022."
)



def formater_mesures(mesures: list[dict]) -> str:
    """Transforme la liste de mesures en texte lisible par le modèle."""
    lignes = []
    for i, m in enumerate(mesures, start=1):
        theme = m["theme"]
        if m["theme_secondaire"]:
            theme += f" / {m['theme_secondaire']}"
        lignes.append(
            f"{i}. Candidat : {m['candidat']}\n"
            f"   Thème : {theme}\n"
            f"   Mesure : {m['mesure']}\n"
            f"   Source : {m['source']}\n"
            f"   Type de source : {m['type_source']} ({m['date']})"
        )
    return "\n\n".join(lignes)


def generer_reponse(question: str, mesures: list[dict]) -> str:
    """
    Rédige une réponse à la question à partir des mesures renvoyées par rechercher().

    question : la question du citoyen.
    mesures  : la liste renvoyée par rechercher() (peut être vide).
    """
    # Pas de mesure : inutile d'appeler le modèle, il risquerait d'inventer
    if not mesures:
        return MESSAGE_AUCUNE_MESURE

    if MODE_FACTICE:
        return reponse_factice(mesures)

    message_utilisateur = (
        f"Question du citoyen : {question}\n\n"
        f"Mesures des programmes :\n\n{formater_mesures(mesures)}"
    )
    return appeler_modele(
        [
            {"role": "system", "content": CONSIGNES},
            {"role": "user", "content": message_utilisateur},
        ]
    )


def appeler_modele(messages: list[dict]) -> str:
    """Envoie les messages au modèle ILaaS et renvoie le texte de sa réponse."""
    entetes = {
        # La clé est lue dans une variable d'environnement, jamais écrite dans le code
        "Authorization": f"Bearer {os.environ['ILAAS_API_KEY']}",
        "Content-Type": "application/json",
    }
    donnees = {
        "model": MODELE,
        "messages": messages,
        "temperature": 0.2,  # bas = réponses plus fidèles aux mesures
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
        except requests.ConnectionError:
            if essai == NB_ESSAIS:
                raise
        time.sleep(2 * essai)

    raise RuntimeError(f"Le modèle {MODELE} est occupé, réessayez dans un instant.")


def grouper_par_candidat(mesures: list[dict]) -> dict[str, list[dict]]:
    """Regroupe les mesures par candidat, en gardant l'ordre de pertinence."""
    groupes = {}
    for m in mesures:
        groupes.setdefault(m["candidat"], []).append(m)
    return groupes


def reponse_factice(mesures: list[dict]) -> str:
    """Fausse réponse au même format que celle du modèle, pour tester l'interface."""
    lignes = ["*(Réponse factice : le modèle n'est pas appelé.)*"]
    for candidat, mesures_candidat in grouper_par_candidat(mesures).items():
        # "####" = titre markdown : en gras et un peu plus gros que le texte
        lignes += ["", f"#### {candidat}"]
        for m in mesures_candidat:
            lignes.append(f"- {m['mesure']} [{m['source']}]")
    return "\n".join(lignes)


if __name__ == "__main__":
    from my_package.recherche import rechercher

    question = "Que proposent les candidats sur l'énergie ?"
    print(generer_reponse(question, rechercher(question)))
