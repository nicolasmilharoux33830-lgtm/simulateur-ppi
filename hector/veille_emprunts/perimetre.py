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
