"""Collecte J-1 des signaux d'emprunt des communes (<10 000 hab.) et EPCI (<20 000 hab.)
de Pays de la Loire, Bretagne, Centre-Val de Loire et Normandie.

Usage : python3 veille.py [AAAA-MM-JJ] [dossier_sortie] [--sans-sites]
Écrit candidats.json et les PDF des actes à lire dans le dossier de sortie.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get, jget, jpost  # noqa: E402
from perimetre import DEPT2REG, DEPT_NAME, norm  # noqa: E402
from totem import emprunts  # noqa: E402
try:
    import imminence  # noqa: E402
except ImportError:          # fichier absent : pas d'échéances, le reste de la veille tourne
    imminence = None
import budgets_pdf  # noqa: E402
import facebook  # noqa: E402
import mairies  # noqa: E402
import marches  # noqa: E402
import panneaupocket  # noqa: E402
import presse  # noqa: E402

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
KW_ACTE_EXCLU = re.compile(r"virement|fongibilit|subvention|pret d.honneur|pret de (materiel|salle|vehicule|local)|"
                           r"mise a disposition|arrete (permanent|temporaire)|circulation|permis de construire")
KW_ROB = re.compile(r"\b(orientations? budgetaires?|debat d.orientation|rapport d.orientation|rob|dob)\b")
TEXTE_INTEGRAL = ["emprunt", "emprunts", "prêt", "prêts", "bancaire", "banque"]
AGE_MAX = 45
MAX_FICHES = 80
KW_BOAMP = re.compile(r"\b(emprunt|pret|prets|financement bancaire|bancaire|credit|ligne de tresorerie|"
                      r"concours financier|refinanc)")


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
    """Communes et EPCI des 20 départements (geo.api.gouv.fr) ; copie de secours referentiel.json si l'API coupe."""
    secours = os.path.join(os.path.dirname(os.path.abspath(__file__)), "referentiel.json")
    try:
        communes, epcis = {}, {}

        def dep(d):
            return d, jget(f"https://geo.api.gouv.fr/departements/{d}/communes",
                           {"fields": "nom,code,population,siren,codeEpci"}, tries=25, timeout=60)
        with ThreadPoolExecutor(5) as ex:
            for d, rows in ex.map(dep, sorted(DEPT2REG)):
                for c in rows:
                    communes[c["siren"]] = {"type": "Commune", "nom": c["nom"], "code_insee": c["code"],
                                            "population": c.get("population"), "dept": d}
        for e in jget("https://geo.api.gouv.fr/epcis", {"fields": "nom,code,population,codesDepartements"},
                      tries=25, timeout=60):
            ds = [x for x in (e.get("codesDepartements") or []) if x in DEPT2REG]
            if ds:
                epcis[e["code"]] = {"type": "EPCI", "nom": e["nom"], "population": e.get("population"), "dept": ds[0]}
        return communes, epcis
    except Exception:
        r = json.load(open(secours, encoding="utf-8"))
        return r["communes"], r["epcis"]


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


# ---------- comptes officiels (OFGL) ----------
OFGL = "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets"
INDIC = {"Encours de dette": "encours", "Annuité de la dette": "annuite", "Epargne brute": "epargne_brute",
         "Epargne nette": "epargne_nette", "Recettes de fonctionnement": "recettes_fonctionnement",
         "Dépenses d'équipement": "depenses_equipement", "Emprunts hors GAD": "emprunts_annee",
         "Dépôts au Trésor": "tresorerie", "Fonds de roulement": "fonds_roulement",
         "Capacité ou besoin de financement": "capacite_financement"}


def finances(ent, budget_nom=None):
    """Derniers comptes publiés (tous budgets) et, si besoin, ceux du budget annexe concerné."""
    commune = ent.get("type") == "Commune"
    ds = "ofgl-base-communes-consolidee" if commune else "ofgl-base-gfp-consolidee"
    cle = f'com_code="{ent.get("code_insee")}"' if commune else f'epci_code="{ent["siren"]}"'
    an0 = datetime.now(PARIS).year - 1
    try:
        for an in (an0, an0 - 1):
            ex = f"year(exer)={an}"
            rows = jget(f"{OFGL}/{ds}/records", {"where": f"{cle} and {ex}", "limit": 100,
                                                  "select": "agregat,montant,euros_par_habitant"},
                        tries=12, timeout=40).get("results", [])
            if rows:
                break
        else:
            return {"erreur": "comptes non publiés"}
        f = {"annee": an, "source": "OFGL, comptes de gestion tous budgets"}
        for r in rows:
            k = INDIC.get(r["agregat"])
            if k:
                f[k] = r["montant"]
                f[k + "_hab"] = r.get("euros_par_habitant")
        eb, enc, rrf = f.get("epargne_brute"), f.get("encours"), f.get("recettes_fonctionnement")
        if eb and eb > 0 and enc is not None:
            f["desendettement_ans"] = round(enc / eb, 1)
        if eb is not None and rrf:
            f["taux_epargne_brute"] = round(100 * eb / rrf, 1)
        mots = [m for m in re.findall(r"[a-z]{5,}", norm(budget_nom or ""))
                if m not in ("budget", "annexe", "principal", "commune", "collectivite")
                and m not in norm(ent.get("nom", ""))]
        if commune and mots:
            try:
                rows = jget(f"{OFGL}/ofgl-base-communes/records",
                            {"where": f"{cle} and year(exer)={an} and type_de_budget=\"Budget annexe\"",
                             "limit": 100, "select": "lbudg,agregat,montant"},
                            tries=12, timeout=40).get("results", [])
                ann = {}
                for r in rows:
                    if any(m[:6] in norm(r["lbudg"]) for m in mots) and r["agregat"] in INDIC:
                        ann["budget"] = r["lbudg"]
                        ann[INDIC[r["agregat"]]] = r["montant"]
                if ann:
                    f["budget_annexe"] = ann
            except Exception:
                f["budget_annexe"] = {"erreur": "détail du budget annexe indisponible"}
        return f
    except Exception as e:
        return {"erreur": str(e)[:120]}


def a_paris(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(PARIS).strftime("%Y-%m-%d %H:%M")
    except (ValueError, AttributeError):
        return iso


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


def plein_texte(api, d):
    """Actes du jour dont le texte (et pas seulement l'objet) contient un mot du financement bancaire."""
    a, b = fenetre_utc(d)
    out = {}
    for q in TEXTE_INTEGRAL:
        try:
            r = jget(api, {"date_de_publication_debut": a, "date_de_publication_fin": b, "lignes": 100, "query": q},
                     tries=6, timeout=60)
        except Exception:
            continue
        for x in r.get("resultats", []):
            out.setdefault(x["url"], (x, q))
    return out


def ecart_budget(em):
    """Motif d'écart d'un document budgétaire, ou None si c'est un emprunt nouveau voté maintenant."""
    if em.get("natdec") in ("Budget primitif", "Compte administratif"):
        return f"{em['natdec']} : prévision ou bilan, pas une décision d'emprunt nouvelle"
    if em.get("total_vote", 0) <= 0:
        return "Aucun emprunt nouveau voté dans cette décision (montant reporté du budget primitif)"
    if em.get("total_realise", 0) >= em.get("total_budget", 0) > 0:
        return "Emprunt de l'année déjà encaissé"
    return None


def age(date_acte, d):
    try:
        return (d - date.fromisoformat(date_acte[:10])).days
    except (TypeError, ValueError):
        return None


def collecte_actes(d, outdir, communes, epcis, stats):
    cands = []
    for nom, api in PLATEFORMES.items():
        try:
            actes, annonces = actes_du_jour(api, d)
        except Exception as e:
            stats[nom] = f"ERREUR : {e}"
            continue
        texte = plein_texte(api, d)
        n_bud, n_txt, n_bp, n_vieux = 0, 0, 0, 0
        for a in actes:
            budget = a["url"].endswith(".xml")
            cl = a.get("classification_code") or ""
            o = norm(a.get("objet"))
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
            elif cl.startswith("7.3") or (KW_ACTE.search(o) and not KW_ACTE_EXCLU.search(o)):
                em, kind = None, "acte"
            elif KW_ROB.search(o):
                em, kind = None, "orientations budgétaires"
            elif a["url"] in texte and not KW_ACTE_EXCLU.search(o):
                em, kind = None, "acte (mot trouvé dans le texte)"
                n_txt += 1
            else:
                continue
            ent = entite(a["siren"], communes, epcis)
            c = {"source": nom, "type_signal": kind, "siren": a["siren"], "objet": a.get("objet"),
                 "classification": f"{cl} {a.get('classification_libelle', '')}".strip(),
                 "date_acte": (a.get("date_acte") or "")[:10], "date_publication": d.isoformat(),
                 "publie_le": a_paris(a.get("date_publication")), "id_publication": a.get("id_publication"),
                 "typologie": a.get("typologie"), "lien": a["url"],
                 "annexes": [x["url"] for x in a.get("annexes", [])], "budget_emprunt": em, "entite": ent}
            if a["url"] in texte:
                c["mot_texte_integral"] = texte[a["url"]][1]
            c["age_jours"] = age(c["date_acte"], d)
            if kind == "budget":
                c["motif_ecart"] = ecart_budget(em)
                n_bp += bool(c["motif_ecart"])
            elif c["age_jours"] is not None and c["age_jours"] > AGE_MAX and kind != "orientations budgétaires":
                c["motif_ecart"] = f"Décision du {c['date_acte']} ({c['age_jours']} jours) : publiée tardivement, besoin ancien"
                n_vieux += 1
            if kind != "budget" and not c.get("motif_ecart") and ent.get("eligible"):
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
        n_annexes = sum(len(a.get("annexes") or []) for a in actes)
        bpdf = budgets_en_pdf(actes, cands, d, outdir, communes, epcis, nom)
        stats[nom] = (f"{len(actes)} actes publiés lus avec leurs {n_annexes} annexes ({annonces} documents annoncés), "
                      f"{n_bud} budgets XML analysés "
                      f"({n_bp} écartés : budget primitif, compte administratif ou aucun emprunt nouveau), "
                      f"{bpdf}, "
                      f"{len(texte)} actes trouvés en texte intégral ({n_txt} de plus que par leur objet), "
                      f"{n_vieux} décisions de plus de {AGE_MAX} jours écartées")
    return cands


def telecharge_pdf(a, outdir, n_max=4):
    """Document principal et annexes PDF d'un acte : (chemins locaux, contenus)."""
    chemins, contenus = [], []
    for i, u in enumerate(([a["url"]] + [x["url"] for x in a.get("annexes", [])])[:n_max]):
        if not u.lower().endswith(".pdf"):
            continue
        fn = os.path.join(outdir, "pdf", f"{a['siren']}_{a.get('id_publication', 'x')}_{i}.pdf")
        try:
            b = open(fn, "rb").read() if os.path.exists(fn) else get(u, tries=6, timeout=90)
            if not os.path.exists(fn):
                open(fn, "wb").write(b)
            chemins.append(fn)
            contenus.append(b)
        except Exception:
            pass
    return chemins, contenus


def budgets_en_pdf(actes, cands, d, outdir, communes, epcis, nom):
    """Décisions modificatives et budgets supplémentaires publiés seulement en PDF (souvent scannés) :
    lecture ligne à ligne de l'emprunt inscrit en recettes (compte 1641), annexes comprises, OCR si besoin.
    Les actes d'emprunt (7.3) scannés reçoivent aussi leur texte OCR, pour être triés sans être ouverts."""
    deja = {c["lien"]: c for c in cands}
    a_lire = []
    for a in actes:
        if a["url"].endswith(".xml"):
            continue
        cl, o = a.get("classification_code") or "", norm(a.get("objet"))
        budget = cl.startswith("7.1") and budgets_pdf.OBJET_BUDGET.search(o) and not budgets_pdf.OBJET_EXCLU.search(o)
        emprunt_scanne = a["url"] in deja and not deja[a["url"]].get("motif_ecart") and \
            deja[a["url"]]["type_signal"] == "acte"
        if not (budget or emprunt_scanne):
            continue
        ent = entite(a["siren"], communes, epcis)
        if not ent.get("eligible"):
            continue
        if age((a.get("date_acte") or "")[:10], d) is not None and age((a.get("date_acte") or "")[:10], d) > AGE_MAX:
            continue
        a_lire.append((a, ent, bool(budget)))

    def un(item):
        a, ent, budget = item
        chemins, contenus = telecharge_pdf(a, outdir)
        if not contenus:
            return item, chemins, None, None
        res = budgets_pdf.analyse(contenus, ocr=True, max_ocr=4) if budget else None
        texte = None
        if not budget:
            textes, faits, _ = budgets_pdf.pages_texte(contenus[0], max_pages=3, max_ocr=2)
            if faits:
                texte = re.sub(r"\s+", " ", " ".join(textes))[:1500]
        return item, chemins, res, texte

    n_bud, n_ocr, n_pistes = 0, 0, 0
    with ThreadPoolExecutor(4) as ex:
        for (a, ent, budget), chemins, res, texte in ex.map(un, a_lire):
            c = deja.get(a["url"])
            if texte and c is not None:
                c["texte_ocr"] = texte
            if not budget:
                continue
            n_bud += 1
            n_ocr += bool(res and res["pages_ocr"])
            if not res or not res["force"]:
                continue
            n_pistes += 1
            if c is None:
                c = {"source": nom, "type_signal": "budget (PDF)", "siren": a["siren"], "objet": a.get("objet"),
                     "classification": f"{a.get('classification_code', '')} {a.get('classification_libelle', '')}".strip(),
                     "date_acte": (a.get("date_acte") or "")[:10], "date_publication": d.isoformat(),
                     "publie_le": a_paris(a.get("date_publication")), "id_publication": a.get("id_publication"),
                     "typologie": a.get("typologie"), "lien": a["url"],
                     "annexes": [x["url"] for x in a.get("annexes", [])], "budget_emprunt": None, "entite": ent,
                     "age_jours": age((a.get("date_acte") or "")[:10], d)}
                cands.append(c)
            c["budget_pdf"] = res
            c["pdf_locaux"] = chemins
    return (f"{n_bud} décisions budgétaires en PDF analysées ligne à ligne ({n_ocr} scannées lues par OCR), "
            f"{n_pistes} avec un emprunt en recettes")


# ---------- BOAMP ----------
def collecte_boamp(d, communes, epcis, stats):
    idx = marches.index_acheteurs(communes, epcis)
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
                siren = marches.rattacher(r.get("nomacheteur"), r.get("code_departement"), idx)
                out.append({"source": "BOAMP", "type_signal": lot, "acheteur": r.get("nomacheteur"),
                            "objet": r.get("objet"), "departements": r.get("code_departement"),
                            "date_publication": r.get("dateparution"), "date_limite": r.get("datelimitereponse"),
                            "nature": r.get("nature_libelle"), "lien": r.get("url_avis"),
                            "entite": entite(siren, communes, epcis) if siren else
                            {"eligible": False, "motif": "Acheteur non rattaché à une commune ou un EPCI du périmètre"}})
    stats["BOAMP"] = (f"{len(jour_rows)} avis publiés le {d:%d/%m} ({len(per)} dans le périmètre) ; "
                      f"{len(ouv_rows)} avis encore ouverts du périmètre contrôlés")
    return out


def collecte_echeances(d, communes, epcis, stats):
    """Délibérations d'emprunt et de ligne de trésorerie des 14 derniers mois (Mégalis, RECIA) : échéances
    attendues autour de leur date anniversaire, et collectivités qui viennent déjà d'emprunter."""
    if imminence is None:
        return [], {}
    try:
        actes = imminence.historique(PLATEFORMES, (d - timedelta(days=430)).isoformat(), d.isoformat())
    except Exception as e:
        stats["Échéances (historique des emprunts)"] = f"ERREUR : {e}"
        return [], {}
    ech = (imminence.echeances(actes, d, communes, epcis, entite, "ligne")
           + imminence.echeances(actes, d, communes, epcis, entite, "emprunt"))
    recents = {}
    for a in actes:
        if imminence.type_acte(a["objet"]) in ("emprunt", "ligne") and a["date_acte"] >= (d - timedelta(days=75)).isoformat():
            recents.setdefault(a["siren"], []).append({"date": a["date_acte"], "objet": a["objet"], "lien": a["url"]})
    stats["Échéances (historique des emprunts)"] = (
        f"{len(actes)} délibérations d'emprunt et de trésorerie des 14 derniers mois relues (Mégalis, RECIA), "
        f"{sum(e['genre'] == 'ligne' for e in ech)} lignes de trésorerie et {sum(e['genre'] == 'emprunt' for e in ech)} "
        f"emprunts arrivant à leur date anniversaire")
    return ech, recents


def collecte_travaux(d, communes, epcis, stats, jours=90):
    """Marchés de travaux lancés par les communes et EPCI éligibles ces 90 derniers jours (BOAMP) :
    un chantier engagé appelle un financement dans les mois qui suivent."""
    idx = marches.index_acheteurs(communes, epcis)
    deps = ",".join(f'"{x}"' for x in sorted(DEPT2REG))
    try:
        rows = json.loads(get(BOAMP, {"where": f'dateparution>=date\'{d - timedelta(days=jours)}\' and '
                                                f'dateparution<=date\'{d}\' and nature="APPEL_OFFRE" and '
                                                f'type_marche="TRAVAUX" and code_departement in ({deps})',
                                       "select": "idweb,dateparution,nomacheteur,famille,code_departement,objet,url_avis"},
                              tries=25, timeout=120))
    except Exception as e:
        stats["BOAMP travaux"] = f"ERREUR : {e}"
        return {}
    out = {}
    for r in rows:
        siren = marches.rattacher(r.get("nomacheteur"), r.get("code_departement"), idx)
        e = entite(siren, communes, epcis) if siren else {}
        if e.get("eligible"):
            out.setdefault(siren, []).append({"date": r.get("dateparution"), "objet": r.get("objet"),
                                              "taille": {"MAPA": "moins de 90 k€", "FNS": "90 k€ à 5,5 M€",
                                                         "JOUE": "plus de 5,5 M€"}.get(r.get("famille"), ""),
                                              "lien": r.get("url_avis")})
    for v in out.values():
        v.sort(key=lambda x: x["date"] or "", reverse=True)
    stats["BOAMP travaux"] = (f"{len(rows)} marchés de travaux publiés en {jours} jours dans les 20 départements, "
                              f"{sum(len(v) for v in out.values())} lancés par {len(out)} communes ou EPCI éligibles")
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


def fiche(siren):
    """Fiche vérifiée d'une collectivité (pour un acheteur BOAMP/TED ou un article de presse)."""
    communes, epcis = referentiel()
    e = entite(siren, communes, epcis)
    if e.get("eligible") or e.get("type"):
        e["contacts"] = contacts(e)
        e["finances"] = finances(e)
    return e


def historique(siren, mois=6):
    """Actes des derniers mois d'une collectivité sur l'emprunt, le prêt ou la trésorerie (Mégalis, RECIA) :
    sert à vérifier qu'aucune banque n'est déjà retenue avant de garder un A ou un B."""
    communes, epcis = referentiel()
    e = entite(siren, communes, epcis)
    fin = datetime.now(PARIS).date()
    debut = fin - timedelta(days=30 * mois)
    vus = {}
    for nom, api in PLATEFORMES.items():
        for mot in ("emprunt", "prêt", "trésorerie", "bancaire"):
            try:
                r = jget(api, {"date_de_publication_debut": f"{debut}T00:00:00Z",
                               "date_de_publication_fin": f"{fin}T23:59:59Z",
                               "lignes": 100, "query": f"{e.get('nom', '')} {mot}"}, tries=4, timeout=60)
            except Exception:
                continue
            for a in r.get("resultats", []):
                if a.get("siren") == siren:
                    vus.setdefault(a["url"], {"date_acte": (a.get("date_acte") or "")[:10], "plateforme": nom,
                                              "classification": a.get("classification_code"),
                                              "objet": a.get("objet"), "lien": a["url"]})
    return {"siren": siren, "nom": e.get("nom"), "depuis": debut.isoformat(),
            "actes": sorted(vus.values(), key=lambda a: a["date_acte"], reverse=True)}


def priorite_sites(epcis):
    """Ordre de lecture des sites : les intercommunalités, puis les communes les plus probables (scores.csv)."""
    import csv
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.csv")
    out = {}
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter=";"):
                try:
                    out[r["siren"]] = max(float(r.get("proba") or 0), float(r.get("proba_annee_suivante") or 0))
                except ValueError:
                    pass
    for s in epcis:
        out[s] = out.get(s, 0) + 1.0
    return out


def scores(sirens):
    """Probabilité d'emprunt dans l'année (modele.py) pour les collectivités retenues."""
    import csv
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.csv")
    if not os.path.exists(chemin):
        return {}
    with open(chemin, encoding="utf-8") as f:
        return {r["siren"]: r for r in csv.DictReader(f, delimiter=";") if r["siren"] in sirens}


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--fiche":
        print(json.dumps(fiche(sys.argv[2]), ensure_ascii=False, indent=1))
        return
    if len(sys.argv) > 2 and sys.argv[1] == "--historique":
        print(json.dumps(historique(sys.argv[2]), ensure_ascii=False, indent=1))
        return
    sans_sites = "--sans-sites" in sys.argv     # le lundi, les sites ne sont lus qu'une fois (fenêtre de 3 jours)
    argv = [a for a in sys.argv if a != "--sans-sites"]
    d = jour(argv)
    outdir = argv[2] if len(argv) > 2 else f"veille_{d}"
    os.makedirs(os.path.join(outdir, "pdf"), exist_ok=True)
    stats = {}
    communes, epcis = referentiel()
    stats["Référentiel"] = f"{len(communes)} communes et {len(epcis)} EPCI dans les 20 départements (INSEE)"
    debut, fin = presse.fenetre(d, PARIS)
    plan = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan_sites.json")
    with ThreadPoolExecutor(12) as ex:
        f_actes = ex.submit(collecte_actes, d, outdir, communes, epcis, stats)
        f_boamp = ex.submit(collecte_boamp, d, communes, epcis, stats)
        f_trav = ex.submit(collecte_travaux, d, communes, epcis, stats)
        f_ech = ex.submit(collecte_echeances, d, communes, epcis, stats)
        f_ted = ex.submit(collecte_ted, d, stats)
        f_presse = ex.submit(presse.collecte, debut, fin, communes, epcis, entite, stats)
        f_marches = ex.submit(marches.collecte, d, communes, epcis, entite, stats)
        mairies.DOSSIER_OCR = os.path.join(outdir, "scans")
        os.makedirs(mairies.DOSSIER_OCR, exist_ok=True)
        f_sites = (ex.submit(mairies.scan, plan, d, communes, epcis, entite, stats, priorite=priorite_sites(epcis))
                   if os.path.exists(plan) and not sans_sites else None)
        pp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panneaupocket.json")
        f_pp = (ex.submit(panneaupocket.scan, pp, d, communes, epcis, entite, stats, 3, 16, 900,
                         priorite_sites(epcis))
                if os.path.exists(pp) and not sans_sites else None)
        # Facebook : fils republiés par les mairies sur leur site, et API officielle de Meta si un jeton existe
        rs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reseaux.json")
        f_fb = ([ex.submit(facebook.flux_sites, rs, d, communes, epcis, entite, stats, 3),
                 ex.submit(facebook.api_meta, rs, d, communes, epcis, entite, stats, 3)]
                if os.path.exists(rs) and not sans_sites else [])
        actes, boamp, ted, travaux = f_actes.result(), f_boamp.result(), f_ted.result(), f_trav.result()
        echeances, recents = f_ech.result()
        (articles, orphelins), consultations = f_presse.result(), f_marches.result()
        sites = (f_sites.result() if f_sites else []) + (f_pp.result() if f_pp else [])
        for f in f_fb:
            sites += f.result()
    res = {"jour": d.isoformat(), "genere": datetime.now(PARIS).isoformat(timespec="minutes"),
           "fenetre_presse": f"{debut:%Y-%m-%d %H:%M} -> {fin:%Y-%m-%d %H:%M}",
           "couverture": stats, "actes": actes, "consultations": consultations, "boamp": boamp, "ted": ted,
           "presse": articles, "presse_sans_collectivite": orphelins, "sites": sites, "travaux": travaux,
           "echeances": echeances, "emprunts_recents": recents,
           "non_couvert": "Pays de la Loire et Normandie : pas de plateforme publique des actes connue ; "
                          "couverts par les sites des mairies, les appels d'offres, la presse locale et le modèle.",
           "note": "Fiches (contacts, comptes, probabilité) dans 'fiches' ; pour une autre collectivité : "
                   "python3 veille.py --fiche SIREN"}
    chemin = os.path.join(outdir, "candidats.json")
    json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=1)

    # Fiches des collectivités éligibles à vérifier (actes retenus d'abord, puis appels d'offres, puis presse)
    pistes = {}
    for c in actes:
        if c["entite"].get("eligible") and not c.get("motif_ecart"):
            pistes.setdefault(c["siren"], (c["entite"], (c.get("budget_emprunt") or {}).get("budget")))
    for c in consultations + boamp + sites:
        e = c.get("entite") or {}
        if e.get("eligible"):
            pistes.setdefault(e["siren"], (e, None))
    for a in articles:
        for e in a["collectivites_citees"]:
            if e.get("eligible"):
                pistes.setdefault(e["siren"], (e, None))
    pistes = dict(list(pistes.items())[:MAX_FICHES])

    def enrichir(item):
        siren, (e, bud) = item
        return siren, {"contacts": contacts(e), "finances": finances(e, bud)}

    with ThreadPoolExecutor(8) as ex:
        res["fiches"] = dict(ex.map(enrichir, pistes.items()))
    proba = scores(set(res["fiches"]) | {e["siren"] for a in articles for e in a["collectivites_citees"]})
    for siren, p in proba.items():
        res["fiches"].setdefault(siren, {})["prediction"] = p
    for c in actes:
        f = res["fiches"].get(c["siren"], {})
        if "contacts" in f:
            c["contacts"], c["finances"] = f["contacts"], f["finances"]
    json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=1)
    retenus = [c for c in actes if c["entite"].get("eligible") and not c.get("motif_ecart")]
    print(json.dumps({"jour": res["jour"], "couverture": stats, "actes_candidats": len(actes),
                      "actes_eligibles_retenus": len(retenus),
                      "consultations": len(consultations), "boamp": len(boamp), "ted": len(ted),
                      "presse": len(articles), "sites": len(sites), "travaux": len(travaux),
                      "fiches": len(res["fiches"])}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
