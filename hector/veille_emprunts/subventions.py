"""Subventions d'investissement obtenues par les communes et EPCI éligibles : un projet subventionné doit
trouver le reste de son financement (autofinancement, emprunt). Signal « probable », jamais un « sûr ».

Source structurée disponible : Fonds vert, liste des projets subventionnés (Ministère de la Transition
écologique, data.gouv.fr, un fichier par année). DETR et DSIL ne sont publiées qu'en PDF par chaque
préfecture, au printemps : pas encore lues.

  python3 subventions.py subventions.json
"""
import csv
import io
import json
import os
import re
import sys
import urllib.request
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import jget  # noqa: E402
from perimetre import DEPT2REG  # noqa: E402

FONDS_VERT = "66a215a463a9da4fb801b8cf"


def fichiers_fonds_vert(annees):
    d = jget(f"https://www.data.gouv.fr/api/1/datasets/{FONDS_VERT}/", {}, tries=8, timeout=60)
    out = []
    for r in d["resources"]:
        t = r.get("title") or ""
        m = re.match(r"fonds-vert-(\d{4})-export\.csv", t)
        if m and int(m.group(1)) in annees:
            out.append((int(m.group(1)), r["url"]))
    return out


def lire_csv(url):
    req = urllib.request.Request(url, headers={"User-Agent": "HectorVeille/1.0"})
    raw = urllib.request.urlopen(req, timeout=300).read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            s = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    dia = csv.Sniffer().sniff(s[:5000], delimiters=";,\t")
    return list(csv.DictReader(io.StringIO(s), dialect=dia))


def main():
    sortie = sys.argv[1]
    r = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "referentiel.json"), encoding="utf-8"))
    eligibles = {s for s, c in r["communes"].items() if (c.get("population") or 0) < 10000}
    eligibles |= {s for s, e in r["epcis"].items() if (e.get("population") or 0) < 20000}
    an = date.today().year
    out = {}
    lus = 0
    for annee, url in fichiers_fonds_vert({an - 2, an - 1, an}):
        rows = lire_csv(url)
        lus += len(rows)
        for x in rows:
            siren = (x.get("siret_beneficiaire") or "")[:9]
            if siren not in eligibles or (x.get("code_departement") or "") not in DEPT2REG:
                continue
            try:
                m = float(x.get("montant_engage") or 0)
            except ValueError:
                m = 0
            out.setdefault(siren, []).append({"dispositif": "Fonds vert", "annee": annee, "montant": round(m),
                                              "projet": (x.get("nom_du_projet") or "")[:160],
                                              "demarche": x.get("demarche")})
    for v in out.values():
        v.sort(key=lambda x: (-x["annee"], -x["montant"]))
    json.dump({"genere": date.today().isoformat(), "lignes_lues": lus, "collectivites": out},
              open(sortie, "w"), ensure_ascii=False, indent=0)
    print(lus, "projets Fonds vert lus ;", len(out), "collectivités éligibles subventionnées")


if __name__ == "__main__":
    main()
