"""Sites internet des mairies et des intercommunalités du périmètre.

Depuis le 1er juillet 2022, les communes publient leurs actes (délibérations, procès-verbaux, liste des
délibérations du conseil) sur leur site internet : c'est la source la plus complète là où il n'existe pas
de registre public des actes (Pays de la Loire, Normandie). Les mairies y publient aussi leurs
consultations et leurs avis d'appel public à la concurrence.

Le robot se présente sous son nom (USER_AGENT), respecte le fichier robots.txt de chaque site et ne
force aucune protection : un site qui refuse est noté « refus » et laissé de côté.

  python3 mairies.py --annuaire sites.json             liste des sites (Annuaire de l'administration)
  python3 mairies.py --plan sites.json plan.json       repère sur chaque site les pages délibérations, conseil, marchés
  (dans veille.py) scan(plan, jour, ...)               documents récents de ces pages, lus et filtrés
"""
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get  # noqa: E402
from perimetre import DEPT2REG, norm  # noqa: E402

USER_AGENT = "Mozilla/5.0 (compatible; HectorVeille/1.0; veille des actes publics des collectivites)"
ANNUAIRE = "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration"
# Pages à suivre depuis l'accueil (texte du lien ou adresse)
PAGE = re.compile(r"deliber|conseil[- _]?municipal|conseil[- _]?communautaire|compte[- _]?rendu|proces[- _]?verba|"
                  r"\bpv\b|seances?\b|actes?[- _](administratif|reglementaire)|recueil[- _]des[- _]actes|"
                  r"publication[- _]des[- _]actes|registre|marches?[- _]publics?|appels?[- _]d[- _']?offres?|"
                  r"consultations?\b|avis[- _]d[- _']?appel|vie[- _]municipale|vie[- _]communautaire|"
                  r"budget|finances|conseil\b|mairie")
FORT_PAGE = re.compile(r"deliber|compte[- _]?rendu|proces[- _]?verba|conseil[- _]?municipal|conseil[- _]?communautaire|"
                       r"\bpv\b|actes|marches?[- _]publics|appels?[- _]d")
DOC = re.compile(r"\.(pdf|docx?|odt)(\?|#|$)", re.I)
EXCLU = re.compile(r"facebook|twitter|instagram|linkedin|youtube|mailto:|tel:|javascript:|\.(jpe?g|png|gif|svg|zip|mp4)(\?|$)",
                   re.I)
MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
# Ce qui fait d'un document une piste : un emprunt nouveau, une consultation des banques
EMPRUNT = re.compile(r"(recours a l.emprunt|contracter un (emprunt|pret)|souscrire un (emprunt|pret)|"
                     r"realisation d.un (emprunt|pret)|nouvel emprunt|emprunt (de|d.un montant)|pret (de|d.un montant)|"
                     r"offres? de (pret|financement)|consultation (bancaire|des banques|des etablissements)|"
                     r"etablissements (bancaires|de credit|financiers)|organismes? bancaires?|"
                     r"ligne de tresorerie|pret relais|pret[- ]relais|preteur|financement bancaire|"
                     r"banque des territoires|caisse d.epargne|credit agricole|credit mutuel|banque postale|"
                     r"arkea|caisse des depots|refinancement|renegociation|reamenagement)")
CONTEXTE = 260


class Refus(Exception):
    pass


# ---------- 1. Annuaire ----------
def _site(v):
    try:
        return json.loads(v)[0]["valeur"].strip() if v else None
    except (ValueError, KeyError, IndexError):
        return None


def annuaire(chemin):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import veille
    communes, epcis = veille.referentiel()
    insee = {c["code_insee"]: (s, c) for s, c in communes.items() if (c.get("population") or 0) < 10000}
    out = {}
    for d in sorted(DEPT2REG):
        for piv, cle in (("mairie", "code_insee_commune"), ("epci", "siren")):
            cache = f"{chemin}.{piv}{d}.part"
            if os.path.exists(cache):
                rows = json.load(open(cache))
            else:
                rows = json.loads(get(f"{ANNUAIRE}/exports/json",
                                      {"where": f'pivot like "{piv}" and startswith(code_insee_commune,"{d}")',
                                       "select": "nom,code_insee_commune,site_internet,siren"}, tries=40, timeout=120))
                json.dump(rows, open(cache, "w"))
            for r in rows:
                site = _site(r.get("site_internet"))
                if not site:
                    continue
                if piv == "mairie" and r.get("code_insee_commune") in insee:
                    s, c = insee[r["code_insee_commune"]]
                    if "deleguee" in norm(r.get("nom")):
                        continue
                    out.setdefault(s, {"nom": c["nom"], "type": "Commune", "dept": c["dept"], "site": site})
                elif piv == "epci" and r.get("siren") in epcis and (epcis[r["siren"]].get("population") or 0) < 20000:
                    e = epcis[r["siren"]]
                    out.setdefault(r["siren"], {"nom": e["nom"], "type": "EPCI", "dept": e["dept"], "site": site})
        print(d, len(out), flush=True)
    json.dump(out, open(chemin, "w"), ensure_ascii=False, indent=0)
    for f in os.listdir(os.path.dirname(os.path.abspath(chemin))):
        if f.startswith(os.path.basename(chemin) + ".") and f.endswith(".part"):
            os.remove(os.path.join(os.path.dirname(os.path.abspath(chemin)), f))
    return out


# ---------- 2. Accès poli ----------
_robots = {}


def autorise(url):
    p = urllib.parse.urlparse(url)
    hote = f"{p.scheme}://{p.netloc}"
    if hote not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        for i in range(3):
            try:
                req = urllib.request.Request(hote + "/robots.txt", headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=10) as r:
                    rp.parse(r.read(200000).decode("utf-8", "ignore").splitlines())
                break
            except urllib.error.HTTPError as e:
                rp.parse([] if e.code < 500 else ["User-agent: *", "Disallow: /"])
                break
            except Exception:
                rp.parse([])
                time.sleep(1 + i)
        _robots[hote] = rp
    return _robots[hote].can_fetch(USER_AGENT, url)


def ascii_url(url):
    """Adresse utilisable par urllib : domaine accentué en punycode, chemin encodé."""
    p = urllib.parse.urlsplit(url.strip())
    try:
        hote = p.hostname.encode("idna").decode() if p.hostname else ""
    except UnicodeError:
        hote = p.hostname or ""
    netloc = hote + (f":{p.port}" if p.port else "")
    chemin = urllib.parse.quote(p.path, safe="/%:@!$&'()*+,;=-._~")
    requete = urllib.parse.quote(p.query, safe="=&%/:+,;-._~")
    return urllib.parse.urlunsplit((p.scheme, netloc, chemin, requete, ""))


def lire(url, max_octets=3_000_000, timeout=15, methode="GET", essais=3):
    """(adresse finale, type, octets, date de modification) ; Refus si robots.txt ou le site refuse."""
    url = ascii_url(url)
    if not autorise(url):
        raise Refus("robots.txt")
    dernier = None
    for i in range(essais):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fr"}, method=methode)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read(max_octets) if methode == "GET" else b""
                lm = r.headers.get("Last-Modified")
                return r.geturl(), r.headers.get("Content-Type", ""), b, lm
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429, 503):
                raise Refus(f"HTTP {e.code}")
            raise
        except Exception as e:      # coupure réseau : on réessaie
            dernier = e
            time.sleep(1 + 2 * i)
    raise dernier


def texte_html(b):
    s = b.decode("utf-8", "ignore")
    s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)))


def liens(base, b):
    s = b.decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'(?is)<a\b[^>]*href\s*=\s*["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', s):
        href, txt = html.unescape(m.group(1)).strip(), html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))
        if EXCLU.search(href) or "{{" in href:
            continue
        u = urllib.parse.urljoin(base, href)
        if u.startswith("http"):
            # le texte autour du lien (titre de la séance, date)
            autour = re.sub(r"<[^>]+>", " ", s[max(0, m.start() - 300):m.start()])
            out.append((u, re.sub(r"\s+", " ", txt).strip(), html.unescape(re.sub(r"\s+", " ", autour)).strip()[-160:]))
    return out


def meme_site(a, b):
    ha, hb = urllib.parse.urlparse(a).netloc.lower(), urllib.parse.urlparse(b).netloc.lower()
    ra, rb = ".".join(ha.split(".")[-2:]), ".".join(hb.split(".")[-2:])
    return ra == rb


# ---------- 3. Plan : les pages utiles de chaque site ----------
def plan_site(siren, info):
    out = {"siren": siren, "site": info["site"], "pages": [], "etat": "ok"}
    try:
        base, ctype, b, _ = lire(info["site"])
    except Refus as e:
        out["etat"] = f"refus ({e})"
        return out
    except Exception as e:
        out["etat"] = f"injoignable ({str(e)[:60]})"
        return out
    out["site"] = base
    cands = {}
    for u, txt, _ in liens(base, b):
        if not meme_site(u, base) or DOC.search(u):
            continue
        cle = norm(f"{txt} {urllib.parse.unquote(u)}")
        if PAGE.search(cle):
            score = 3 if FORT_PAGE.search(cle) else 1
            cands[u] = max(cands.get(u, 0), score)
    # un niveau de plus pour les rubriques (« Vie municipale » -> « Conseil municipal » -> « Délibérations »)
    premiers = sorted(cands, key=lambda u: -cands[u])[:6]
    for u in premiers:
        try:
            u2, ctype, b2, _ = lire(u)
        except Exception:
            continue
        if "html" not in ctype:
            continue
        for v, txt, _ in liens(u2, b2):
            if meme_site(v, base) and not DOC.search(v):
                cle = norm(f"{txt} {urllib.parse.unquote(v)}")
                if FORT_PAGE.search(cle):
                    cands[v] = max(cands.get(v, 0), 2)
    out["pages"] = sorted(cands, key=lambda u: -cands[u])[:10]
    return out


def plan(sites_json, chemin, fils=64):
    sites = json.load(open(sites_json))
    res = {}
    with ThreadPoolExecutor(fils) as ex:
        for i, p in enumerate(ex.map(lambda kv: plan_site(*kv), sites.items())):
            res[p["siren"]] = p
            if i % 250 == 0:
                print(i, flush=True)
    json.dump(res, open(chemin, "w"), ensure_ascii=False, indent=0)
    etats = {}
    for p in res.values():
        k = p["etat"].split(" ")[0]
        etats[k] = etats.get(k, 0) + 1
    print(json.dumps(etats), sum(1 for p in res.values() if p["pages"]), "sites avec pages utiles")
    return res


# ---------- 4. Scan du jour ----------
def dates(s):
    """Dates écrites dans un texte ou une adresse (titre de séance, nom de fichier)."""
    n = norm(urllib.parse.unquote(s))
    out = []
    for j, m, a in re.findall(r"\b(\d{1,2})(?:er)?[ _-]+(" + "|".join(MOIS) + r")[ _-]+(20\d\d)\b", n):
        out.append((int(a), MOIS[m], int(j)))
    for j, m, a in re.findall(r"\b(\d{1,2})[./_-](\d{1,2})[./_-](20\d\d)\b", n):
        out.append((int(a), int(m), int(j)))
    for a, m, j in re.findall(r"\b(20\d\d)[./_-](\d{1,2})[./_-](\d{1,2})\b", n):
        out.append((int(a), int(m), int(j)))
    for a, m, j in re.findall(r"\b(20[2-3]\d)(0[1-9]|1[0-2])([0-2]\d|3[01])\b", n):
        out.append((int(a), int(m), int(j)))
    for j, m, a in re.findall(r"\b([0-2]\d|3[01])(0[1-9]|1[0-2])(20[2-3]\d)\b", n):
        out.append((int(a), int(m), int(j)))
    res = []
    for a, m, j in out:
        try:
            res.append(date(a, m, j))
        except ValueError:
            pass
    return res


def recent(lm, jour, jours):
    """Date de mise en ligne (en-tête Last-Modified) si elle tombe dans les `jours` derniers jours, sinon None."""
    if not lm:
        return None
    try:
        d = parsedate_to_datetime(lm).astimezone(timezone.utc).date()
    except (TypeError, ValueError):
        return None
    return d if jour - timedelta(days=jours) <= d <= jour + timedelta(days=1) else None


def texte_pdf(b):
    try:
        from pypdf import PdfReader
    except Exception:
        return None
    try:
        r = PdfReader(io.BytesIO(b))
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in r.pages[:40]))
    except Exception:
        return ""


def extraits(texte):
    n = norm(texte)
    out, fin = [], -1
    for m in EMPRUNT.finditer(n):
        if m.start() < fin:
            continue
        a, b = max(0, m.start() - CONTEXTE), min(len(texte), m.end() + CONTEXTE)
        out.append(texte[a:b].strip())
        fin = b
        if len(out) >= 4:
            break
    return out, sorted({m.group(1) for m in EMPRUNT.finditer(n)})


def scan_site(p, jour, recent_jours=3, fenetre_seance=45):
    """Documents récents des pages utiles d'un site, avec les passages sur un emprunt."""
    res = {"siren": p["siren"], "etat": "ok", "docs_vus": 0, "docs_recents": 0, "pistes": []}
    if not p.get("pages"):
        res["etat"] = "sans page utile"
        return res
    vus, n_head, n_get = set(), 0, 0
    for page in p["pages"][:8]:
        try:
            u, ctype, b, _ = lire(page)
        except Refus as e:
            res["etat"] = f"refus ({e})"
            break
        except Exception:
            continue
        if "html" not in ctype:
            continue
        # la page elle-même (annonces de séance, comptes rendus en ligne)
        t = texte_html(b)
        ex, mots = extraits(t)
        recentes = [d for d in dates(t) if jour - timedelta(days=fenetre_seance) <= d <= jour]
        if ex and recentes:
            res["pistes"].append({"type": "page", "url": u, "titre": None, "date_seance": max(recentes).isoformat(),
                                  "mis_en_ligne": None, "mots": mots, "extraits": ex})
        for v, txt, autour in liens(u, b):
            if v in vus or not DOC.search(v):
                continue
            vus.add(v)
            res["docs_vus"] += 1
            ds = [d for d in dates(f"{txt} {v}") or dates(autour) if d <= jour + timedelta(days=1)]
            seance = max(ds) if ds else None
            if seance and seance < jour - timedelta(days=fenetre_seance):
                continue
            if not seance:
                # sans date lisible : on demande seulement la date de mise en ligne (HEAD), dans la limite de 40
                n_head += 1
                if n_head > 40:
                    continue
                try:
                    _, _, _, lm = lire(v, methode="HEAD", timeout=12)
                except Exception:
                    continue
                if not recent(lm, jour, recent_jours):
                    continue
            n_get += 1
            if n_get > 15:
                break
            try:
                v2, ct, bd, lm = lire(v, max_octets=25_000_000, timeout=40)
            except Exception:
                continue
            mise = recent(lm, jour, 3650)
            dossier = re.search(r"/(20\d\d)/(0[1-9]|1[0-2])/", v2)       # /uploads/2026/10/ des sites WordPress
            mois_depot = dossier and (int(dossier.group(1)), int(dossier.group(2))) == (jour.year, jour.month)
            neuf = (mise and jour - timedelta(days=recent_jours) <= mise <= jour + timedelta(days=1)) or \
                   (not mise and seance and (seance >= jour - timedelta(days=recent_jours) or mois_depot))
            if not neuf:
                continue
            res["docs_recents"] += 1
            if "pdf" in ct or v2.lower().split("?")[0].endswith(".pdf") or bd[:4] == b"%PDF":
                tx = texte_pdf(bd)
            else:
                tx = None
            piste = {"type": "document", "url": v2, "page": u, "titre": txt[:160] or None,
                     "date_seance": seance.isoformat() if seance else None,
                     "mis_en_ligne": mise.isoformat() if mise else None}
            if tx is None or (tx == "" and bd[:4] == b"%PDF"):
                piste.update(mots=[], extraits=[], a_lire=True)   # scan ou format non lu : Hector le lit
                res["pistes"].append(piste)
                continue
            ex, mots = extraits(tx)
            if ex:
                piste.update(mots=mots, extraits=ex)
                if not seance:
                    ds = dates(tx[:1500])
                    piste["date_seance"] = max(ds).isoformat() if ds else None
                res["pistes"].append(piste)
    return res


def scan(plan_json, jour, communes, epcis, entite, stats, fils=48):
    p = json.load(open(plan_json)) if isinstance(plan_json, str) else plan_json
    t0 = time.time()
    out, etats, n_docs, n_rec = [], {}, 0, 0
    with ThreadPoolExecutor(fils) as ex:
        for r in ex.map(lambda x: scan_site(x, jour), p.values()):
            k = r["etat"].split(" ")[0]
            etats[k] = etats.get(k, 0) + 1
            n_docs += r["docs_vus"]
            n_rec += r["docs_recents"]
            for piste in r["pistes"]:
                piste.update(source="Site de la collectivité", type_signal="site internet",
                             siren=r["siren"], entite=entite(r["siren"], communes, epcis))
                out.append(piste)
    stats["Sites des mairies et EPCI"] = (
        f"{len(p)} sites parcourus ({etats.get('ok', 0)} lus, {etats.get('refus', 0)} refus du site, "
        f"{etats.get('sans', 0)} sans page délibérations ou marchés), {n_docs} documents listés, "
        f"{n_rec} récents ouverts (séance de moins de 45 jours, mis en ligne depuis 3 jours), {len(out)} parlant "
        f"d'emprunt ou de banque ou à lire "
        f"({round(time.time() - t0)} s)")
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--annuaire":
        annuaire(sys.argv[2])
    elif sys.argv[1] == "--plan":
        plan(sys.argv[2], sys.argv[3])
