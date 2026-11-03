"""Registre des prêts et lignes de trésorerie des communes et EPCI éligibles, pour savoir qui est la banque
en place et quand un contrat arrive à échéance.

Sources (tâche de nuit, pas la routine du matin) :
- annexes « état de la dette » des budgets XML (TOTEM) publiés sur Mégalis et RECIA : prêteur, montant,
  date de signature, taux, capital restant dû, durée restante, pour chaque emprunt ;
- délibérations et décisions des 14 derniers mois sur un emprunt ou une ligne de trésorerie (banque citée
  dans l'objet) ;
- délibérations d'adhésion à l'Agence France Locale (concurrent).

  python3 registre.py registre.json [mois=14]
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get, jget  # noqa: E402
from perimetre import norm  # noqa: E402

PLATEFORMES = {
    "Mégalis Bretagne": "https://data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search",
    "GIP RECIA (Centre-Val de Loire)": "https://data-api.publication-actes.fr/mq_apis/actes/v1/search",
}
BANQUES = [("Crédit Agricole", r"credit agricole|\bca\b (?:atlantique|anjou|finistere|morbihan|cotes|ille|centre|normandie|"
            r"touraine|loire|val de france|brie)|caisse regionale"),
           ("Banque des Territoires", r"banque des territoires|caisse des depots|\bcdc\b"),
           ("La Banque Postale", r"banque postale|\blbp\b"),
           ("Caisse d'Épargne", r"caisse d.epargne|\bcepac\b|cebpl"),
           ("Crédit Mutuel / Arkéa", r"credit mutuel|arkea|\bcmb\b|\bcmlaco\b"),
           ("Banque Populaire", r"banque populaire|\bbpgo\b|\bbred\b"),
           ("Agence France Locale", r"agence france locale|\bafl\b"),
           ("Société Générale", r"societe generale"), ("Crédit Coopératif", r"credit cooperatif"),
           ("SFIL / Caffil", r"\bsfil\b|caffil")]


def banque(texte):
    n = norm(texte)
    for nom, motif in BANQUES:
        if re.search(motif, n):
            return nom
    return None


def chercher(api, debut, fin, query=None, classification=None, lignes=100, max_pages=40):
    out, token = [], None
    for _ in range(max_pages):
        p = {"date_de_publication_debut": f"{debut}T00:00:00Z", "date_de_publication_fin": f"{fin}T23:59:59Z",
             "lignes": lignes}
        if query:
            p["query"] = query
        if classification:
            p["classifications"] = classification
        if token:
            p["page_suivante"] = token
        r = jget(api, p, tries=8, timeout=90)
        out += r.get("resultats", [])
        token = r.get("page_suivante")
        if not token or not r.get("resultats"):
            break
    return out


def emprunts_xml(xml):
    """Emprunts de l'annexe « état de la dette » d'un budget XML TOTEM."""
    s = xml.decode("utf-8", "ignore")
    nature = re.search(r'<NatDec V="(\d+)"', s)
    exer = re.search(r'<Exer V="(\d{4})"', s)
    out = []
    for b in re.findall(r"(?s)<EMPRUNT>(.*?)</EMPRUNT>", s):
        v = dict(re.findall(r'<([A-Za-z0-9_]+) V="([^"]*)"', b))
        if not v.get("MtEmprOrig"):
            continue
        out.append({"preteur": v.get("LibOrgaPreteur"), "banque": banque(v.get("LibOrgaPreteur", "")),
                    "objet": v.get("ObjEmpr"), "montant": float(v["MtEmprOrig"]),
                    "signe_le": v.get("DtSignInit"), "taux": float(v["TxActua"]) if v.get("TxActua") else None,
                    "type_taux": v.get("CodTyptxDtVote") or v.get("CodTyptxInit"),
                    "restant_du": float(v.get("MtCapitalRestDu_31_12") or v.get("MtCapitalRestDu_01_01") or 0),
                    "duree_restante": float(v["DureeRest"]) if v.get("DureeRest") else None,
                    "article": v.get("CodArticle")})
    return {"nature": nature.group(1) if nature else None, "exercice": exer.group(1) if exer else None,
            "emprunts": out}


def construire(sortie, mois=14):
    r = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "referentiel.json"), encoding="utf-8"))
    eligibles = {s: c for s, c in r["communes"].items() if (c.get("population") or 0) < 10000}
    eligibles.update({s: e for s, e in r["epcis"].items() if (e.get("population") or 0) < 20000})
    fin = date.today()
    debut = fin - timedelta(days=30 * mois)
    reg = {}
    # 1. budgets XML : le plus récent par collectivité (budget primitif ou compte financier unique)
    budgets = []
    for nom, api in PLATEFORMES.items():
        t = debut
        while t < fin:
            u = min(fin, t + timedelta(days=14))
            try:
                for a in chercher(api, t, u, classification="7.1"):
                    if a["url"].endswith(".xml") and a.get("siren") in eligibles:
                        budgets.append((nom, a))
            except Exception as e:
                print(nom, t, "ERREUR", str(e)[:80], flush=True)
            t = u + timedelta(days=1)
    par_siren = {}
    for nom, a in budgets:
        if re.search(r"annexe|lotissement|zac\b|assainissement|eau\b|ccas|spic|mouillage|camping|regie|"
                     r"photovolta|chaufferie|transport", norm(a.get("objet"))):
            continue                        # le budget principal porte l'essentiel de la dette
        par_siren.setdefault(a["siren"], []).append((nom, a))
    for v in par_siren.values():
        v.sort(key=lambda x: x[1].get("date_publication") or "", reverse=True)
    print(len(budgets), "budgets XML ;", len(par_siren), "collectivités avec un budget principal", flush=True)

    def lit(liste):
        """Le budget le plus récent qui contient l'état de la dette (3 essais au plus)."""
        vu = None
        for nom, a in liste[:3]:
            try:
                d = emprunts_xml(get(a["url"], tries=5, timeout=120))
            except Exception:
                continue
            vu = vu or (a, nom, d)
            if d["emprunts"]:
                return a, nom, d
        return vu or (liste[0][1], liste[0][0], None)

    with ThreadPoolExecutor(8) as ex:
        for a, nom, d in ex.map(lit, par_siren.values()):
            if not d:
                continue
            e = reg.setdefault(a["siren"], {"nom": eligibles[a["siren"]]["nom"], "emprunts": [], "actes": []})
            e["source_budget"] = {"plateforme": nom, "objet": a.get("objet"), "lien": a["url"],
                                  "publie_le": (a.get("date_publication") or "")[:10]}
            e["emprunts"] = sorted(d["emprunts"], key=lambda x: x.get("signe_le") or "", reverse=True)
    # 2. actes d'emprunt et de ligne de trésorerie (banque citée), adhésions à l'Agence France Locale
    for nom, api in PLATEFORMES.items():
        for q in ("emprunt", "ligne de trésorerie", "prêt", "Agence France Locale"):
            try:
                actes = chercher(api, debut, fin, query=q, max_pages=60)
            except Exception as e:
                print(nom, q, "ERREUR", str(e)[:80], flush=True)
                continue
            for a in actes:
                if a.get("siren") not in eligibles:
                    continue
                o = a.get("objet") or ""
                no = norm(o)
                if q == "Agence France Locale" and "agence france locale" not in no:
                    continue
                if q != "Agence France Locale" and not re.search(r"emprunt|pret|tresorerie", no):
                    continue
                if re.search(r"garantie|garanti", no):
                    continue
                genre = ("AFL" if "agence france locale" in no else "ligne" if "tresorerie" in no else "emprunt")
                e = reg.setdefault(a["siren"], {"nom": eligibles[a["siren"]]["nom"], "emprunts": [], "actes": []})
                if any(x["lien"] == a["url"] for x in e["actes"]):
                    continue
                e["actes"].append({"genre": genre, "date": (a.get("date_acte") or "")[:10], "objet": o[:200],
                                   "banque": banque(o), "lien": a["url"], "plateforme": nom})
    for e in reg.values():
        e["actes"].sort(key=lambda x: x["date"], reverse=True)
        b = [x["banque"] for x in e["actes"] if x.get("banque")] + [x["banque"] for x in e["emprunts"] if x.get("banque")]
        e["banques"] = sorted(set(b), key=b.index)
        e["afl"] = any(x["genre"] == "AFL" for x in e["actes"])
    json.dump({"genere": fin.isoformat(), "mois": mois, "collectivites": reg}, open(sortie, "w"),
              ensure_ascii=False, indent=0)
    print(len(reg), "collectivités dans le registre ;", sum(1 for e in reg.values() if e["emprunts"]),
          "avec l'état de la dette ;", sum(1 for e in reg.values() if e["afl"]), "adhérentes à l'Agence France Locale")


def echeances_lignes(reg, jour, jours=60):
    """Lignes de trésorerie souscrites il y a 10 à 13 mois : renouvellement attendu dans les `jours` jours.
    Seules celles dont la banque est connue (concurrent) sont signalées."""
    out = []
    for siren, e in reg.get("collectivites", {}).items():
        for x in e["actes"]:
            if x["genre"] != "ligne" or not x.get("date"):
                continue
            d = date.fromisoformat(x["date"])
            echeance = d.replace(year=d.year + 1) if not (d.month == 2 and d.day == 29) else d + timedelta(days=365)
            if 0 <= (echeance - jour).days <= jours:
                out.append({"siren": siren, "nom": e["nom"], "date": x["date"], "echeance": echeance.isoformat(),
                            "banque": x.get("banque"), "objet": x["objet"], "lien": x["lien"]})
                break
    return sorted(out, key=lambda x: x["echeance"])


if __name__ == "__main__":
    construire(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 14)
