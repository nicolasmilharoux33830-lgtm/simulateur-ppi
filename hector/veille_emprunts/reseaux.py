"""Pages Facebook, Instagram et applications mobiles officielles des communes et EPCI éligibles, d'après
l'Annuaire de l'administration (service-public.fr), qui publie les liens déclarés par chaque mairie.

Facebook n'est pas lu par Hector : ses pages demandent une connexion et son robots.txt interdit la
lecture automatique, et les moteurs de recherche ne renvoient pas ses publications (essai du 24/10/2026).
La liste sert à Nicolas, qui suit lui-même les pages des collectivités à appeler.

  python3 reseaux.py reseaux.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get  # noqa: E402
from perimetre import DEPT2REG, norm  # noqa: E402

ANNUAIRE = "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration"


def _liste(champ):
    try:
        v = json.loads(champ) if isinstance(champ, str) else (champ or [])
    except ValueError:
        return []
    return v if isinstance(v, list) else []


def liens(r):
    """{'facebook': [...], 'instagram': [...], 'applis': [...]} d'une fiche de l'annuaire."""
    out = {"facebook": [], "instagram": [], "applis": []}
    for x in _liste(r.get("reseau_social")):
        u, genre = (x.get("valeur") or "").strip(), norm(x.get("custom_dico2") or "")
        if "facebook" in genre or "facebook.com" in u:
            out["facebook"].append(u)
        elif "instagram" in genre or "instagram.com" in u:
            out["instagram"].append(u)
    for x in _liste(r.get("application_mobile")):
        t = " ".join(str(v) for v in x.values() if v) if isinstance(x, dict) else str(x)
        if t:
            out["applis"].append(t[:160])
    return out


def construire(sortie):
    import veille
    communes, epcis = veille.referentiel()
    insee = {c["code_insee"]: s for s, c in communes.items() if (c.get("population") or 0) < 10000}
    out = {}
    for d in sorted(DEPT2REG):
        for piv in ("mairie", "epci"):
            rows = json.loads(get(f"{ANNUAIRE}/exports/json",
                                  {"where": f'pivot like "{piv}" and startswith(code_insee_commune,"{d}")',
                                   "select": "nom,code_insee_commune,siren,reseau_social,application_mobile"},
                                  tries=40, timeout=120))
            for r in rows:
                if piv == "mairie":
                    if "deleguee" in norm(r.get("nom")) or r.get("code_insee_commune") not in insee:
                        continue
                    siren = insee[r["code_insee_commune"]]
                    ent = communes[siren]
                elif r.get("siren") in epcis and (epcis[r["siren"]].get("population") or 0) < 20000:
                    siren = r["siren"]
                    ent = epcis[siren]
                else:
                    continue
                l = liens(r)
                if not any(l.values()):
                    continue
                e = out.setdefault(siren, {"nom": ent["nom"], "type": "Commune" if piv == "mairie" else "EPCI",
                                           "dept": ent["dept"], "facebook": [], "instagram": [], "applis": []})
                for k, v in l.items():
                    e[k] += [x for x in v if x not in e[k]]
        print(d, len(out), flush=True)
    json.dump({"collectivites": out}, open(sortie, "w"), ensure_ascii=False, indent=0)
    print(len(out), "collectivités éligibles avec un réseau social ou une application ;",
          sum(1 for e in out.values() if e["facebook"]), "avec une page Facebook")
    return out


if __name__ == "__main__":
    construire(sys.argv[1])
