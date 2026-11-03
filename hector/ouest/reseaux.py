"""Pages Facebook, Instagram et applications mobiles officielles des communes et EPCI éligibles :
- liens déclarés par chaque mairie à l'Annuaire de l'administration (service-public.fr) ;
- liens présents sur la page d'accueil du site de la mairie (en-tête, pied de page), robots.txt respecté.

Facebook n'est pas lu par Hector : son robots.txt interdit toute collecte automatique sans autorisation
écrite de Meta, ses pages demandent une connexion, et les moteurs de recherche accessibles ne renvoient
pas ses publications (essais du 24/10/2026). La lecture automatique passera par l'API officielle de Meta
(accès au contenu public des pages) une fois l'autorisation obtenue. D'ici là, la liste sert à Nicolas,
qui suit lui-même les pages des collectivités à appeler.

  python3 reseaux.py reseaux.json [sites.json]     annuaire, puis liens des sites des mairies
  python3 reseaux.py --sites reseaux.json sites.json   ajoute seulement les liens des sites
"""
import html
import json
import os
import re
import sys
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get  # noqa: E402
from perimetre import DEPT2REG, norm  # noqa: E402

ANNUAIRE = "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/datasets/api-lannuaire-administration"
FB = re.compile(r"https?://(?:[a-z]{2}-[a-z]{2}\.|www\.|m\.|fr\.|web\.)?facebook\.com/[^\"'<>\s\\]+", re.I)
IG = re.compile(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+", re.I)
# fil Facebook recopié côté serveur dans la page du site (extensions WordPress Smash Balloon, Feed Them
# Social, WP Social Ninja...) : le texte des publications est dans le HTML de la mairie
FLUX = re.compile(r"cff-item|cff-post-text|fts-jal-single-fb-post|wpsr-fb-feed|fb-feed-item|efbl-feed|"
                  r"sb_facebook|cff-wrapper", re.I)
PAS_UNE_PAGE = re.compile(r"^/(sharer|share|dialog|plugins|tr|login|policies|policy|privacy|help|legal|ads|watch|"
                          r"hashtag|search|business|events|photo|story|reel|l\.php|v\d)", re.I)


def page_fb(u):
    """Adresse canonique d'une page ou d'un groupe Facebook (sans paramètres de suivi), sinon None."""
    p = urllib.parse.urlparse(html.unescape(u))
    chemin = urllib.parse.unquote(p.path).rstrip("/")
    if not chemin or PAS_UNE_PAGE.search(chemin):
        return None
    if chemin.lower() == "/profile.php":
        q = urllib.parse.parse_qs(p.query).get("id")
        return f"https://www.facebook.com/profile.php?id={q[0]}" if q else None
    morceaux = [x for x in chemin.split("/") if x]
    # /pages/Nom/ID et /people/Nom/ID : 3 segments ; /p/Nom-ID, /groups/nom, /pg/nom : 2 ; sinon le nom seul
    garde = {"pages": 3, "people": 3, "p": 2, "groups": 2, "pg": 2}.get(morceaux[0].lower(), 1)
    if len(morceaux) < garde:
        return None
    return "https://www.facebook.com/" + "/".join(morceaux[:garde])


def _liste(champ):
    try:
        v = json.loads(champ) if isinstance(champ, str) else (champ or [])
    except ValueError:
        return []
    return v if isinstance(v, list) else []


def liens(r):
    """{'facebook': [...], 'instagram': [...], 'applis': [...]} d'une fiche de l'annuaire."""
    out = {"facebook": [], "instagram": [], "applis": []}
    for x in _liste(r.get("reseau_social")):
        u, genre = (x.get("valeur") or "").strip(), norm(x.get("custom_dico2") or "")
        if "facebook" in genre or "facebook.com" in u:
            p = page_fb(u if u.startswith("http") else "https://" + u)
            if p:
                out["facebook"].append(p)
        elif "instagram" in genre or "instagram.com" in u:
            out["instagram"].append(u)
    for x in _liste(r.get("application_mobile")):
        t = " ".join(str(v) for v in x.values() if v) if isinstance(x, dict) else str(x)
        if t:
            out["applis"].append(t[:160])
    return out


def construire(sortie):
    import veille
    communes, epcis = veille.referentiel()
    insee = {c["code_insee"]: s for s, c in communes.items() if (c.get("population") or 0) < 10000}
    out = {}
    for d in sorted(DEPT2REG):
        for piv in ("mairie", "epci"):
            rows = json.loads(get(f"{ANNUAIRE}/exports/json",
                                  {"where": f'pivot like "{piv}" and startswith(code_insee_commune,"{d}")',
                                   "select": "nom,code_insee_commune,siren,reseau_social,application_mobile"},
                                  tries=40, timeout=120))
            for r in rows:
                if piv == "mairie":
                    if "deleguee" in norm(r.get("nom")) or r.get("code_insee_commune") not in insee:
                        continue
                    siren = insee[r["code_insee_commune"]]
                    ent = communes[siren]
                elif r.get("siren") in epcis and (epcis[r["siren"]].get("population") or 0) < 20000:
                    siren = r["siren"]
                    ent = epcis[siren]
                else:
                    continue
                l = liens(r)
                if not any(l.values()):
                    continue
                e = out.setdefault(siren, {"nom": ent["nom"], "type": "Commune" if piv == "mairie" else "EPCI",
                                           "dept": ent["dept"], "facebook": [], "instagram": [], "applis": []})
                for k, v in l.items():
                    e[k] += [x for x in v if x not in e[k]]
        print(d, len(out), flush=True)
    json.dump({"collectivites": out}, open(sortie, "w"), ensure_ascii=False, indent=0)
    print(len(out), "collectivités éligibles avec un réseau social ou une application ;",
          sum(1 for e in out.values() if e["facebook"]), "avec une page Facebook")
    return out


def depuis_sites(sortie, sites_json, fils=24):
    """Ajoute à reseaux.json les pages Facebook et Instagram citées sur la page d'accueil des sites."""
    import mairies
    sites = json.load(open(sites_json))
    try:
        out = json.load(open(sortie)).get("collectivites", {})
    except (OSError, ValueError):
        out = {}

    def un(kv):
        siren, info = kv
        try:
            base, _, b, _ = mairies.lire(info["site"])
        except Exception:
            return siren, [], [], None
        s = b.decode("utf-8", "ignore")
        fb = list(dict.fromkeys(x for x in (page_fb(u) for u in FB.findall(s)) if x))
        ig = list(dict.fromkeys(u.rstrip("/") for u in IG.findall(s)))
        return siren, fb[:3], ig[:2], (base if FLUX.search(s) else None)

    trouves, flux = {}, {}
    with ThreadPoolExecutor(fils) as ex:
        for siren, fb, ig, f in ex.map(un, sites.items()):
            if fb or ig:
                trouves[siren] = (fb, ig)
            if f:
                flux[siren] = f
    for siren, f in flux.items():
        info = sites[siren]
        e = out.setdefault(siren, {"nom": info.get("nom"), "type": info.get("type"), "dept": info.get("dept"),
                                   "facebook": [], "instagram": [], "applis": []})
        e["flux_facebook_site"] = f
    print(len(flux), "sites republient leurs publications Facebook dans la page (texte lisible)", flush=True)
    # une page citée par plusieurs sites est celle du prestataire ou de l'intercommunalité, pas de la mairie
    compte = Counter(u for fb, _ in trouves.values() for u in fb)
    ajouts = 0
    for siren, (fb, ig) in trouves.items():
        fb = [u for u in fb if compte[u] <= 2]
        if not fb and not ig:
            continue
        info = sites[siren]
        e = out.setdefault(siren, {"nom": info.get("nom"), "type": info.get("type"), "dept": info.get("dept"),
                                   "facebook": [], "instagram": [], "applis": []})
        connus = {norm(u).rstrip("/") for u in e["facebook"]}
        nouveaux = [u for u in fb if norm(u).rstrip("/") not in connus]
        if nouveaux:
            ajouts += 1
            e["facebook"] += nouveaux
            e["facebook_site"] = nouveaux
        e["instagram"] += [u for u in ig if u not in e["instagram"]]
    json.dump({"collectivites": out}, open(sortie, "w"), ensure_ascii=False, indent=0)
    print(len(trouves), "sites citent un réseau social ;", ajouts, "pages Facebook ajoutées ;",
          sum(1 for e in out.values() if e["facebook"]), "collectivités avec une page Facebook au total")
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--sites":
        depuis_sites(sys.argv[2], sys.argv[3])
    else:
        construire(sys.argv[1])
        if len(sys.argv) > 2:
            depuis_sites(sys.argv[1], sys.argv[2])
