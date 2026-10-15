"""Génération de la réponse à partir des mesures trouvées par rechercher()."""

import os

from mistralai.client import Mistral

MODELE = "mistral-small-latest"

# VERSION TEMPORAIRE : True = fausse réponse sans appeler Mistral (pas besoin de clé).
# Repasser à False quand on aura un accès à l'API.
MODE_FACTICE = True

# Consignes données au modèle : il ne doit utiliser QUE les mesures fournies
CONSIGNES = """Tu es un assistant neutre qui aide les citoyens à comprendre
les programmes de l'élection présidentielle française de 2022.

Règles :
- Réponds uniquement à partir des mesures fournies. N'invente rien.
- Si les mesures ne permettent pas de répondre, dis-le simplement.
- Présente les propositions candidat par candidat, sans donner ton avis
  et sans juger quelle proposition est la meilleure.
- Pour chaque mesure citée, indique sa source entre crochets, ex. [projet-lecologie.pdf].
- Réponds en français, de façon claire et concise."""

MESSAGE_AUCUNE_MESURE = (
    "Je n'ai trouvé aucune mesure correspondant à votre question "
    "dans les programmes de 2022."
)



def formater_mesures(mesures: list[dict]) -> str:
    """Transforme la liste de mesures en texte lisible par le modèle."""
    lignes = []
    for i, m in enumerate(mesures, start=1):
        lignes.append(
            f"{i}. Candidat : {m['candidat']}\n"
            f"   Thème : {m['theme']}\n"
            f"   Mesure : {m['texte']}\n"
            f"   Source : {m['source']} ({m['date']})"
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

    client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

    message_utilisateur = (
        f"Question du citoyen : {question}\n\n"
        f"Mesures des programmes :\n\n{formater_mesures(mesures)}"
    )

    reponse = client.chat.complete(
        model=MODELE,
        messages=[
            {"role": "system", "content": CONSIGNES},
            {"role": "user", "content": message_utilisateur},
        ],
        temperature=0.2,  # bas = réponses plus fidèles aux mesures
    )
    return reponse.choices[0].message.content


def reponse_factice(mesures: list[dict]) -> str:
    """Fausse réponse au même format que celle du modèle, pour tester l'interface."""
    lignes = ["*(Réponse factice : le modèle n'est pas encore branché.)*", ""]
    for m in mesures:
        lignes.append(f"- **{m['candidat']}** : {m['texte']} [{m['source']}]")
    return "\n".join(lignes)


if __name__ == "__main__":
    from my_package.recherche import rechercher

    question = "Que proposent les candidats sur l'énergie ?"
    print(generer_reponse(question, rechercher(question)))
