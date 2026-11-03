import unicodedata
DEPTS = {
 "Pays de la Loire": {"44":"Loire-Atlantique","49":"Maine-et-Loire","53":"Mayenne","72":"Sarthe","85":"Vendée"},
 "Bretagne": {"22":"Côtes-d'Armor","29":"Finistère","35":"Ille-et-Vilaine","56":"Morbihan"},
 "Centre-Val de Loire": {"18":"Cher","28":"Eure-et-Loir","36":"Indre","37":"Indre-et-Loire","41":"Loir-et-Cher","45":"Loiret"},
 "Normandie": {"14":"Calvados","27":"Eure","50":"Manche","61":"Orne","76":"Seine-Maritime"},
}
REGION_CODES = {"52":"Pays de la Loire","53":"Bretagne","24":"Centre-Val de Loire","28":"Normandie"}
DEPT2REG = {d:r for r,m in DEPTS.items() for d in m}
DEPT_NAME = {d:n for m in DEPTS.values() for d,n in m.items()}
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()
    return s
KW = ["emprunt","pret","financement","bancaire","banque","credit","tresorerie","concours financier","services financiers","refinancement"]

# ---------- propre à la région de ce dossier (le reste du code est identique pour toutes les régions) ----------
NOM = "Ouest"                                   # nom du bot et de la région
BOT = "Veille emprunts Ouest"                   # titre des messages Telegram
CODES = {n: c for c, n in DEPT_NAME.items()}    # nom du département -> code
# Registres publics des actes transmis en préfecture (API Mégalis / GIP RECIA)
PLATEFORMES = {
    "Mégalis Bretagne": "https://data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search",
    "GIP RECIA (Centre-Val de Loire)": "https://data-api.publication-actes.fr/mq_apis/actes/v1/search",
}
# Plateformes régionales de marchés publics (Atexo)
ATEXO = {
    "Mégalis Bretagne (marchés)": "https://marches.megalis.bretagne.bzh",
    "Marchés publics Pays de la Loire": "https://marchespublics.paysdelaloire.fr",
}
# Presse régionale : journal -> départements qu'il couvre (None : national ou multirégional)
MEDIAS = {
    "ouest-france.fr": ["14", "22", "29", "35", "44", "49", "50", "53", "56", "61", "72", "85"],
    "letelegramme.fr": ["22", "29", "35", "56"],
    "actu.fr": None,
    "lanouvellerepublique.fr": ["36", "37", "41"],
    "courrier-ouest.com": ["49"],
    "maine-libre.fr": ["72"],
    "presseocean.fr": ["44"],
    "paris-normandie.fr": ["76", "27"],
    "larep.fr": ["45"],
    "lechorepublicain.fr": ["28"],
    "leberry.fr": ["18"],
    "tendanceouest.com": ["14", "50", "61", "76", "27"],
    "actu44.fr": ["44"],
    "lepetitcourrier.fr": ["14"],
}
MEDIAS_PAR_DEPT = ["ouest-france.fr"]           # journaux interrogés département par département
SANS_REGISTRE = "Pays de la Loire et Normandie"  # territoires sans registre public des actes
