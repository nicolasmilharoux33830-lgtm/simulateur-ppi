"""Deux sources publiques de plus, sur le modèle d'IntraMuros :

- Illiwap (station.illiwap.com) : plus de 3 000 collectivités ; chaque commune a une page publique
  /fr/public/<nom>_<numéro> avec ses actualités (/fr/public/<numéro>/actu/) et son agenda (/evenements/).
  Le robots.txt autorise /fr/ à tous les robots. Il n'y a pas d'annuaire : les numéros sont repérés sur les
  sites des mairies (lien « Illiwap »), quelques centaines de sites par nuit, à tour de rôle.
- L'Annuaire des Collectivités de l'État (collectivite.fr, ANCT) : une page par commune (<nom>-<code postal>)
  où les mairies peuvent déposer délibérations, procès-verbaux et comptes rendus. Le robots.txt autorise tout.
  Les communes qui y ont déposé des documents sont repérées la nuit, à tour de rôle.

  python3 applis.py --decouvrir [n]      repérage de nuit (illiwap.json, collectivite.json, applis_suivi.json)
  (dans veille.py) scan(jour, ...)       lecture quotidienne, filtrée comme PanneauPocket
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from perimetre import DEPT2REG, norm  # noqa: E402

UA = "Mozilla/5.0 (compatible; HectorVeille/1.0; veille des actes publics des collectivites)"
ILLIWAP = "https://station.illiwap.com"
ANNUAIRE = "https://collectivite.fr"
F_ILLI = os.path.join(ICI, "illiwap.json")
F_ANN = os.path.join(ICI, "collectivite.json")
F_SUIVI = os.path.join(ICI, "applis_suivi.json")
RE_ILLI = re.compile(r"station\.illiwap\.com/fr/public/([a-z0-9-]+)_(\d+)", re.I)
RE_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
RE_LONG = re.compile(r"\b(\d{1,2})(?:er)? (janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|"
                     r"novembre|decembre) (\d{4})\b")
CONSEIL = re.compile(r"conseil (?:municipal|communautaire|syndical)|comite syndical|ordre du jour|convocation|"
                     r"seance|deliberations?|compte.rendu|proces.verbal|\bpv\b")
FINANCE = re.compile(r"\b(emprunts?|prets?|tresorerie|banques?|bancaires?|budget|decision modificative|financement)\b")


def lire(url, timeout=30, essais=2):
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fr-FR"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == essais - 1:
                raise
            time.sleep(2 + 2 * i)


def texte(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def une_date(t):
    m = RE_DMY.search(t)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = RE_LONG.search(norm(t))
    if m:
        try:
            return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
        except ValueError:
            pass
    return None


def slug(nom):
    s = norm(nom).replace("'", "-").replace("’", "-")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def liens(page_html, motif):
    """[(url absolue, texte qui suit le lien)] des liens dont l'adresse correspond au motif."""
    out, vus = [], set()
    for m in re.finditer(r'href="([^"]+)"', page_html):
        u = html.unescape(m.group(1))
        if not re.search(motif, u) or u in vus:
            continue
        vus.add(u)
        out.append((u, texte(page_html[m.start():m.end() + 700])[:600]))
    return out


# ---------- repérage de nuit, à tour de rôle ----------
def decouvrir(n=1500, pause=0.6):
    import veille
    communes, _ = veille.referentiel()
    try:
        suivi = json.load(open(F_SUIVI))
    except (OSError, ValueError):
        suivi = {}
    illi = _charge(F_ILLI)
    ann = _charge(F_ANN)
    sites = _charge(os.path.join(ICI, "sites.json"))
    cps = {}
    try:
        from net import jget
        for d in sorted(DEPT2REG):
            for c in jget(f"https://geo.api.gouv.fr/departements/{d}/communes", {"fields": "code,codesPostaux"},
                          tries=6, timeout=60):
                cps[c["code"]] = c.get("codesPostaux") or []
    except Exception:
        pass
    cibles = [(s, c) for s, c in communes.items() if (c.get("population") or 0) < 10000]
    cibles.sort(key=lambda sc: suivi.get(sc[0], ""))           # jamais vus d'abord, puis les plus anciens
    aujourd = date.today().isoformat()
    n_ill, n_ann = 0, 0

    def un(sc):
        s, c = sc
        trouve = {}
        site = (sites.get(s) or {}).get("site")
        if site and s not in illi:
            try:
                h = lire(site, timeout=20).decode("utf-8", "ignore")
                m = RE_ILLI.search(h)
                if m:
                    trouve["illi"] = {"nom": c["nom"], "dept": c["dept"], "id": m.group(2),
                                      "url": f"{ILLIWAP}/fr/public/{m.group(1)}_{m.group(2)}"}
            except Exception:
                pass
        for cp in (cps.get(c.get("code_insee")) or [])[:2]:
            u = f"{ANNUAIRE}/{slug(c['nom'])}-{cp}"
            try:
                h = lire(u, timeout=20).decode("utf-8", "ignore")
            except Exception:
                continue
            docs = liens(h, r"\.pdf(\?|$)|/documents?/|deliberation|proces-verbal|compte-rendu")
            if docs:
                trouve["ann"] = {"nom": c["nom"], "dept": c["dept"], "url": u, "n_docs": len(docs)}
            break
        time.sleep(pause)
        return s, trouve

    with ThreadPoolExecutor(6) as ex:
        for s, t in ex.map(un, cibles[:n]):
            suivi[s] = aujourd
            if t.get("illi"):
                illi[s] = t["illi"]
                n_ill += 1
            if t.get("ann"):
                ann[s] = t["ann"]
                n_ann += 1
            elif s in ann:
                ann.pop(s)
    json.dump(illi, open(F_ILLI, "w"), ensure_ascii=False, indent=0)
    json.dump(ann, open(F_ANN, "w"), ensure_ascii=False, indent=0)
    json.dump(suivi, open(F_SUIVI, "w"), ensure_ascii=False)
    print(f"{min(n, len(cibles))} communes examinées : {n_ill} stations Illiwap trouvées (total {len(illi)}), "
          f"{n_ann} pages collectivite.fr avec documents (total {len(ann)})")


def _charge(f):
    try:
        return json.load(open(f, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ---------- lecture quotidienne ----------
def scan(jour, communes, epcis, entite, stats, jours=3, fils=4, duree_max=900):
    import mairies
    illi, ann = _charge(F_ILLI), _charge(F_ANN)
    if not illi and not ann:
        return []
    t0, lus, ouverts = time.time(), 0, 0
    lim = jour - timedelta(days=jours)

    def lire_pdf(u):
        import budgets_pdf
        try:
            return re.sub(r"\s+", " ", " ".join(budgets_pdf.pages_texte(lire(u), max_pages=5, max_ocr=2)[0]))
        except Exception:
            return ""

    def garde(siren, source, url, titre, d, t, agenda=False):
        ex, mots = mairies.extraits(t)
        if not ex:
            return None
        return {"type": source, "url": url, "page": url, "titre": titre[:160],
                "date_seance": d.isoformat() if agenda and d else None,
                "mis_en_ligne": d.isoformat() if d and not agenda else None, "mots": mots, "extraits": ex[:4],
                "convocation": agenda, "source": source, "type_signal": source, "siren": siren,
                "entite": entite(siren, communes, epcis)}

    def un_illi(item):
        nonlocal lus, ouverts
        siren, e = item
        out = []
        if time.time() - t0 > duree_max:
            return out
        for rub in ("actu", "evenements"):
            try:
                h = lire(f"{ILLIWAP}/fr/public/{e['id']}/{rub}/").decode("utf-8", "ignore")
            except Exception:
                continue
            lus += 1
            for u, bloc in liens(h, rf"/fr/public/{e['id']}/{rub}/[a-z0-9-]+"):
                nb = norm(bloc)
                d = une_date(bloc)
                if rub == "actu" and (not d or not (lim <= d <= jour + timedelta(days=1))):
                    continue
                if rub == "evenements" and (not d or not (jour <= d <= jour + timedelta(days=21))
                                            or not CONSEIL.search(nb)):
                    continue
                if not (CONSEIL.search(nb) or FINANCE.search(nb)):
                    continue
                url = urllib.parse.urljoin(ILLIWAP, u)
                try:
                    ph = lire(url).decode("utf-8", "ignore")
                except Exception:
                    continue
                ouverts += 1
                t = texte(ph)
                if not mairies.extraits(t)[0]:
                    for p in re.findall(r'href="(https?://[^"]+\.pdf)"', ph, re.I)[:2]:
                        t += " " + lire_pdf(p)
                g = garde(siren, "Illiwap", url, bloc, d, t, agenda=rub == "evenements")
                if g:
                    out.append(g)
                time.sleep(0.4)
        return out

    def un_ann(item):
        nonlocal lus, ouverts
        siren, e = item
        out = []
        if time.time() - t0 > duree_max:
            return out
        try:
            h = lire(e["url"]).decode("utf-8", "ignore")
        except Exception:
            return out
        lus += 1
        for u, bloc in liens(h, r"\.pdf(\?|$)|/documents?/|deliberation|proces-verbal|compte-rendu"):
            d = une_date(bloc)
            if not d or not (lim - timedelta(days=4) <= d <= jour + timedelta(days=1)):
                continue
            url = urllib.parse.urljoin(e["url"], u)
            ouverts += 1
            t = lire_pdf(url) if re.search(r"\.pdf(\?|$)", url, re.I) else texte(lire(url).decode("utf-8", "ignore"))
            g = garde(siren, "Annuaire des Collectivités", url, bloc, d, t)
            if g:
                out.append(g)
            time.sleep(0.4)
        return out

    res = []
    with ThreadPoolExecutor(fils) as ex:
        for r in ex.map(un_illi, illi.items()):
            res += r
        for r in ex.map(un_ann, ann.items()):
            res += r
    stats["Illiwap et Annuaire des Collectivités"] = (
        f"{len(illi)} stations Illiwap et {len(ann)} pages collectivite.fr suivies, {lus} pages lues, "
        f"{ouverts} documents ouverts, {len(res)} qui parlent d'emprunt ou de banque")
    return res


def _test():
    h = ('<a href="/fr/public/42124/actu/conseil-municipal-du-3-decembre">Conseil municipal du 3 décembre</a>'
         '<span>20/11/2026</span>')
    l = liens(h, r"/fr/public/42124/actu/[a-z0-9-]+")
    assert l and une_date(l[0][1]) == date(2026, 11, 20), l
    assert RE_ILLI.search('src="https://station.illiwap.com/fr/public/mairie-de-lupe_42124"').group(2) == "42124"
    assert slug("Saint-Denis-d'Anjou") == "saint-denis-d-anjou"
    print("applis ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--decouvrir":
        decouvrir(int(sys.argv[2]) if len(sys.argv) > 2 else 1500)
    else:
        _test()
