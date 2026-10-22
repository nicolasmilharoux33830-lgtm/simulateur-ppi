"""Collecte J-1 des signaux d'emprunt des communes (<10 000 hab.) et EPCI (<20 000 hab.)
de Pays de la Loire, Bretagne, Centre-Val de Loire et Normandie.

Usage : python3 veille.py [AAAA-MM-JJ] [dossier_sortie]
Écrit candidats.json et les PDF des actes à lire dans le dossier de sortie.
"""
import json
import os
import re
import sys
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get, jget, jpost  # noqa: E402
from perimetre import DEPT2REG, DEPT_NAME, norm  # noqa: E402
from totem import emprunts  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
PLATEFORMES = {
    "Mégalis Bretagne": "https://data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search",
    "GIP RECIA (Centre-Val de Loire)": "https://data-api.publication-actes.fr/mq_apis/actes/v1/search",
}
BOAMP = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/exports/json"
ANNUAIRE = "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration/records"
TED_NUTS = ("FRG", "FRH", "FRB", "FRD")
KW_ACTE = re.compile(r"\b(emprunt|pret|prets|tresorerie|refinanc|renegoci|reamenag|banque|bancaire|"
                     r"credit agricole|credit mutuel|caisse d.epargne|caisse des depots|financement bancaire)\b")
KW_ACTE_EXCLU = re.compile(r"virement|fongibilit|subvention")
KW_TITRE = re.compile(r"\b(emprunt|emprunts|endettement|dette|dettes|financement|financements|banque|banques|"
                      r"bancaire|budget|budgets|tresorerie|investissement|investissements|prets|pret bancaire)\b")
KW_BOAMP = re.compile(r"\b(emprunt|pret|prets|financement bancaire|bancaire|credit|ligne de tresorerie|"
                      r"concours financier|refinanc)")
NEWS_QUERIES = [
    'emprunt commune', 'emprunt "conseil municipal"', 'emprunt "communauté de communes"',
    'emprunt mairie investissement', '"prêt" "conseil municipal" banque', '"ligne de trésorerie"',
    '"consultation bancaire"', '"recours à l\'emprunt"', '"contracter un emprunt"', '"souscrire un emprunt"',
    'endettement commune budget', '"plan de financement" commune travaux',
] + [f'emprunt "{n}"' for n in DEPT_NAME.values()] + [
    'financement commune "Pays de la Loire"', 'financement commune Bretagne',
    'financement commune "Centre-Val de Loire"', 'financement commune Normandie']
NAME_STOP = {"mayenne", "loire", "cher", "indre", "eure", "orne", "manche", "vendee", "sarthe", "morbihan",
             "finistere", "calvados", "loiret", "bretagne", "normandie", "centre", "ouest", "grand", "saint",
             "sainte", "ville", "conde", "chateau", "vallee", "plaine", "fontaine", "moulins", "monts"}


def jour(argv):
    if len(argv) > 1:
        return date.fromisoformat(argv[1])
    return datetime.now(PARIS).date() - timedelta(days=1)


def fenetre_utc(d):
    a = datetime.combine(d, time(0, 0), PARIS).astimezone(timezone.utc)
    b = datetime.combine(d, time(23, 59, 59), PARIS).astimezone(timezone.utc)
    return a.strftime("%Y-%m-%dT%H:%M:%SZ"), b.strftime("%Y-%m-%dT%H:%M:%SZ")


def tokens(s):
    return " " + re.sub(r"[^a-z0-9]+", " ", norm(s)).strip() + " "


# ---------- référentiel communes / EPCI du périmètre ----------
def referentiel():
    communes, epcis = {}, {}
    def dep(d):
        return d, jget(f"https://geo.api.gouv.fr/departements/{d}/communes",
                       {"fields": "nom,code,population,siren,codeEpci"}, tries=10, timeout=60)
    with ThreadPoolExecutor(5) as ex:
        for d, rows in ex.map(dep, sorted(DEPT2REG)):
            for c in rows:
                communes[c["siren"]] = {"type": "Commune", "nom": c["nom"], "code_insee": c["code"],
                                        "population": c.get("population"), "dept": d}
    for e in jget("https://geo.api.gouv.fr/epcis", {"fields": "nom,code,population,codesDepartements"},
                  tries=10, timeout=60):
        ds = [x for x in (e.get("codesDepartements") or []) if x in DEPT2REG]
        if ds:
            epcis[e["code"]] = {"type": "EPCI", "nom": e["nom"], "population": e.get("population"), "dept": ds[0]}
    return communes, epcis


def entite(siren, communes, epcis):
    e = communes.get(siren) or epcis.get(siren)
    if not e:
        return {"siren": siren, "eligible": False,
                "motif": "Hors cible : ni commune ni EPCI à fiscalité propre des 20 départements"}
    seuil = 10000 if e["type"] == "Commune" else 20000
    pop = e.get("population") or 0
    out = dict(e, siren=siren, region=DEPT2REG[e["dept"]], departement=DEPT_NAME[e["dept"]],
               annee_population="2023", eligible=pop < seuil)
    if pop >= seuil:
        out["motif"] = f"{e['type']} de {pop:,} habitants (seuil : moins de {seuil:,})".replace(",", " ")
    return out


def contacts(ent):
    out = {}
    try:
        w = (f'code_insee_commune="{ent["code_insee"]}" and pivot like "mairie"' if ent["type"] == "Commune"
             else f'siren="{ent["siren"]}"')
        r = jget(ANNUAIRE, {"where": w, "limit": 1,
                            "select": "nom,telephone,adresse_courriel,site_internet,date_modification"},
                 tries=12, timeout=25).get("results", [])
        if r:
            r = r[0]
            tel = json.loads(r["telephone"])[0]["valeur"] if r.get("telephone") else None
            site = json.loads(r["site_internet"])[0]["valeur"] if r.get("site_internet") else None
            out.update(annuaire_nom=r.get("nom"), telephone=tel, email=r.get("adresse_courriel"),
                       site=site, annuaire_maj=r.get("date_modification"))
    except Exception as e:
        out["annuaire_erreur"] = str(e)[:120]
    try:
        r = jget("https://recherche-entreprises.api.gouv.fr/search", {"q": ent["siren"], "per_page": 1},
                 tries=12, timeout=25)["results"][0]
        out["nom_officiel"] = r.get("nom_complet")
        out["nature_juridique"] = r.get("nature_juridique")
        elus = ((r.get("complements") or {}).get("collectivite_territoriale") or {}).get("elus") or []
        chef = [e for e in elus if re.match(r"(maire|pr[ée]sident)", (e.get("fonction") or "").lower())]
        if chef:
            out["elu"] = f"{chef[0].get('prenoms', '')} {chef[0].get('nom', '')}".strip().title()
            out["elu_fonction"] = chef[0].get("fonction")
    except Exception as e:
        out["rne_erreur"] = str(e)[:120]
    return out


# ---------- actes transmis en préfecture (Mégalis, RECIA) ----------
def actes_du_jour(api, d):
    a, b = fenetre_utc(d)
    out, token = [], None
    while True:
        p = {"date_de_publication_debut": a, "date_de_publication_fin": b, "lignes": 100}
        if token:
            p["page_suivante"] = token
        r = jget(api, p, tries=10, timeout=60)
        res = r.get("resultats", [])
        out += res
        token = r.get("page_suivante")
        if not res or not token or len(out) >= r.get("nb_resultats", 0) or len(out) > 5000:
            return out, r.get("nb_resultats", len(out))


def collecte_actes(d, outdir, communes, epcis, stats):
    cands = []
    for nom, api in PLATEFORMES.items():
        try:
            actes, annonces = actes_du_jour(api, d)
        except Exception as e:
            stats[nom] = f"ERREUR : {e}"
            continue
        n_bud = 0
        for a in actes:
            budget = a["url"].endswith(".xml")
            cl = a.get("classification_code") or ""
            if budget:
                n_bud += 1
                try:
                    em = emprunts(get(a["url"], tries=8, timeout=60))
                except Exception as e:
                    em = {"erreur": str(e)[:100], "total_budget": 0}
                if not em.get("total_budget"):
                    continue
                em["deja_realise"] = em.get("total_realise", 0) >= em["total_budget"]
                kind = "budget"
            elif cl.startswith("7.3") or (KW_ACTE.search(norm(a.get("objet")))
                                          and not KW_ACTE_EXCLU.search(norm(a.get("objet")))):
                em, kind = None, "acte"
            else:
                continue
            ent = entite(a["siren"], communes, epcis)
            c = {"source": nom, "type_signal": kind, "siren": a["siren"], "objet": a.get("objet"),
                 "classification": f"{cl} {a.get('classification_libelle', '')}".strip(),
                 "date_acte": (a.get("date_acte") or "")[:10], "date_publication": d.isoformat(),
                 "typologie": a.get("typologie"), "lien": a["url"],
                 "annexes": [x["url"] for x in a.get("annexes", [])], "budget_emprunt": em, "entite": ent}
            if kind == "acte" and ent.get("eligible"):
                c["pdf_locaux"] = []
                for i, u in enumerate([a["url"]] + c["annexes"]):
                    if u.lower().endswith(".pdf"):
                        fn = os.path.join(outdir, "pdf", f"{a['siren']}_{a.get('id_publication', 'x')}_{i}.pdf")
                        try:
                            open(fn, "wb").write(get(u, tries=8, timeout=90))
                            c["pdf_locaux"].append(fn)
                        except Exception:
                            pass
            cands.append(c)
        stats[nom] = f"{len(actes)} actes publiés lus (sur {annonces} annoncés), {n_bud} budgets XML analysés"
    return cands


# ---------- BOAMP ----------
def collecte_boamp(d, stats):
    deps = ",".join(f'"{x}"' for x in sorted(DEPT2REG))
    sel = "idweb,objet,code_departement,nomacheteur,dateparution,datelimitereponse,nature_libelle,url_avis"
    out = []
    try:
        jour_rows = json.loads(get(BOAMP, {"where": f"dateparution=date'{d}'", "select": sel},
                                   tries=25, timeout=60))
        ouv_rows = json.loads(get(BOAMP, {"where": f"dateparution>=date'{d - timedelta(days=90)}' and "
                                                   f"code_departement in ({deps}) and "
                                                   f"datelimitereponse>=date'{d + timedelta(days=1)}'",
                                          "select": sel}, tries=25, timeout=60))
    except Exception as e:
        stats["BOAMP"] = f"ERREUR : {e}"
        return out
    per = [r for r in jour_rows if set(r.get("code_departement") or []) & set(DEPT2REG)]
    for lot, rows in (("publié J-1", per), ("consultation encore ouverte", ouv_rows)):
        for r in rows:
            if KW_BOAMP.search(norm(r.get("objet"))):
                out.append({"source": "BOAMP", "type_signal": lot, "acheteur": r.get("nomacheteur"),
                            "objet": r.get("objet"), "departements": r.get("code_departement"),
                            "date_publication": r.get("dateparution"), "date_limite": r.get("datelimitereponse"),
                            "nature": r.get("nature_libelle"), "lien": r.get("url_avis")})
    stats["BOAMP"] = (f"{len(jour_rows)} avis publiés le {d:%d/%m} ({len(per)} dans le périmètre) ; "
                      f"{len(ouv_rows)} avis encore ouverts du périmètre contrôlés")
    return out


# ---------- TED ----------
def collecte_ted(d, stats):
    q = (f"publication-date={d:%Y%m%d} AND buyer-country=FRA AND "
         "classification-cpv IN (66113000 66110000 66100000)")
    try:
        r = jpost("https://api.ted.europa.eu/v3/notices/search",
                  {"query": q, "fields": ["publication-number", "notice-title", "buyer-name", "buyer-city",
                                          "place-of-performance", "classification-cpv"], "limit": 250},
                  tries=8, timeout=60)
    except Exception as e:
        stats["TED"] = f"ERREUR : {e}"
        return []
    out = []
    for n in r.get("notices", []):
        cpv = n.get("classification-cpv") or []
        pop = n.get("place-of-performance") or []
        if any(c.startswith("661") for c in cpv) and any(str(p).startswith(TED_NUTS) for p in pop):
            out.append({"source": "TED", "type_signal": "publié J-1", "acheteur": n.get("buyer-name"),
                        "ville": n.get("buyer-city"), "objet": (n.get("notice-title") or {}).get("fra"),
                        "lien": f"https://ted.europa.eu/fr/notice/{n.get('publication-number')}"})
    stats["TED"] = f"{len(r.get('notices', []))} avis France banque/crédit publiés le {d:%d/%m}, {len(out)} dans le périmètre"
    return out


# ---------- presse (Google News) ----------
def fold(s):
    """Sans accents, casse conservée, apostrophes typographiques unifiées."""
    s = unicodedata.normalize("NFKD", (s or "").replace("’", "'")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s)


def cite(titre_fold, nom):
    """Nom présent tel quel (majuscule comprise), sans faire partie d'un nom composé plus long."""
    i = titre_fold.find(nom)
    while i >= 0:
        avant = titre_fold[i - 1] if i > 0 else " "
        apres = titre_fold[i + len(nom)] if i + len(nom) < len(titre_fold) else " "
        if not (avant.isalnum() or avant == "-") and not (apres.isalnum() or apres == "-"):
            return True
        i = titre_fold.find(nom, i + 1)
    return False


def index_noms(communes, epcis):
    idx = {}
    for siren, c in communes.items():
        k = fold(c["nom"])
        if len(k) >= 5 and norm(k) not in NAME_STOP:
            idx.setdefault(k, []).append(siren)
    for siren, e in epcis.items():
        k = re.sub(r"^(CC|CA|CU|Communaut. (de communes|d.agglom.ration|urbaine)) (du |de la |de l'|des |de |d')?",
                   "", fold(e["nom"]), flags=re.I)
        if len(k) >= 8 and norm(k) not in NAME_STOP:
            idx.setdefault(k, []).append(siren)
    return idx


def collecte_presse(d, communes, epcis, stats):
    idx = index_noms(communes, epcis)
    vus, out, n_items = set(), [], 0
    for q in NEWS_QUERIES:
        u = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": q + " when:2d", "hl": "fr", "gl": "FR", "ceid": "FR:fr"})
        try:
            s = get(u, tries=6, timeout=40).decode("utf-8", "ignore")
        except Exception:
            continue
        for it in re.findall(r"<item>(.*?)</item>", s, re.S):
            n_items += 1
            titre = re.sub(r"<!\[CDATA\[|\]\]>", "", re.search(r"<title>(.*?)</title>", it, re.S).group(1))
            lien = re.search(r"<link>(.*?)</link>", it, re.S).group(1)
            pub = re.search(r"<pubDate>(.*?)</pubDate>", it).group(1)
            src = re.search(r"<source[^>]*>(.*?)</source>", it)
            try:
                dt = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=timezone.utc).astimezone(PARIS)
            except ValueError:
                continue
            if dt.date() != d or titre in vus:
                continue
            vus.add(titre)
            if not KW_TITRE.search(norm(titre)):
                continue
            t = fold(titre)
            hits = sorted({s2 for k, sirens in idx.items() if cite(t, k) for s2 in sirens})
            if hits:
                out.append({"source": "Presse (Google News)", "type_signal": "article", "titre": titre,
                            "media": src.group(1) if src else None, "date_publication": dt.strftime("%Y-%m-%d %H:%M"),
                            "lien": lien, "collectivites_citees": [entite(x, communes, epcis) for x in hits]})
    stats["Presse (Google News)"] = (f"{len(NEWS_QUERIES)} requêtes, {n_items} articles parcourus, "
                                     f"{len(vus)} publiés le {d:%d/%m}, {len(out)} citant une collectivité du périmètre")
    return out


def fiche(siren):
    """Fiche vérifiée d'une collectivité (pour un acheteur BOAMP/TED ou un article de presse)."""
    communes, epcis = referentiel()
    e = entite(siren, communes, epcis)
    if e.get("eligible") or e.get("type"):
        e["contacts"] = contacts(e)
    return e


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--fiche":
        print(json.dumps(fiche(sys.argv[2]), ensure_ascii=False, indent=1))
        return
    d = jour(sys.argv)
    outdir = sys.argv[2] if len(sys.argv) > 2 else f"veille_{d}"
    os.makedirs(os.path.join(outdir, "pdf"), exist_ok=True)
    stats = {}
    communes, epcis = referentiel()
    stats["Référentiel"] = f"{len(communes)} communes et {len(epcis)} EPCI dans les 20 départements (INSEE)"
    with ThreadPoolExecutor(4) as ex:
        f_actes = ex.submit(collecte_actes, d, outdir, communes, epcis, stats)
        f_boamp = ex.submit(collecte_boamp, d, stats)
        f_ted = ex.submit(collecte_ted, d, stats)
        f_presse = ex.submit(collecte_presse, d, communes, epcis, stats)
        actes, boamp, ted, presse = f_actes.result(), f_boamp.result(), f_ted.result(), f_presse.result()
    res = {"jour": d.isoformat(), "genere": datetime.now(PARIS).isoformat(timespec="minutes"),
           "couverture": stats, "actes": actes, "boamp": boamp, "ted": ted, "presse": presse,
           "non_couvert": "Pays de la Loire et Normandie : pas de plateforme publique des actes connue ; "
                          "couverts par BOAMP, TED et presse uniquement.",
           "note": "Contacts fournis pour les actes éligibles ; pour une piste BOAMP, TED ou presse retenue, "
                   "lancer : python3 veille.py --fiche SIREN"}
    chemin = os.path.join(outdir, "candidats.json")
    json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=1)
    elig = [c for c in actes if c["entite"].get("eligible")]
    with ThreadPoolExecutor(8) as ex:
        for c, ct in zip(elig, ex.map(lambda c: contacts(c["entite"]), elig)):
            c["contacts"] = ct
    json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"jour": res["jour"], "couverture": stats,
                      "actes_candidats": len(actes), "actes_eligibles": sum(c["entite"].get("eligible", False) for c in actes),
                      "boamp": len(boamp), "ted": len(ted), "presse": len(presse)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
