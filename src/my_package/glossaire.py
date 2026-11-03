"""Glossaire des sigles et termes techniques des programmes.

Sert à enrichir le texte AVANT de le vectoriser, pour que la recherche fasse le lien
entre un sigle et les mots qu'un citoyen utilise (ex. « CETA » <-> « Canada »).
Le texte de la mesure affiché à l'utilisateur ne change pas.

- Clés en MAJUSCULES (sigles) : reconnues seulement en majuscules et en mot entier
  (« BUT » le diplôme, pas « but » le mot courant).
- Autres clés (termes) : reconnues sans tenir compte des majuscules.
- Les définitions restent neutres et factuelles, et ajoutent les mots du langage courant.

Pour ajouter un terme : une ligne "SIGLE": "définition, synonymes courants".
"""

import re

GLOSSAIRE = {
    # --- Commerce et international
    "CETA": "accord de libre-échange entre l'Union européenne et le Canada",
    "MERCOSUR": "marché commun d'Amérique du Sud (Brésil, Argentine, Uruguay, Paraguay), accord de libre-échange",
    "OMC": "Organisation mondiale du commerce, échanges commerciaux internationaux",
    "UE": "Union européenne, Europe",
    "BCE": "Banque centrale européenne, euro, politique monétaire",
    "FMI": "Fonds monétaire international",
    "OCDE": "Organisation de coopération et de développement économiques",
    "ONU": "Organisation des Nations unies",
    "OTAN": "Organisation du traité de l'Atlantique Nord, alliance militaire",
    "OSCE": "Organisation pour la sécurité et la coopération en Europe",
    "BRICS": "Brésil, Russie, Inde, Chine, Afrique du Sud, pays émergents",
    "CNUCED": "Conférence des Nations unies sur le commerce et le développement",
    "FAO": "Organisation des Nations unies pour l'alimentation et l'agriculture",
    "OMS": "Organisation mondiale de la santé",
    "UNESCO": "Organisation des Nations unies pour l'éducation, la science et la culture",
    "UNHCR": "Haut Commissariat des Nations unies pour les réfugiés, asile",
    "OIM": "Organisation internationale pour les migrations, migrants",
    "UICN": "Union internationale pour la conservation de la nature, biodiversité",
    "AFD": "Agence française de développement, aide aux pays pauvres",
    "APF": "Assemblée parlementaire de la Francophonie",
    "CELAC": "Communauté des États latino-américains et caraïbes",
    "CDAA": "Communauté de développement d'Afrique australe",
    "IORA": "Association des pays riverains de l'océan Indien",
    "CFA": "franc CFA, monnaie de pays d'Afrique, ou centre de formation d'apprentis",
    "ECO": "nouvelle monnaie d'Afrique de l'Ouest remplaçant le franc CFA",
    "ONG": "organisation non gouvernementale, associations",
    "Schengen": "espace de libre circulation sans contrôle aux frontières en Europe",
    "Frontex": "agence européenne de garde-frontières, contrôle des frontières",
    "Dublin": "règlement européen sur l'État responsable des demandes d'asile",
    "Erasmus": "programme européen d'échanges d'étudiants",
    # --- Impôts, économie, entreprises
    "ISF": "impôt de solidarité sur la fortune, impôt sur les riches, patrimoine",
    "IFI": "impôt sur la fortune immobilière, impôt sur les riches, patrimoine",
    "flat tax": "prélèvement forfaitaire unique de 30 % sur les revenus du capital, dividendes, placements",
    "exit tax": "impôt sur les plus-values des contribuables qui partent vivre à l'étranger, exil fiscal",
    "CSG": "contribution sociale généralisée, prélèvement sur les revenus pour financer la Sécurité sociale",
    "TVA": "taxe sur la valeur ajoutée, impôt sur la consommation, prix",
    "CVAE": "cotisation sur la valeur ajoutée des entreprises, impôt de production",
    "PIB": "produit intérieur brut, richesse nationale",
    "CAC": "CAC 40, grandes entreprises cotées en Bourse",
    "LBO": "rachat d'entreprise financé par l'emprunt",
    "PGE": "prêt garanti par l'État, aide aux entreprises pendant le Covid",
    "PPP": "partenariat public-privé",
    "PME": "petites et moyennes entreprises",
    "TPE": "très petites entreprises, artisans, commerçants",
    "ESS": "économie sociale et solidaire, coopératives, associations",
    "CAE": "coopérative d'activité et d'emploi, indépendants",
    "SCOP": "société coopérative et participative, entreprise détenue par les salariés",
    "SCIC": "société coopérative d'intérêt collectif",
    "GAFAM": "géants du numérique : Google, Apple, Facebook, Amazon, Microsoft",
    "EADS": "ancien nom d'Airbus, aéronautique",
    "de minimis": "petites aides publiques aux entreprises autorisées par l'Union européenne",
    "superprofits": "bénéfices exceptionnels des grandes entreprises",
    # --- Énergie, environnement
    "EPR": "réacteur nucléaire de nouvelle génération, centrale nucléaire",
    "EMR": "énergies marines renouvelables, éoliennes en mer, hydroliennes",
    "GW": "gigawatt, puissance électrique",
    "EDF": "Électricité de France, électricité, nucléaire",
    "GES": "gaz à effet de serre, émissions de CO2, climat",
    "CO2": "dioxyde de carbone, émissions de gaz à effet de serre, climat",
    "ICPE": "installations industrielles à risque pour l'environnement, usines dangereuses",
    "carburants": "essence, gazole, diesel, plein, prix à la pompe",
    "fioul": "fioul domestique, chauffage au fioul",
    "bifurcation écologique": "transition écologique, changement de modèle pour le climat",
    "planification écologique": "transition écologique organisée par l'État, climat",
    "règle verte": "ne pas prélever sur la nature plus qu'elle ne peut reconstituer",
    "passoires": "logements mal isolés, rénovation énergétique, chauffage",
    # --- Agriculture, alimentation
    "PAC": "politique agricole commune, aides européennes aux agriculteurs",
    "EGalim": "loi sur les prix agricoles et l'alimentation, revenu des agriculteurs",
    "HVE": "haute valeur environnementale, label agricole",
    "OGM": "organismes génétiquement modifiés",
    "ZNT": "zones de non-traitement, pesticides près des habitations",
    "nutri-score": "étiquetage nutritionnel des aliments, qualité alimentaire",
    "Inra": "institut de recherche agronomique",
    # --- Social, santé, retraite
    "RSA": "revenu de solidarité active, minimum social, aide aux personnes sans revenu",
    "AAH": "allocation aux adultes handicapés, handicap",
    "APL": "aide personnalisée au logement, aide au loyer",
    "ASF": "allocation de soutien familial, parents seuls, familles monoparentales",
    "CAF": "caisse d'allocations familiales, aides sociales",
    "SMIC": "salaire minimum, bas salaires",
    "RTT": "réduction du temps de travail, jours de repos, congés",
    "CDD": "contrat à durée déterminée, emploi précaire",
    "TODE": "exonération de cotisations pour les travailleurs saisonniers agricoles",
    "CHSCT": "comité d'hygiène, de sécurité et des conditions de travail, santé au travail",
    "Pôle emploi": "service public de l'emploi, chômeurs, chômage",
    "France Travail": "nouveau nom de Pôle emploi, chômage, recherche d'emploi",
    "RATP": "transports en commun parisiens, régimes spéciaux de retraite",
    "Sécu": "Sécurité sociale, assurance maladie, remboursement des soins",
    "EHPAD": "maisons de retraite médicalisées, personnes âgées, dépendance",
    "ARS": "agences régionales de santé, hôpitaux",
    "CMP": "centres médico-psychologiques, santé mentale, psychiatrie",
    "AME": "aide médicale d'État, soins des étrangers sans papiers",
    "VIH": "virus du sida",
    "IVG": "interruption volontaire de grossesse, avortement",
    "PMA": "procréation médicalement assistée",
    "GPA": "gestation pour autrui, mères porteuses",
    "PNSE": "plan national santé environnement, pollution",
    "Inserm": "institut de recherche médicale",
    "ASE": "aide sociale à l'enfance, protection de l'enfance, enfants placés",
    "LGBTI": "personnes lesbiennes, gays, bisexuelles, trans et intersexes",
    # --- Éducation, recherche
    "AESH": "accompagnants des élèves en situation de handicap, auxiliaires de vie scolaire, AVS",
    "CP": "cours préparatoire, première année d'école primaire",
    "REP": "réseau d'éducation prioritaire, écoles des quartiers populaires",
    "ZEP": "zone d'éducation prioritaire, écoles des quartiers populaires",
    "RASED": "réseau d'aide aux élèves en difficulté",
    "ELCO": "cours de langue et culture d'origine pour enfants d'immigrés",
    "CAPES": "concours de recrutement des professeurs",
    "INSPÉ": "instituts de formation des enseignants",
    "BTS": "brevet de technicien supérieur, études courtes",
    "DUT": "diplôme universitaire de technologie, études courtes",
    "BUT": "bachelor universitaire de technologie, études courtes",
    "LSF": "langue des signes française, sourds",
    "LRU": "loi sur l'autonomie des universités",
    "Fioraso": "loi de 2013 sur l'enseignement supérieur et la recherche",
    "Blanquer": "ministre de l'Éducation, réforme du baccalauréat et du lycée",
    "Parcoursup": "plateforme d'admission dans l'enseignement supérieur après le bac",
    "CNRS": "Centre national de la recherche scientifique",
    "CTS": "conseillers techniques sportifs, sport",
    # --- Sécurité, justice, défense
    "BAC": "brigades anticriminalité, police",
    "BRAV-M": "brigades motorisées de police, maintien de l'ordre, manifestations",
    "IGPN": "inspection générale de la police, « police des polices »",
    "IGGN": "inspection générale de la gendarmerie",
    "DGSE": "services de renseignement extérieur, espionnage",
    "DST": "ancienne direction du renseignement intérieur",
    "RG": "renseignements généraux, renseignement intérieur",
    "ANSSI": "agence nationale de cybersécurité, cyberattaques",
    "PHAROS": "plateforme de signalement des contenus illicites sur internet",
    "OFAST": "office anti-stupéfiants, drogue, trafic",
    "JIRS": "juridictions spécialisées contre le crime organisé",
    "Perben": "loi Perben II sur la criminalité organisée et la procédure pénale",
    "SMA": "service militaire adapté, insertion des jeunes en outre-mer",
    "SNSM": "sauvetage en mer",
    "CEDH": "Convention européenne des droits de l'homme, Cour européenne des droits de l'homme",
    "CNIL": "autorité de protection des données personnelles, vie privée",
    # --- Institutions, territoires, logement, transports
    "RIC": "référendum d'initiative citoyenne, démocratie directe",
    "6e République": "nouvelle Constitution, changement de régime politique",
    "Constituante": "assemblée élue pour écrire une nouvelle Constitution",
    "49.3": "article de la Constitution permettant d'adopter une loi sans vote",
    "priorité nationale": "accès prioritaire des Français à l'emploi, au logement ou aux aides",
    "HLM": "logements sociaux, habitations à loyer modéré",
    "SRU": "loi imposant un quota de logements sociaux dans les communes",
    "RE2020": "réglementation environnementale des constructions neuves",
    "SNCF": "trains, chemins de fer",
    "Galileo": "système européen de géolocalisation par satellite, concurrent du GPS",
    "FEDER": "fonds européen de développement régional",
    "POSEI": "aides européennes à l'agriculture des outre-mer",
    "Mayotte": "département d'outre-mer dans l'océan Indien",
    "Ultramarins": "habitants des outre-mer, DOM-TOM",
    "ultramarins": "des outre-mer, DOM-TOM",
}


def _motif(cle: str) -> re.Pattern:
    """Mot entier ; sensible aux majuscules seulement pour les sigles."""
    drapeaux = 0 if cle.isupper() else re.IGNORECASE
    return re.compile(rf"(?<!\w){re.escape(cle)}(?!\w)", drapeaux)


_MOTIFS = [(cle, definition, _motif(cle)) for cle, definition in GLOSSAIRE.items()]


def enrichir(texte: str) -> str:
    """Ajoute à la fin du texte la définition des sigles et termes qu'il contient.

    "Ne pas ratifier le traité CETA."
    -> "Ne pas ratifier le traité CETA. (Lexique : CETA : accord de libre-échange ... Canada)"
    """
    definitions = [f"{cle} : {definition}" for cle, definition, motif in _MOTIFS if motif.search(texte)]
    if not definitions:
        return texte
    return f"{texte} (Lexique : {' ; '.join(definitions)})"