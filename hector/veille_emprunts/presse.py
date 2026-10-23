"""Presse locale : Google News (titres, filtré par journal régional) et Bing News (titre + début d'article
+ adresse réelle de l'article), sur la fenêtre J 8h -> J+1 8h.

Ne lit jamais les sites des journaux eux-mêmes (ils refusent les outils d'IA) : seulement les flux
publics des moteurs d'actualité. L'adresse de l'article (code INSEE chez actu.fr, code postal chez
Ouest-France) sert à lever les homonymies de communes.
"""
import html
import re
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from net import jget, get
from perimetre import DEPT_NAME, norm

# Journal -> départements du périmètre qu'il couvre (None : national ou multirégional)
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
SUJETS = ["emprunt", "emprunts OR prêts", "dette OR endettement", '"conseil municipal" budget',
          '"conseil municipal" travaux', '"conseil communautaire"', "investissement commune", "finances commune",
          '"décision modificative" OR "budget supplémentaire"', '"plan de financement"', "millions d'euros travaux"]
OF_DEP = ['"conseil municipal"', "budget", "travaux"]
BING_DEP = ["emprunt commune", "emprunt conseil municipal", "recours à l'emprunt"]
BING_GEN = ["vote un emprunt commune", "souscrire un emprunt commune", "contracter un emprunt mairie",
            "emprunt de millions d'euros commune", "ligne de trésorerie commune", "consultation bancaire commune",
            "renégociation emprunt commune", "réaménagement de la dette commune", "nouvel emprunt mairie",
            "emprunt conseil communautaire"]
GOOGLE_GEN = ['emprunt commune', 'emprunt "conseil municipal"', 'emprunt "communauté de communes"',
              '"recours à l\'emprunt"', '"contracter un emprunt"', '"ligne de trésorerie"', '"consultation bancaire"',
              'endettement commune budget']

FORT = re.compile(r"\b(emprunt|emprunts|emprunter|empruntera|pret bancaire|prets?(?! (a|pour)\b)|endettement|dette|"
                  r"dettes|tresorerie|bancaire|bancaires|refinancement|renegociation)\b")
CONSEIL = re.compile(r"\b(conseil municipal|conseil communautaire|conseillers|elus|maire|budget|travaux|projet|"
                     r"chantier|renovation|construction|investissement|finances|commune|communaute de communes)\b")
MAX_CHAPEAUX = 320
PROJET = re.compile(r"\b(travaux|renovation|construction|reconstruction|amenagement|extension|rehabilitation|"
                    r"projet|chantier|equipement|investissement|investissements|programme)\b")
BUDGET = re.compile(r"\b(budget|budgets|budgetaire|finances|financement|financements|financier|financiere|"
                    r"subvention|subventions|fiscalite|impots?|taxe fonciere)\b")
MONTANT = re.compile(r"\d[\d\s.,]*\s?(?:M€|k€|€|millions? d.euros|millions? €|euros)", re.I)
NAME_STOP = {"mayenne", "loire", "cher", "indre", "eure", "orne", "manche", "vendee", "sarthe", "morbihan",
             "finistere", "calvados", "loiret", "bretagne", "normandie", "centre", "ouest", "grand", "saint",
             "sainte", "ville", "conde", "chateau", "vallee", "plaine", "fontaine", "moulins", "monts",
             "matignon", "france", "europe", "paris"}


def fold(s):
    s = unicodedata.normalize("NFKD", (s or "").replace("’", "'")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s)


def cite(texte, nom):
    """Nom présent tel quel (majuscule comprise), sans faire partie d'un nom composé plus long."""
    i = texte.find(nom)
    while i >= 0:
        av = texte[i - 1] if i > 0 else " "
        ap = texte[i + len(nom)] if i + len(nom) < len(texte) else " "
        if not (av.isalnum() or av == "-") and not (ap.isalnum() or ap == "-"):
            return True
        i = texte.find(nom, i + 1)
    return False


def index_noms(communes, epcis):
    idx = {}
    for siren, c in communes.items():
        k = fold(c["nom"])
        if len(k) >= 4 and norm(k) not in NAME_STOP:
            idx.setdefault(k, []).append(siren)
    for siren, e in epcis.items():
        k = re.sub(r"^(CC|CA|CU|Communaut. (de communes|d.agglom.ration|urbaine)) (du |de la |de l'|des |de |d')?",
                   "", fold(e["nom"]), flags=re.I)
        if len(k) >= 8 and norm(k) not in NAME_STOP:
            idx.setdefault(k, []).append(siren)
    return idx


def homonymes():
    """Nombre de communes de France portant chaque nom (pour savoir quand il faut confirmer le département)."""
    n = {}
    for c in jget("https://geo.api.gouv.fr/communes", {"fields": "nom", "format": "json"}, tries=10, timeout=90):
        k = fold(c["nom"])
        n[k] = n.get(k, 0) + 1
    return n


def _items(xml):
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def g(t, it=it):
            m = re.search(rf"<{t}[^>]*>(.*?)</{t}>", it, re.S)
            return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""
        src = re.search(r'<source url="([^"]*)"', it)
        yield g, src.group(1) if src else ""


def domaine(url):
    h = urllib.parse.urlparse(url or "").netloc.lower()
    return h[4:] if h.startswith("www.") else h


def bing(q):
    u = "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": q, "format": "rss", "setlang": "fr", "cc": "FR"}) + "&qft=sortbydate%3d%221%22"
    out = []
    for g, _ in _items(get(u, tries=4, timeout=30).decode("utf-8", "ignore")):
        lien = g("link")
        reel = urllib.parse.parse_qs(urllib.parse.urlparse(lien).query).get("url", [lien])[0]
        desc = re.sub(r"<[^>]+>", " ", g("description"))
        out.append({"titre": g("title"), "extrait": re.sub(r"\s+", " ", desc).strip(), "lien": reel,
                    "date": g("pubDate"), "media": domaine(reel), "moteur": "Bing News"})
    return out


def google(q):
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "fr", "gl": "FR", "ceid": "FR:fr"})
    out = []
    for g, src in _items(get(u, tries=4, timeout=30).decode("utf-8", "ignore")):
        t, nom = g("title"), g("source")
        if nom and t.endswith(" - " + nom):
            t = t[: -len(nom) - 3]
        out.append({"titre": t, "extrait": "", "lien": g("link"), "date": g("pubDate"),
                    "media": domaine(src) or nom, "media_nom": nom, "moteur": "Google News"})
    return out


def requetes():
    rq = []
    for dom in MEDIAS:
        rq += [("google", f"site:{dom} {s} when:2d", None) for s in SUJETS]
    for d in MEDIAS["ouest-france.fr"]:
        rq += [("google", f"site:ouest-france.fr {s} {DEPT_NAME[d]} when:2d", d) for s in OF_DEP]
    rq += [("google", f"emprunt {DEPT_NAME[d]} when:3d", d) for d in DEPT_NAME]
    # comptes rendus de conseils, tous journaux confondus, département par département
    rq += [("google", f'"conseil municipal" {DEPT_NAME[d]} when:1d', d) for d in DEPT_NAME]
    rq += [("google", f'"conseil communautaire" {DEPT_NAME[d]} when:2d', d) for d in DEPT_NAME]
    rq += [("bing", f"conseil municipal budget {DEPT_NAME[d]}", d) for d in DEPT_NAME]
    rq += [("google", q + " when:3d", None) for q in GOOGLE_GEN]
    rq += [("bing", f"{m} {DEPT_NAME[d]}", d) for d in DEPT_NAME for m in BING_DEP]
    rq += [("bing", m, None) for m in BING_GEN]
    return rq


def indices_lieu(a):
    """Départements que l'article désigne par son adresse, son journal ou son texte."""
    url = a.get("lien_article") or a["lien"]
    ins = re.search(r"actu\.fr/[a-z-]+/[a-z0-9-]+_(\d{5})/", url)
    cp = re.search(r"ouest-france\.fr/[a-z-]+/[a-z0-9-]+-(\d{5})/", url)
    d_url = (ins.group(1)[:2] if ins else None) or (cp.group(1)[:2] if cp else None)
    d_texte = {d for d, n in DEPT_NAME.items() if cite(fold(f"{a['titre']} {a['extrait']}"), fold(n))}
    d_media = MEDIAS.get(a.get("media") or "")
    return d_url, (ins.group(1) if ins else None), d_texte, d_media


def rattacher(a, idx, homo, communes, epcis):
    """Collectivités citées, en écartant les homonymes que rien ne permet de situer dans le périmètre."""
    t = fold(f"{a['titre']} {a['extrait']}")
    d_url, insee, d_texte, d_media = indices_lieu(a)
    deps = set(d_texte) | {d for d in a["departements_requete"] if d}
    retenus, doutes = [], []
    for k, sirens in idx.items():
        if not cite(t, k):
            continue
        for s in sirens:
            c = communes.get(s) or epcis.get(s)
            if insee and c.get("code_insee") == insee:
                retenus.append((s, "adresse de l'article (code INSEE)"))
            elif d_url and c["dept"] != d_url:
                doutes.append(s)
            elif d_url == c["dept"]:
                retenus.append((s, "adresse de l'article (département)"))
            elif c["dept"] in deps:
                retenus.append((s, "département cité ou recherché"))
            elif c["type"] == "EPCI" or homo.get(k, 1) <= 1:
                if d_media is None or c["dept"] in d_media:
                    retenus.append((s, "nom unique en France"))
                else:
                    doutes.append(s)
            elif d_media and c["dept"] in d_media and sum(
                    (communes.get(x) or epcis.get(x))["dept"] in d_media for x in sirens) == 1:
                retenus.append((s, "journal régional du département"))
            else:
                doutes.append(s)
    vus, out = set(), []
    for s, motif in retenus:
        if s not in vus:
            vus.add(s)
            out.append((s, motif))
    return out, sorted(set(doutes) - vus)


def ramasse(debut, fin, rq):
    """Interroge les moteurs ; renvoie les articles distincts publiés dans la fenêtre."""
    def lance(r):
        moteur, q, d = r
        for i in range(2):
            try:
                time.sleep(0.2)
                return r, (google(q) if moteur == "google" else bing(q))
            except Exception:
                time.sleep(2 + 3 * i)
        return r, None

    vus, err, n_lus = {}, 0, 0
    with ThreadPoolExecutor(4) as ex:
        for (moteur, q, d), arts in ex.map(lance, rq):
            if arts is None:
                err += 1
                continue
            for a in arts:
                n_lus += 1
                try:
                    dt = parsedate_to_datetime(a.pop("date"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    continue
                if not (debut <= dt < fin):
                    continue
                cle = norm(a["titre"])[:90]
                if cle in vus:
                    v = vus[cle]
                    v["requetes"].append(q)
                    v["departements_requete"].add(d)
                    if a["moteur"] == "Bing News" and v["moteur"] != "Bing News":
                        v.update(extrait=a["extrait"], lien_article=a["lien"], moteur="Google News + Bing News")
                    continue
                a["publie_le"] = dt.astimezone(debut.tzinfo).strftime("%Y-%m-%d %H:%M")
                a["requetes"], a["departements_requete"] = [q], {d}
                if a["moteur"] == "Bing News":
                    a["lien_article"] = a["lien"]
                vus[cle] = a
    return list(vus.values()), err, n_lus


def chapeau(a):
    """Début de l'article via Bing News (recherche du titre exact)."""
    try:
        for b in bing(f'"{a["titre"][:120]}"'):
            if norm(b["titre"])[:60] == norm(a["titre"])[:60]:
                return a, b
    except Exception:
        pass
    return a, None


def classe(a):
    texte = f"{a['titre']} {a['extrait']}"
    n = norm(texte)
    a["montants"] = sorted(set(m.strip() for m in MONTANT.findall(texte)))
    if FORT.search(n):
        return "emprunt / dette"
    if PROJET.search(n) and a["montants"]:
        return "projet chiffré"
    if BUDGET.search(n):
        return "budget / finances"
    return None


def collecte(debut, fin, communes, epcis, entite, stats, cache=None):
    """Articles publiés entre debut et fin (datetime avec fuseau) citant une collectivité du périmètre.
    Renvoie (articles rattachés, articles sur l'emprunt ou la dette sans collectivité identifiée)."""
    idx = index_noms(communes, epcis)
    try:
        homo = homonymes()
    except Exception:
        homo = {}
    rq = requetes()
    arts, err, n_lus = ramasse(debut, fin, rq) if cache is None else cache
    for a in arts:
        a["signal"] = classe(a)
        a["_cites"] = rattacher(a, idx, homo, communes, epcis)
    # Chapeau des articles qui citent une collectivité mais dont le titre seul ne dit rien des finances
    # (comptes rendus de conseil municipal, projets, travaux), et des articles financiers déjà retenus
    a_lire = [a for a in arts if not a["extrait"] and a["_cites"][0]
              and (a["signal"] or CONSEIL.search(norm(a["titre"])))][:MAX_CHAPEAUX]
    with ThreadPoolExecutor(4) as ex:
        for a, b in ex.map(chapeau, a_lire):
            if b:
                a.update(extrait=b["extrait"], lien_article=b["lien"], moteur="Google News + Bing News")
                a["signal"] = classe(a)
                a["_cites"] = rattacher(a, idx, homo, communes, epcis)
    out, orphelins, n_doute = [], [], 0
    for a in arts:
        hits, doutes = a.pop("_cites")
        a["departements_requete"] = sorted(x for x in a["departements_requete"] if x)
        if not a["signal"]:
            continue
        if not hits:
            n_doute += bool(doutes)
            if a["signal"] == "emprunt / dette" and a.get("media") in MEDIAS:
                orphelins.append(a)
            continue
        a["collectivites_citees"] = [dict(entite(s, communes, epcis), rattachement=m) for s, m in hits]
        a["homonymes_ecartes"] = doutes
        a.update(source="Presse", type_signal="article", signal_fort=a["signal"] == "emprunt / dette")
        out.append(a)
    rang = {"emprunt / dette": 0, "projet chiffré": 1, "budget / finances": 2}
    out.sort(key=lambda a: (rang[a["signal"]], a["publie_le"]))
    nb = {s: sum(a["signal"] == s for a in out) for s in rang}
    stats["Presse locale (Google News + Bing News)"] = (
        f"{len(rq)} requêtes sur {len(MEDIAS)} journaux régionaux et les moteurs ({err} en échec), "
        f"{n_lus} résultats parcourus, {len(arts)} articles distincts publiés entre le {debut:%d/%m %Hh} et le "
        f"{fin:%d/%m %Hh}, {len(a_lire)} chapeaux d'articles lus, {len(out)} citant une collectivité du périmètre : "
        f"{nb['emprunt / dette']} sur l'emprunt ou la dette, {nb['projet chiffré']} projets chiffrés, "
        f"{nb['budget / finances']} sur le budget ; {n_doute} écartés car le nom désigne aussi une commune "
        f"hors périmètre")
    return out, orphelins


def fenetre(jour, tz):
    """Du jour J à 8h au lendemain 8h (heure de Paris) : chaque article n'apparaît qu'une fois."""
    d = datetime.combine(jour, datetime.min.time(), tz) + timedelta(hours=8)
    return d, d + timedelta(days=1)
