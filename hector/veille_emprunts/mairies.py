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
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta, timezone
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
# Ce qui annonce un conseil à venir : là qu'on lit « choix de l'organisme bancaire », « emprunt » avant le vote
PRIO = re.compile(r"convocation|ordres?[- _]du[- _]jour|\bodj\b|prochain[- _]conseil|prochaine[- _]seance|"
                  r"seance[- _]du[- _]conseil|reunion[- _]du[- _]conseil|note[- _]de[- _]synthese|"
                  r"note[- _]explicative")
SECOND = re.compile(r"agenda|bulletin|magazine|journal[- _](?:municipal|communal|communautaire|d.information)|"
                    r"lettre[- _](?:municipale|d.info)|infos?[- _]municipales?|actualites?")
PAGE = re.compile(PAGE.pattern + "|" + PRIO.pattern + "|" + SECOND.pattern)
DOC = re.compile(r"\.(pdf|docx?|odt)(\?|#|$)", re.I)
EXCLU = re.compile(r"facebook|twitter|instagram|linkedin|youtube|mailto:|tel:|javascript:|\.(jpe?g|png|gif|svg|zip|mp4)(\?|$)",
                   re.I)
MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
# Ce qui fait d'un document une piste : un emprunt nouveau, une consultation des banques
EMPRUNT = re.compile(r"(recours a l.emprunt|contracter un (?:emprunt|pret)|souscrire un (?:emprunt|pret)|"
                     r"souscription d.un (?:emprunt|pret)|realisation d.un (?:emprunt|pret)|nouvel emprunt|"
                     r"(?:emprunt|pret) (?:de|d.un montant de) (?:\d{1,3}(?:[ .]\d{3})+|\d+(?:[.,]\d+)? ?(?:k|m|millions?|euros?)\b)|"
                     r"(?:emprunt|pret) aupres|"
                     r"offres? de (?:pret|financement)|consultation (?:bancaire|des banques|des etablissements|"
                     r"d.organismes|aupres)|etablissements (?:bancaires|de credit|financiers)|"
                     r"organismes? (?:bancaires?|preteurs?)|ligne de tresorerie|pret[- ]relais|preteur|"
                     r"financement bancaire|contrat de pret(?! a usage)(?! de \d+ (?:oeuvre|objet|tableau))|refinancement|"
                     r"renegociation d|reamenagement de (?:la )?dette)")
CONTEXTE = 260
DOC_EXCLU = re.compile(r"\bcfu|compte financier|compte administratif|budget primitif|\bbp ?\d|"
                       r"presentation (?:sommaire|breve)|rapport financier|rpqs|rapport annuel|\barrete|\bmenu|"
                       r"cantine|\btarif|urbanisme|\bplu\b|enquete publique")
BUDGET_DOC = re.compile(r"budget|decision modificative|\bdm\b|emprunt|pret|financement|orientation")


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
    try:
        port = p.port
    except ValueError:
        port = None
    netloc = hote + (f":{port}" if port else "")
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
        if EXCLU.search(href) or "{{" in href or "[" in href or " id=" in href:
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
    try:
        return _plan_site(siren, info)
    except Exception as e:
        return {"siren": siren, "site": info["site"], "pages": [], "etat": f"erreur ({str(e)[:60]})"}


def _plan_site(siren, info):
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
            cands[u] = max(cands.get(u, 0), score_page(cle))
    # un niveau de plus pour les rubriques (« Vie municipale » -> « Conseil municipal » -> « Délibérations »)
    premiers = sorted(cands, key=lambda u: -cands[u])[:8]
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
                if PRIO.search(cle) or FORT_PAGE.search(cle) or SECOND.search(cle):
                    cands[v] = max(cands.get(v, 0), score_page(cle) - 1)
    out["pages"] = sorted(cands, key=lambda u: -cands[u])[:12]
    out["prio"] = [u for u in out["pages"] if cands[u] >= 5]
    return out


def score_page(cle):
    """Convocations et ordres du jour d'abord, puis délibérations et comptes rendus, puis agenda et bulletins."""
    if PRIO.search(cle):
        return 6
    if FORT_PAGE.search(cle):
        return 4
    if SECOND.search(cle):
        return 3
    return 1


def plan(sites_json, chemin, fils=64):
    sites = json.load(open(sites_json))
    res = {}
    with ThreadPoolExecutor(fils) as ex:
        for i, p in enumerate(ex.map(lambda kv: plan_site(*kv), sites.items())):
            res[p["siren"]] = p
            if i % 250 == 0:
                print(i, flush=True)
                json.dump(res, open(chemin + ".part", "w"), ensure_ascii=False)
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
    n = re.sub(r"/20\d\d/\d\d/", "/", n)          # dossier de dépôt WordPress, pas une date de séance
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
    for j, m, a in re.findall(r"\b([0-2]?\d|3[01])[._-](0?[1-9]|1[0-2])[._-](2[0-9])\b(?![./_-]?\d)", n):
        out.append((2000 + int(a), int(m), int(j)))
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
        import logging
        import warnings
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.CRITICAL)
        warnings.filterwarnings("ignore")
    except Exception:
        return None
    try:
        r = PdfReader(io.BytesIO(b))
        return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in r.pages[:40]))
    except Exception:
        return ""


def plat(texte):
    """Texte sans accents ni majuscules, de même longueur que l'original (positions conservées)."""
    out = []
    for ch in texte:
        a = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode().lower()
        out.append(a[:1] if a else " ")
    return "".join(out)


def extraits(texte, jour=None, fenetre=45):
    """Passages sur un emprunt ; avec jour, seulement ceux qui ont une date récente à proximité
    (une page liste souvent des délibérations de plusieurs années)."""
    n = plat(texte)
    out, mots, fin, recentes = [], set(), -1, []
    for m in EMPRUNT.finditer(n):
        if jour is not None:
            proches = [d for d in dates(texte[max(0, m.start() - 700):m.end() + 300])
                       if jour - timedelta(days=fenetre) <= d <= jour + timedelta(days=30)]
            if not proches:
                continue
            recentes += proches
        mots.add(m.group(1))
        if m.start() < fin:
            continue
        a, b = max(0, m.start() - CONTEXTE), min(len(texte), m.end() + CONTEXTE)
        out.append(texte[a:b].strip())
        fin = b
        if len(out) >= 4:
            break
    if jour is not None:
        return out, sorted(mots), recentes
    return out, sorted(mots)


def scan_site(p, jour, recent_jours=3, fenetre_seance=45):
    """Documents récents des pages utiles d'un site, avec les passages sur un emprunt."""
    try:
        return _scan_site(p, jour, recent_jours, fenetre_seance)
    except Exception as e:
        return {"siren": p["siren"], "etat": f"erreur ({str(e)[:60]})", "docs_vus": 0, "docs_recents": 0, "pistes": []}


def _scan_site(p, jour, recent_jours, fenetre_seance):
    res = {"siren": p["siren"], "etat": "ok", "docs_vus": 0, "docs_recents": 0, "pistes": []}
    if not p.get("pages"):
        res["etat"] = "sans page utile"
        return res
    # les pages de convocation et d'ordre du jour d'abord, puis les meilleures pages du plan
    pages = list(dict.fromkeys(p.get("prio", []) + p["pages"]))[:8]
    docs, vus = [], set()
    for page in pages:
        try:
            u, ctype, b, _ = lire(page, essais=2)
        except Refus as e:
            res["etat"] = f"refus ({e})"
            break
        except Exception:
            continue
        if "html" not in ctype:
            continue
        # la page elle-même (annonces de séance, ordres du jour et comptes rendus en ligne)
        t = texte_html(b)
        ex, mots, recentes = extraits(t, jour, fenetre_seance)
        if ex and recentes:
            res["pistes"].append({"type": "page", "url": u, "titre": None, "date_seance": max(recentes).isoformat(),
                                  "mis_en_ligne": None, "mots": mots, "extraits": ex,
                                  "convocation": bool(PRIO.search(norm(f"{u} {t[:400]}")))})
        for v, txt, autour in liens(u, b):
            if v in vus or not DOC.search(v):
                continue
            vus.add(v)
            res["docs_vus"] += 1
            cle = norm(f"{txt} {urllib.parse.unquote(v)}")
            if DOC_EXCLU.search(re.sub(r"[^a-z0-9]+", " ", cle)):
                continue
            ds = [d for d in dates(f"{txt} {v}") or dates(autour) if d <= jour + timedelta(days=30)]
            seance = max(ds) if ds else None
            if seance and seance < jour - timedelta(days=fenetre_seance):
                continue
            dossier = re.search(r"/(20\d\d)/(0[1-9]|1[0-2])/", v)        # /uploads/2026/10/ des sites WordPress
            if dossier and (int(dossier.group(1)), int(dossier.group(2))) < ((jour - timedelta(days=40)).year,
                                                                         (jour - timedelta(days=40)).month):
                continue
            rang = 0 if PRIO.search(cle) else 1 if BUDGET_DOC.search(cle) else 2
            docs.append((rang, -(seance.toordinal() if seance else 0), v, txt, u, seance, dossier))
    # convocations et ordres du jour, puis budgets et emprunts, puis le reste ; les plus récents d'abord
    docs.sort(key=lambda x: x[:2])
    n_head, n_get = 0, 0
    for rang, _, v, txt, u, seance, dossier in docs:
        # date de mise en ligne demandée au serveur (HEAD), sans télécharger le document
        n_head += 1
        if n_head > 30:
            break
        try:
            _, _, _, lm = lire(v, methode="HEAD", timeout=12, essais=2)
        except Exception:
            lm = None
        mise = recent(lm, jour, 3650)
        mois_depot = dossier and (int(dossier.group(1)), int(dossier.group(2))) == (jour.year, jour.month)
        neuf = (mise and jour - timedelta(days=recent_jours) <= mise <= jour + timedelta(days=1)) or \
               (not mise and seance and (seance >= jour - timedelta(days=recent_jours) or mois_depot))
        # un ordre du jour d'un conseil à venir se lit même s'il a été mis en ligne il y a plus de 3 jours
        neuf = neuf or (rang == 0 and seance and seance >= jour)
        if not neuf:
            continue
        n_get += 1
        if n_get > 8:
            break
        try:
            v2, ct, bd, lm2 = lire(v, max_octets=12_000_000, timeout=40, essais=2)
        except Exception:
            continue
        res["docs_recents"] += 1
        est_pdf = "pdf" in ct or v2.lower().split("?")[0].endswith(".pdf") or bd[:4] == b"%PDF"
        tx = texte_pdf(bd) if est_pdf else None
        piste = {"type": "document", "url": v2, "page": u, "titre": txt[:160] or None,
                 "date_seance": seance.isoformat() if seance else None,
                 "mis_en_ligne": mise.isoformat() if mise else None, "convocation": rang == 0}
        cle = norm(f"{txt} {urllib.parse.unquote(v2)}")
        if not tx:
            # scan, format non lu ou pypdf absent : OCR après le passage sur tous les sites, sinon Hector le lit
            if rang < 2 or FORT_PAGE.search(cle):
                piste.update(mots=[], extraits=[], a_lire=True)
                if est_pdf and DOSSIER_OCR:
                    fn = os.path.join(DOSSIER_OCR, f"{p['siren']}_{abs(hash(v2)) % 10**10}.pdf")
                    try:
                        open(fn, "wb").write(bd)
                        piste["fichier"] = fn
                    except OSError:
                        pass
                res["pistes"].append(piste)
            continue
        ex, mots = extraits(tx)
        if rang == 1 or "1641" in tx:
            ex += lignes_budget(bd)
            if ex and not mots:
                mots = ["compte 1641"]
        if ex:
            piste.update(mots=mots, extraits=ex[:5])
            if not seance:
                ds = dates(tx[:1500])
                piste["date_seance"] = max(ds).isoformat() if ds else None
            res["pistes"].append(piste)
    return res


DOSSIER_OCR = None          # dossier où garder les scans à passer à l'OCR (fixé par veille.py)


def lignes_budget(octets, ocr=False):
    """Lignes d'emprunt nouveau d'un document budgétaire (compte 1641 en recettes), au format des extraits."""
    try:
        import budgets_pdf
    except ImportError:
        return []
    textes, _, _ = budgets_pdf.pages_texte(octets, ocr=ocr)
    out = []
    for h in budgets_pdf.lignes_emprunt(textes):
        if h["cote"] in ("recette", "inconnu") and max(h["montants"]) >= 1000:
            out.append(f"[budget, page {h['page']}, {h['cote']}] {h['ligne']}")
    return out[:3]


def ocr_pistes(pistes, duree_max=480, stats=None):
    """Passe à l'OCR les documents scannés des sites ; garde ceux qui parlent d'emprunt ou de banque,
    écarte ceux qui n'en parlent pas, laisse « à lire » ceux que l'OCR n'a pas pu lire."""
    try:
        import budgets_pdf
    except ImportError:
        return pistes
    a_ocr = [x for x in pistes if x.get("a_lire") and x.get("fichier")]
    if not a_ocr or not budgets_pdf.moteur_ocr():
        return pistes
    t0, ecartes, lus = time.time(), set(), 0

    def un(x):
        if time.time() - t0 > duree_max:
            return x, None
        try:
            textes, faits, _ = budgets_pdf.pages_texte(open(x["fichier"], "rb").read(), max_ocr=3)
        except Exception:
            return x, None
        return x, (textes if faits else None)

    with ThreadPoolExecutor(3) as ex:
        for x, textes in ex.map(un, a_ocr):
            if textes is None:
                continue
            lus += 1
            brut = re.sub(r"\s+", " ", " ".join(textes))
            exs, mots = extraits(brut)
            for h in budgets_pdf.lignes_emprunt(textes):
                if h["cote"] in ("recette", "inconnu") and max(h["montants"]) >= 1000:
                    exs.append(f"[budget, page {h['page']}, {h['cote']}] {h['ligne']}")
            if exs:
                x.update(extraits=exs[:5], mots=mots or ["compte 1641"], a_lire=False, ocr=True)
                if not x.get("date_seance"):
                    ds = dates(brut[:1500])
                    x["date_seance"] = max(ds).isoformat() if ds else None
            else:
                ecartes.add(id(x))
    if stats is not None:
        stats["OCR des scans des sites"] = (f"{len(a_ocr)} documents scannés, {lus} lus par OCR "
                                            f"({round(time.time() - t0)} s), {len(ecartes)} sans emprunt ni banque écartés, "
                                            f"{sum(1 for x in a_ocr if x.get('ocr'))} retenus")
    return [x for x in pistes if id(x) not in ecartes]


def scan(plan_json, jour, communes, epcis, entite, stats, fils=160, duree_max=1500, priorite=None, ocr_max=480):
    """Lit les pages utiles de chaque site, les meilleurs scores d'abord ; s'arrête proprement après duree_max
    secondes, puis passe les documents scannés à l'OCR (ocr_max secondes au plus)."""
    from concurrent.futures import FIRST_COMPLETED, wait
    p = json.load(open(plan_json)) if isinstance(plan_json, str) else plan_json
    # sites avec des pages utiles, communes éligibles seulement (le plan ne contient qu'elles),
    # dans l'ordre de la probabilité d'emprunt : si le temps manque, ce sont les moins probables qui attendent
    sites = [x for x in p.values() if x.get("pages")]
    priorite = priorite or {}
    sites.sort(key=lambda x: -priorite.get(x["siren"], 0))
    t0 = time.time()
    out, etats, n_docs, n_rec, n_fini = [], {}, 0, 0, 0
    ex = ThreadPoolExecutor(fils)
    en_cours = {ex.submit(scan_site, x, jour) for x in sites}
    while en_cours:
        faits, en_cours = wait(en_cours, timeout=30, return_when=FIRST_COMPLETED)
        for f in faits:
            r = f.result()
            n_fini += 1
            k = r["etat"].split(" ")[0]
            etats[k] = etats.get(k, 0) + 1
            n_docs += r["docs_vus"]
            n_rec += r["docs_recents"]
            for piste in r["pistes"]:
                piste.update(source="Site de la collectivité", type_signal="site internet",
                             siren=r["siren"], entite=entite(r["siren"], communes, epcis))
                out.append(piste)
        if time.time() - t0 > duree_max:
            for f in en_cours:
                f.cancel()
            break
    ex.shutdown(wait=False, cancel_futures=True)
    reste = len(sites) - n_fini
    n_scans = sum(1 for x in out if x.get("a_lire"))
    out = ocr_pistes(out, duree_max=ocr_max, stats=stats)
    stats["Sites des mairies et EPCI"] = (
        f"{n_fini} sites lus sur {len(sites)} ayant une page délibérations, conseil ou marchés "
        f"({etats.get('refus', 0)} refus du site{f', {reste} non lus faute de temps' if reste else ''}), "
        f"{n_docs} documents listés, {n_rec} récents ouverts (séance de moins de 45 jours, mis en ligne "
        f"depuis 3 jours), {len(out)} parlant d'emprunt ou de banque ou à lire, dont "
        f"{sum(1 for x in out if x.get('convocation'))} convocations ou ordres du jour "
        f"({n_scans} scans avant OCR ; {round(time.time() - t0)} s)")
    return out


# ---------- 5. Sites absents de l'annuaire ----------
def _formes(nom):
    """Écritures possibles d'un nom de commune dans une adresse (« Le Champ-Saint-Père » -> champsaintpere...)."""
    n = re.sub(r"[^a-z0-9 -]", " ", norm(nom).replace("'", " "))
    mots = [m for m in re.split(r"[\s-]+", n) if m]
    sans_article = mots[1:] if len(mots) > 1 and mots[0] in ("le", "la", "les", "l") else mots
    st = [("st" if m == "saint" else "ste" if m == "sainte" else m) for m in mots]
    out = ["".join(mots), "-".join(mots), "".join(sans_article), "-".join(sans_article), "".join(st), "-".join(st)]
    return list(dict.fromkeys(f for f in out if len(f) >= 3))


def _candidats(nom, dept):
    formes = _formes(nom)
    out = [f"https://www.{formes[0]}.fr/"]
    for f in formes[:5]:
        out += [f"https://{f}.fr/", f"https://www.mairie-{f}.fr/", f"https://{f}{dept}.fr/",
                f"https://www.commune-{f}.fr/", f"https://www.mairie{f}.fr/"]
        if DEPT2REG.get(dept) == "Bretagne":
            out.append(f"https://{f}.bzh/")
    return list(dict.fromkeys(out))


def _valide(b, nom, cps, dept):
    t = norm(texte_html(b)[:60000]).replace("-", " ").replace("'", " ")
    n = norm(nom).replace("-", " ").replace("'", " ")
    if n not in t or not re.search(r"\bmairie\b|\bcommune\b|conseil municipal|hotel de ville", t):
        return False
    if any(cp in t for cp in cps):
        return True
    from perimetre import DEPT_NAME
    return bool(re.search(r"(mairie|commune|ville) d[e'u ]+\s?" + re.escape(n), t)) and \
        (f"({dept})" in t or norm(DEPT_NAME.get(dept, "@")).replace("-", " ") in t)


def _existe(hote):
    """Le nom de domaine existe-t-il ? (DNS sur HTTPS : évite d'attendre une connexion vers un domaine qui n'existe pas)"""
    for essai in range(3):
        try:
            req = urllib.request.Request(f"https://cloudflare-dns.com/dns-query?name={hote}&type=A",
                                         headers={"accept": "application/dns-json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
            return d.get("Status") == 0 and bool(d.get("Answer"))
        except Exception:
            time.sleep(1 + essai)
    return True                     # en cas de doute, on essaie la connexion


def decouvrir(sites_json, fils=48):
    """Cherche le site des communes éligibles absentes de l'annuaire (adresses usuelles), le valide
    (nom de la commune, « mairie », code postal sur la page) et l'ajoute à sites.json."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import veille
    from net import jget
    communes, _ = veille.referentiel()
    sites = json.load(open(sites_json))
    cps = {}
    for d in sorted(DEPT2REG):
        for c in jget(f"https://geo.api.gouv.fr/departements/{d}/communes", {"fields": "code,codesPostaux"},
                      tries=10, timeout=60):
            cps[c["code"]] = c.get("codesPostaux") or []
    sans = [(s, c) for s, c in communes.items() if (c.get("population") or 0) < 10000 and s not in sites]
    print(len(sans), "communes éligibles sans site dans l'annuaire", flush=True)

    def un(sc):
        s, c = sc
        for u in _candidats(c["nom"], c["dept"]):
            if not _existe(urllib.parse.urlparse(u).netloc):
                continue
            try:
                base, ctype, b, _ = lire(u, max_octets=600_000, timeout=8, essais=1)
            except Exception:
                continue
            if "html" in ctype and _valide(b, c["nom"], cps.get(c["code_insee"], []), c["dept"]):
                return s, {"nom": c["nom"], "type": "Commune", "dept": c["dept"], "site": base, "decouvert": True}
        return s, None

    trouves = 0
    with ThreadPoolExecutor(fils) as ex:
        for i, (s, info) in enumerate(ex.map(un, sans)):
            if info:
                sites[s] = info
                trouves += 1
            if i % 200 == 0:
                print(i, trouves, flush=True)
    json.dump(sites, open(sites_json, "w"), ensure_ascii=False, indent=0)
    print(trouves, "sites trouvés")
    return trouves


if __name__ == "__main__":
    if sys.argv[1] == "--annuaire":
        annuaire(sys.argv[2])
    elif sys.argv[1] == "--decouvrir":
        decouvrir(sys.argv[2])
    elif sys.argv[1] == "--plan":
        plan(sys.argv[2], sys.argv[3])
