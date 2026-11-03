"""Marchés publics attribués par les communes (< 10 000 hab.) et EPCI (< 20 000 hab.) des 20 départements,
d'après les données essentielles de la commande publique (DECP consolidées par decp.info / colibre.fr,
publiées chaque jour sur data.gouv.fr).

Un chantier attribué appelle un financement dans les mois qui suivent : c'est un signal « probable »,
jamais un « sûr ». Les marchés de services bancaires et d'emprunt attribués disent qui est la banque
en place (registre des concurrents).

  python3 decp.py signaux_decp.json [jours=365]     télécharge le fichier du jour (250 Mo) et écrit les signaux
"""
import json
import os
import re
import sys
import tempfile
import urllib.request
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import jget  # noqa: E402
from perimetre import DEPT2REG, norm  # noqa: E402

JEU = "608c055b35eb4e6ee20eb325"          # Données essentielles de la commande publique consolidées (format tabulaire)
COLONNES = ["uid", "acheteur_id", "acheteur_nom", "acheteur_categorie", "objet", "montant", "type", "codeCPV",
            "procedure", "dureeMois", "dateNotification", "titulaire_nom", "modification_id", "montant_anomalie"]
FINANCIER = re.compile(r"\bemprunts?\b|\bprets?\b|ligne de tresorerie|financement bancaire|services? bancaires?|"
                       r"credit de tresorerie|tenue de compte")
PAS_FINANCIER = re.compile(r"titres?[ -]restaurants?|cheques?[ -](?:dejeuner|cadeaux?)|assurance|carte achat")
ENTRETIEN = re.compile(r"entretien|accord.cadre|bons? de commande|maintenance|reparations?\b|marche a commandes")
MOE = re.compile(r"maitrise d.oeuvre|\bmoe\b|programmation|assistance a maitrise d.ouvrage|\bamo\b")


def fichier_du_jour(dossier):
    """Adresse du fichier Parquet le plus récent, téléchargé dans dossier."""
    d = jget(f"https://www.data.gouv.fr/api/1/datasets/{JEU}/", {}, tries=8, timeout=60)
    url = [r["url"] for r in d["resources"] if r.get("title") == "decp.parquet"][0]
    chemin = os.path.join(dossier, "decp.parquet")
    req = urllib.request.Request(url, headers={"User-Agent": "HectorVeille/1.0"})
    with urllib.request.urlopen(req, timeout=600) as r, open(chemin, "wb") as f:
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            f.write(bloc)
    return chemin, url


def lignes(chemin, depuis):
    import pyarrow.parquet as pq
    tb = pq.read_table(chemin, columns=COLONNES,
                       filters=[("acheteur_departement_code", "in", sorted(DEPT2REG)),
                                ("dateNotification", ">=", depuis)])
    return tb.to_pylist()


def signaux(rows, eligibles):
    """Par collectivité éligible : chantiers attribués, maîtrises d'œuvre, services bancaires et emprunts."""
    vus, out = set(), {}
    for r in sorted(rows, key=lambda r: r.get("modification_id") or 0):
        siren = (r.get("acheteur_id") or "")[:9]
        if siren not in eligibles or r["uid"] in vus:
            continue
        vus.add(r["uid"])                                    # attribution initiale, un titulaire par marché
        m = r.get("montant") or 0
        if r.get("montant_anomalie") and m > 20_000_000:
            continue
        o = norm(r.get("objet"))
        e = out.setdefault(siren, {"siren": siren, "nom": eligibles[siren]["nom"], "travaux": [], "moe": [],
                                   "financier": []})
        x = {"date": r["dateNotification"].isoformat() if r.get("dateNotification") else None,
             "objet": (r.get("objet") or "")[:160], "montant": round(m), "titulaire": r.get("titulaire_nom"),
             "cpv": r.get("codeCPV"), "duree_mois": r.get("dureeMois"), "procedure": r.get("procedure")}
        cpv = r.get("codeCPV") or ""
        if (cpv.startswith("6611") or FINANCIER.search(o) and r.get("type") == "Services") and not PAS_FINANCIER.search(o):
            e["financier"].append(x)
        elif r.get("type") == "Travaux" and m >= 15_000:
            x["entretien"] = bool(ENTRETIEN.search(o))
            e["travaux"].append(x)
        elif cpv.startswith("71") and MOE.search(o):
            e["moe"].append(x)
    for e in out.values():
        for k in ("travaux", "moe", "financier"):
            e[k].sort(key=lambda x: x["date"] or "", reverse=True)
    return {s: e for s, e in out.items() if e["travaux"] or e["moe"] or e["financier"]}


def resume(e, jour, jours=180):
    """Montant des chantiers attribués depuis `jours` jours et la phrase qui les décrit."""
    lim = (jour - timedelta(days=jours)).isoformat()
    # les accords-cadres d'entretien sont des plafonds sur plusieurs années, pas un chantier à financer
    tr = [t for t in e["travaux"] if (t["date"] or "") >= lim and not t.get("entretien")]
    total = sum(t["montant"] for t in tr)
    if not tr:
        return 0, None
    gros = max(tr, key=lambda t: t["montant"])
    return total, (f"{len(tr)} marché{'s' if len(tr) > 1 else ''} de travaux attribué{'s' if len(tr) > 1 else ''} "
                   f"depuis le {date.fromisoformat(lim):%d/%m} ({round(total / 1000)} k€), dont "
                   f"« {gros['objet'][:70]} » ({round(gros['montant'] / 1000)} k€, {date.fromisoformat(gros['date']):%d/%m})")


def eligibles_locaux():
    """Communes < 10 000 hab. et EPCI < 20 000 hab. du référentiel (copie locale, sans appel réseau)."""
    r = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "referentiel.json"), encoding="utf-8"))
    el = {s: c for s, c in r["communes"].items() if (c.get("population") or 0) < 10000}
    el.update({s: e for s, e in r["epcis"].items() if (e.get("population") or 0) < 20000})
    return el


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--fichier=")]
    local = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--fichier=")]
    sortie = args[0]
    jours = int(args[1]) if len(args) > 1 else 365
    eligibles = eligibles_locaux()
    jour = date.today()
    with tempfile.TemporaryDirectory() as tmp:
        chemin, url = (local[0], "fichier local") if local else fichier_du_jour(tmp)
        rows = lignes(chemin, jour - timedelta(days=jours))
    sig = signaux(rows, eligibles)
    for e in sig.values():
        e["travaux_180j"], e["phrase"] = resume(e, jour)
    res = {"genere": jour.isoformat(), "source": url, "lignes_lues": len(rows), "collectivites": sig}
    json.dump(res, open(sortie, "w"), ensure_ascii=False, indent=0)
    n_tr = sum(1 for e in sig.values() if e["travaux_180j"])
    print(f"{len(rows)} lignes DECP depuis {jours} jours ; {len(sig)} collectivités éligibles avec un marché ; "
          f"{n_tr} avec des travaux attribués depuis 180 jours ; "
          f"{sum(1 for e in sig.values() if e['financier'])} avec un marché bancaire ou d'emprunt")


if __name__ == "__main__":
    main()
