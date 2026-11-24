"""IntraMuros : actualités et agenda publics des communes (www.intramuros.org).

Plus de 8 000 communes publient sur l'application IntraMuros ; chacune a des pages web publiques
(www.intramuros.org/<commune>/actualites et /agenda). Le robots.txt du site autorise tous les robots
(« User-agent: * / Allow: / »). On y cherche les annonces de conseil (convocation, ordre du jour) et toute
actualité qui parle d'emprunt ou de banque ; les PDF joints sont lus comme pour PanneauPocket.

  python3 intramuros.py --liste intramuros.json     communes du périmètre présentes sur IntraMuros (nuit)
  (dans veille.py) scan(chemin, jour, ...)          actualités et conseils récents, filtrés
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from perimetre import DEPT2REG, norm  # noqa: E402

UA = "Mozilla/5.0 (compatible; HectorVeille/1.0; veille des actes publics des collectivites)"
BASE = "https://www.intramuros.org"
FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "intramuros.json")
MOIS = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
        "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12}
RE_DATE = re.compile(r"\b(\d{1,2})(?:er)? (janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|"
                     r"novembre|decembre) (\d{4})\b")
CONSEIL = re.compile(r"conseil (?:municipal|communautaire|syndical)|comite syndical|ordre du jour|convocation|"
                     r"seance du conseil|reunion du conseil|deliberations?|compte.rendu|proces.verbal")
FINANCE = re.compile(r"\b(emprunts?|prets?|tresorerie|banques?|bancaires?|budget|decision modificative|"
                     r"financement|investissement)\b")


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


def slug(nom):
    s = norm(nom).replace("'", "").replace("’", "")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def texte(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def une_date(t):
    m = RE_DATE.search(norm(t))
    if not m:
        return None
    try:
        return date(int(m.group(3)), MOIS[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def elements(page_html, sl, rubrique):
    """[(id, url, extrait de texte autour du lien)] des actualités ou événements d'une page de liste."""
    out, vus = [], set()
    motif = re.compile(rf'href="(?:{re.escape(BASE)})?/{re.escape(sl)}/{rubrique}/(\d+)[^"]*"')
    for m in motif.finditer(page_html):
        i = m.group(1)
        if i in vus:
            continue
        vus.add(i)
        bloc = texte(page_html[m.start():m.end() + 700])
        out.append((i, f"{BASE}/{sl}/{rubrique}/{i}", bloc[:600]))
    return out


# ---------- liste des communes du périmètre présentes sur IntraMuros (tâche de nuit) ----------
def liste(sortie, duree_max=5000):
    import veille
    communes, _ = veille.referentiel()
    cibles = {}
    for s, c in communes.items():
        if (c.get("population") or 0) < 10000:
            cibles.setdefault(slug(c["nom"]), []).append((s, c))
    sm = lire(f"{BASE}/sitemap.xml", timeout=120).decode("utf-8", "ignore")
    slugs = sorted({u for u in re.findall(rf"<loc>{re.escape(BASE)}/([a-z0-9-]+)</loc>", sm)})
    out, t0, testes = {}, time.time(), 0
    for sl in slugs:
        if sl not in cibles or time.time() - t0 > duree_max:
            continue
        try:
            page = lire(f"{BASE}/{sl}").decode("utf-8", "ignore")
        except Exception:
            continue
        testes += 1
        cps = set(re.findall(r"\b(\d{5})\b", page))
        for s, c in cibles[sl]:
            if any(cp.startswith(c["dept"]) for cp in cps) or len(cibles[sl]) == 1 and not cps:
                out[s] = {"nom": c["nom"], "dept": c["dept"], "slug": sl, "url": f"{BASE}/{sl}"}
                break
        time.sleep(0.8)
    json.dump(out, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(out)} communes du périmètre sur IntraMuros ({len(slugs)} communes dans le plan du site, "
          f"{testes} pages vérifiées)")


# ---------- lecture quotidienne ----------
def scan(chemin, jour, communes, epcis, entite, stats, jours=3, fils=4, duree_max=900, priorite=None):
    import mairies
    try:
        ents = json.load(open(chemin, encoding="utf-8"))
    except Exception:
        return []
    if not ents:
        return []
    t0, n_lus, n_recents, n_pdf = time.time(), 0, 0, 0
    lim = jour - timedelta(days=jours)

    def lire_pdfs(page_html):
        import budgets_pdf
        tx = ""
        for u in re.findall(r'href="(https?://[^"]+\.pdf)"', page_html, re.I)[:3]:
            try:
                b = lire(u)
                tx += " " + " ".join(budgets_pdf.pages_texte(b, max_pages=4, max_ocr=2)[0])
            except Exception:
                continue
        return re.sub(r"\s+", " ", tx)

    def un(item):
        nonlocal n_lus, n_recents, n_pdf
        siren, e = item
        if time.time() - t0 > duree_max:
            return []
        out = []
        for rubrique in ("actualites", "agenda"):
            try:
                page = lire(f"{e['url']}/{rubrique}").decode("utf-8", "ignore")
            except Exception:
                continue
            n_lus += 1
            for i, url, bloc in elements(page, e["slug"], rubrique):
                nb = norm(bloc)
                if not (CONSEIL.search(nb) or FINANCE.search(nb)):
                    continue
                d = une_date(bloc)
                if rubrique == "actualites" and (not d or not (lim <= d <= jour + timedelta(days=1))):
                    continue
                if rubrique == "agenda" and (not d or not (jour <= d <= jour + timedelta(days=21))
                                             or not CONSEIL.search(nb)):
                    continue
                n_recents += 1
                try:
                    ph = lire(url).decode("utf-8", "ignore")
                except Exception:
                    continue
                t = texte(ph)
                ex, mots = mairies.extraits(t)
                conseil = bool(CONSEIL.search(norm(t)))
                if not ex and conseil:
                    tx = lire_pdfs(ph)
                    if tx:
                        n_pdf += 1
                        ex, mots = mairies.extraits(tx, large=True)
                if ex:
                    titre = re.split(r"\s{2,}| \| ", bloc)[0][:160]
                    out.append({"type": "IntraMuros", "url": url, "page": f"{e['url']}/{rubrique}",
                                "titre": titre, "date_seance": d.isoformat() if rubrique == "agenda" and d else None,
                                "mis_en_ligne": d.isoformat() if rubrique == "actualites" and d else None,
                                "mots": mots, "extraits": ex[:4], "convocation": conseil and rubrique == "agenda",
                                "source": "IntraMuros", "type_signal": "IntraMuros", "siren": siren,
                                "entite": entite(siren, communes, epcis)})
                time.sleep(0.4)
            time.sleep(0.4)
        return out

    res = []
    ordre = sorted(ents.items(), key=lambda kv: -(priorite or {}).get(kv[0], 0))
    with ThreadPoolExecutor(fils) as ex:
        for r in ex.map(un, ordre):
            res += r
    stats["IntraMuros"] = (f"{n_lus} pages lues ({len(ents)} communes), {n_recents} annonces récentes ouvertes, "
                           f"{n_pdf} avec PDF lus, {len(res)} qui parlent d'emprunt ou de banque"
                           + (" ; arrêt faute de temps" if time.time() - t0 > duree_max else ""))
    return res


def _test():
    h = ('<div class="card"><a href="/mire/actualites/1039812">Conseil municipal du 2 décembre</a>'
         '<span>lundi 23 novembre 2026</span><p>Ordre du jour : emprunt pour la salle</p></div>'
         '<a href="https://www.intramuros.org/mire/actualites/1039800">Chat trouvé</a><span>2 novembre 2026</span>')
    el = elements(h, "mire", "actualites")
    assert [x[0] for x in el] == ["1039812", "1039800"], el
    assert une_date(el[0][2]) == date(2026, 11, 23), el[0]
    assert slug("Saint-Denis-d'Anjou") == "saint-denis-danjou", slug("Saint-Denis-d'Anjou")
    print("intramuros ok")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--liste":
        liste(sys.argv[2])
    else:
        _test()
