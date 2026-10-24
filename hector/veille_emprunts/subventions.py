"""Subventions d'investissement obtenues par les communes et EPCI éligibles : un projet subventionné doit
trouver le reste de son financement (autofinancement, emprunt). Signal « probable », jamais un « sûr ».

Sources structurées :
- Fonds vert, liste des projets subventionnés (Ministère de la Transition écologique, data.gouv.fr, un
  fichier par année) ;
- aides de la Région des Pays de la Loire versées aux communes et EPCI (data.paysdelaloire.fr, mis à jour
  chaque semaine) : projet, dispositif, montant voté et déjà versé ; le reste à percevoir est souvent
  préfinancé (prêt relais).
Les régions Centre-Val de Loire, Bretagne et Normandie et les départements ne publient pas (ou pas à jour)
leurs aides aux communes en données ouvertes : leurs fichiers ne portent que sur les associations.
DETR et DSIL ne sont publiées qu'en PDF par chaque préfecture, au printemps : pas encore lues.

  python3 subventions.py subventions.json
"""
import csv
import io
import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get, jget  # noqa: E402
from perimetre import DEPT2REG, norm  # noqa: E402

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
    raw = get(url, tries=10, timeout=300)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            s = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    dia = csv.Sniffer().sniff(s[:5000], delimiters=";,\t")
    return list(csv.DictReader(io.StringIO(s), dialect=dia))


PDL = "https://data.paysdelaloire.fr/api/explore/v2.1/catalog/datasets/subventions-de-la-region-des-pays-de-la-loire"


def region_pdl(eligibles, depuis):
    """Aides de la Région des Pays de la Loire versées depuis `depuis`, une ligne par dossier."""
    rows = json.loads(get(f"{PDL}/exports/json", {
        "where": f'(startswith(tgen_siret_numero, "21") or startswith(tgen_siret_numero, "200") or '
                 f'startswith(tgen_siret_numero, "24")) and date_execution >= date\'{depuis}\'',
        "select": "date_execution,vote_a_jour,mandat_valeur,code_dossier,libelle_dossier,libelle_aide,"
                  "libelle_operation,libelle_programme,tgen_siret_numero"}, tries=20, timeout=180))
    dossiers = {}
    for x in rows:
        siren = (x.get("tgen_siret_numero") or "").replace(" ", "")[:9]
        if siren not in eligibles:
            continue
        projet = x.get("libelle_dossier") or x.get("libelle_operation") or ""
        if not projet or re.search(r"feder|fse|leader|feader", norm(f"{projet} {x.get('libelle_programme')}")):
            continue                        # fonds européens : la Région ne fait que transmettre
        k = (siren, x.get("code_dossier") or projet)
        d = dossiers.setdefault(k, {"siren": siren, "vote": 0.0, "verse": 0.0, "date": "", "projet": projet,
                                    "aide": x.get("libelle_aide") or x.get("libelle_programme") or ""})
        d["vote"] = max(d["vote"], float(x.get("vote_a_jour") or 0))
        d["verse"] += float(x.get("mandat_valeur") or 0)
        d["date"] = max(d["date"], x.get("date_execution") or "")
    out = {}
    for d in dossiers.values():
        montant = d["vote"] or d["verse"]
        out.setdefault(d["siren"], []).append({
            "dispositif": "Région Pays de la Loire", "aide": d["aide"][:80], "annee": int(d["date"][:4]),
            "date": d["date"], "montant": round(montant), "verse": round(d["verse"]),
            "reste": round(max(0, d["vote"] - d["verse"])), "projet": d["projet"][:160]})
    return len(rows), out


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
    try:
        n, pdl = region_pdl(eligibles, f"{an - 1}-01-01")
        lus += n
        for s, v in pdl.items():
            out.setdefault(s, []).extend(v)
        print(n, "versements de la Région des Pays de la Loire lus ;", len(pdl), "collectivités éligibles aidées")
    except Exception as e:
        print("Région des Pays de la Loire : ERREUR", str(e)[:120])
    for v in out.values():
        v.sort(key=lambda x: (-x["annee"], -x["montant"]))
    json.dump({"genere": date.today().isoformat(), "lignes_lues": lus, "collectivites": out},
              open(sortie, "w"), ensure_ascii=False, indent=0)
    print(lus, "projets Fonds vert lus ;", len(out), "collectivités éligibles subventionnées")


if __name__ == "__main__":
    main()
