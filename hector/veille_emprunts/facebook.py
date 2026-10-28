"""Publications Facebook des communes et EPCI éligibles, par deux voies autorisées seulement :

1. Le fil Facebook que la mairie republie elle-même sur son site (extensions WordPress Smash Balloon, Feed
   Them Social, WP Social Ninja...) : le texte des publications est dans la page du site, lue comme les
   autres pages de la mairie (robots.txt respecté). Liste des sites concernés : reseaux.json
   (« flux_facebook_site »).
2. L'API officielle de Meta (Graph API, fonctionnalité « Page Public Content Access », accordée par Meta
   après examen de l'application et vérification de l'entreprise) : publications publiques des pages
   officielles listées dans reseaux.json. Sans jeton (variable FACEBOOK_JETON ou fichier facebook_jeton.txt,
   jamais publié), cette voie ne lit rien.

Jamais : lecture de facebook.com par un robot (interdite par son robots.txt), compte personnel ou faux
compte, contournement d'un mur de connexion, groupes privés.

Les pistes ont le format de PanneauPocket (type « Facebook ») : titre, extraits sur l'emprunt ou la banque,
date de mise en ligne, annonce de conseil (affiche lue par OCR si besoin), lien vers la publication.
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from perimetre import norm  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
GRAPH = "https://graph.facebook.com/v23.0"
CONSEIL = re.compile(r"conseil (?:municipal|communautaire)|ordre du jour|convocation|seance du conseil|"
                     r"reunion du conseil|deliberations?")
MOIS = {m: i for i, m in enumerate(["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
                                    "septembre", "octobre", "novembre", "decembre"], 1)}
# découpe d'un fil recopié dans la page : un bloc par publication
BLOC = re.compile(r'<(?:div|article)[^>]+class="[^"]*(?:cff-item|fts-jal-single-fb-post|wpsr-fb-feed-item|'
                  r'fb-feed-item|efbl-post)[^"]*"', re.I)
PERMALIEN = re.compile(r'href="(https://(?:www\.)?facebook\.com/[^"]+/(?:posts|photos|videos)/[^"]+|'
                       r'https://(?:www\.)?facebook\.com/permalink\.php[^"]+|https://(?:www\.)?facebook\.com/'
                       r'\d+/posts/[^"]+)"', re.I)


def jeton():
    t = os.environ.get("FACEBOOK_JETON", "").strip()
    if not t and os.path.exists(os.path.join(ICI, "facebook_jeton.txt")):
        t = open(os.path.join(ICI, "facebook_jeton.txt")).read().strip()
    return t or None


def date_fr(texte, jour):
    """Date d'une publication écrite dans le fil : « 23 octobre 2026 », « 23/10/2026 », « il y a 2 jours »,
    « hier », « 3 h »."""
    t = norm(texte)
    m = re.search(r"il y a (\d+) (minute|heure|h\b|jour|semaine)", t)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return jour - timedelta(days=n if u == "jour" else 7 * n if u == "semaine" else 0)
    if re.search(r"\bhier\b", t):
        return jour - timedelta(days=1)
    if re.search(r"\b\d{1,2} ?(?:h|min)\b|aujourd.hui", t):
        return jour
    m = re.search(r"\b(\d{1,2})(?:er)? (" + "|".join(MOIS) + r")(?: (\d{4}))?", t)
    if m:
        try:
            return date(int(m.group(3) or jour.year), MOIS[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None
    return None


def texte(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()


def piste(siren, e, url, titre, quand, corps, entite, communes, epcis, image=None, voie="site"):
    """Une piste si la publication parle d'emprunt ou de banque, ou annonce un conseil dont l'affiche en
    parle (OCR de l'image jointe)."""
    import mairies
    ex, mots = mairies.extraits(corps)
    conseil = bool(CONSEIL.search(norm(corps)))
    lu_ocr = False
    if not ex and conseil and image:
        try:
            import panneaupocket
            tx = panneaupocket.ocr_image(panneaupocket.lire(image, essais=2))
        except Exception:
            tx = None
        if tx:
            lu_ocr = True
            ex, mots = mairies.extraits(re.sub(r"\s+", " ", tx), large=True)
            if not ex:
                ex, mots = mairies.extraits_colles(tx)
    if not ex:
        return None
    return {"type": "Facebook", "url": url, "page": e.get("page"), "titre": titre[:160], "date_seance": None,
            "mis_en_ligne": quand.isoformat() if quand else None, "mots": mots, "extraits": ex[:4],
            "convocation": conseil, "ocr": lu_ocr, "source": "Facebook" + (" (repris sur le site)" if voie == "site"
                                                                          else " (page officielle, API Meta)"),
            "type_signal": "Facebook", "siren": siren, "entite": entite(siren, communes, epcis)}


def flux_sites(chemin, jour, communes, epcis, entite, stats, jours=3, fils=8, duree_max=300):
    """Publications récentes des fils Facebook recopiés sur les sites des mairies."""
    import mairies
    try:
        rs = json.load(open(chemin, encoding="utf-8"))["collectivites"]
    except Exception as e:
        stats["Facebook (fils repris sur les sites)"] = f"ERREUR : reseaux.json illisible ({e})"
        return []
    cibles = {s: e for s, e in rs.items() if e.get("flux_facebook_site")}
    t0, lus, recentes = time.time(), 0, 0
    lim = jour - timedelta(days=jours)

    def un(item):
        nonlocal lus, recentes
        siren, e = item
        if time.time() - t0 > duree_max:
            return []
        try:
            base, _, b, _ = mairies.lire(e["flux_facebook_site"])
        except Exception:
            return []
        lus += 1
        s = b.decode("utf-8", "ignore")
        coupes = [m.start() for m in BLOC.finditer(s)] + [len(s)]
        out = []
        for a, z in zip(coupes, coupes[1:]):
            bloc = s[a:min(z, a + 20000)]
            corps = texte(bloc)
            quand = date_fr(corps[-300:], jour) or date_fr(corps, jour)
            if not quand or not (lim <= quand <= jour + timedelta(days=1)):
                continue
            recentes += 1
            m = PERMALIEN.search(bloc)
            img = re.search(r'<img[^>]+src="(https://[^"]+(?:fbcdn|scontent)[^"]+)"', bloc)
            p = piste(siren, {"page": base}, html.unescape(m.group(1)) if m else base, corps[:120], quand, corps,
                      entite, communes, epcis, html.unescape(img.group(1)) if img else None)
            if p:
                out.append(p)
        return out

    res = []
    with ThreadPoolExecutor(fils) as ex:
        for r in ex.map(un, cibles.items()):
            res += r
    stats["Facebook (fils repris sur les sites)"] = (
        f"{lus} sites lus sur {len(cibles)} qui republient leur page Facebook, {recentes} publications depuis "
        f"{jours} jours, {len(res)} parlant d'emprunt ou de banque ({round(time.time() - t0)} s)")
    return res


def identifiant(u):
    """Identifiant ou nom de page Graph API d'une adresse de page ; None pour un groupe ou un profil."""
    p = urllib.parse.urlparse(u)
    morceaux = [x for x in p.path.split("/") if x]
    if not morceaux or morceaux[0].lower() in ("groups", "people", "profile.php"):
        return None
    if morceaux[0].lower() == "pages":
        return morceaux[-1] if morceaux[-1].isdigit() else None
    return morceaux[0]


def api_meta(chemin, jour, communes, epcis, entite, stats, jours=3, fils=4, duree_max=900):
    """Publications publiques des pages officielles, par l'API de Meta (jeton requis)."""
    import urllib.request
    t = jeton()
    if not t:
        stats["Facebook (API Meta)"] = "pas de jeton d'accès : en attente de l'autorisation de Meta"
        return []
    try:
        rs = json.load(open(chemin, encoding="utf-8"))["collectivites"]
    except Exception as e:
        stats["Facebook (API Meta)"] = f"ERREUR : reseaux.json illisible ({e})"
        return []
    pages = [(s, e, identifiant(u)) for s, e in rs.items() for u in e.get("facebook", [])[:1]]
    pages = [x for x in pages if x[2]]
    depuis = int(datetime.combine(jour - timedelta(days=jours), datetime.min.time()).timestamp())
    t0, lues, publications, erreurs = time.time(), 0, 0, 0

    def un(item):
        nonlocal lues, publications, erreurs
        siren, e, pid = item
        if time.time() - t0 > duree_max:
            return []
        q = urllib.parse.urlencode({"fields": "message,created_time,permalink_url,full_picture",
                                    "since": depuis, "limit": 25, "access_token": t})
        try:
            with urllib.request.urlopen(f"{GRAPH}/{urllib.parse.quote(pid)}/posts?{q}", timeout=30) as r:
                data = json.loads(r.read()).get("data", [])
        except Exception:
            erreurs += 1
            return []
        lues += 1
        out = []
        for x in data:
            publications += 1
            quand = date.fromisoformat(x["created_time"][:10]) if x.get("created_time") else None
            corps = x.get("message") or ""
            p = piste(siren, {"page": e["facebook"][0]}, x.get("permalink_url") or e["facebook"][0], corps[:120],
                      quand, corps, entite, communes, epcis, x.get("full_picture"), voie="api")
            if p:
                out.append(p)
        return out

    res = []
    with ThreadPoolExecutor(fils) as ex:
        for r in ex.map(un, pages):
            res += r
    stats["Facebook (API Meta)"] = (f"{lues} pages lues sur {len(pages)} ({erreurs} en erreur), {publications} "
                                    f"publications depuis {jours} jours, {len(res)} parlant d'emprunt ou de banque "
                                    f"({round(time.time() - t0)} s)")
    return res
