import unicodedata
DEPTS = {
 "Nouvelle-Aquitaine": {"16":"Charente","17":"Charente-Maritime","19":"Corrèze","23":"Creuse","24":"Dordogne","33":"Gironde","40":"Landes","47":"Lot-et-Garonne","64":"Pyrénées-Atlantiques","79":"Deux-Sèvres","86":"Vienne","87":"Haute-Vienne"},
 "Midi-Pyrénées": {"09":"Ariège","12":"Aveyron","31":"Haute-Garonne","32":"Gers","46":"Lot","65":"Hautes-Pyrénées","81":"Tarn","82":"Tarn-et-Garonne"},
}
REGION_CODES = {"75":"Nouvelle-Aquitaine","76":"Midi-Pyrénées"}
DEPT2REG = {d:r for r,m in DEPTS.items() for d in m}
DEPT_NAME = {d:n for m in DEPTS.values() for d,n in m.items()}
def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()
    return s
KW = ["emprunt","pret","financement","bancaire","banque","credit","tresorerie","concours financier","services financiers","refinancement"]

# ---------- propre à la région de ce dossier (le reste du code est identique pour toutes les régions) ----------
NOM = "Sud-Ouest"                               # nom du bot et de la région
BOT = "Veille emprunts Sud-Ouest"               # titre des messages Telegram
CODES = {n: c for c, n in DEPT_NAME.items()}    # nom du département -> code
# Registres publics des actes transmis en préfecture (API) : aucun connu en Nouvelle-Aquitaine ni en
# Midi-Pyrénées pour l'instant ; à compléter ici dès qu'un registre est trouvé (même format que Mégalis).
PLATEFORMES = {}
# Plateformes régionales de marchés publics (Atexo) : à compléter ; AWS, e-marchespublics, BOAMP et TED
# couvrent déjà les 20 départements.
ATEXO = {}
# Presse régionale : journal -> départements qu'il couvre (None : national ou multirégional)
MEDIAS = {
    "sudouest.fr": ["16", "17", "19", "24", "33", "40", "47", "64", "79", "86"],
    "ladepeche.fr": ["09", "12", "31", "32", "46", "65", "81", "82", "47"],
    "lanouvellerepublique.fr": ["79", "86"],
    "actu.fr": None,
    "centrepresseaveyron.fr": ["12"],
    "lamontagne.fr": ["19", "23"],
    "lepopulaire.fr": ["87", "19", "23"],
    "charentelibre.fr": ["16"],
    "larepubliquedespyrenees.fr": ["65", "64"],
    "lepetitbleu.fr": ["47"],
    "lindependant.fr": ["09"],
    "midilibre.fr": ["12"],
}
MEDIAS_PAR_DEPT = ["sudouest.fr", "ladepeche.fr"]   # journaux interrogés département par département
SANS_REGISTRE = "Nouvelle-Aquitaine et Midi-Pyrénées"  # territoires sans registre public des actes
