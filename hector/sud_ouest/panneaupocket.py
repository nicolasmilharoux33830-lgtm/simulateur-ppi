"""PanneauPocket : panneaux d'information des communes et intercommunalités.

L'application est gratuite et consultable sans compte ; ses pages publiques (app.panneaupocket.com) n'ont
pas de robots.txt et ses CGU n'interdisent pas la lecture. Dans le périmètre, 3 166 entités l'utilisent,
dont plus de 1 000 communes éligibles sans autre site connu (Normandie et Centre surtout). On y lit les
annonces de conseil (convocation, ordre du jour) et tout panneau qui parle d'emprunt ou de banque ; les
affiches en image passent à l'OCR.

  python3 panneaupocket.py --liste panneaupocket.json     entités du périmètre, rattachées au référentiel
  (dans veille.py) scan(chemin, jour, ...)                panneaux récents lus et filtrés
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
API = "https://app.panneaupocket.com/public-api/city/FR-{}"
CONSEIL = re.compile(r"conseil (?:municipal|communautaire)|ordre du jour|convocation|seance du conseil|"
                     r"reunion du conseil|deliberations?")


def lire(url, timeout=30, essais=3):
    for i in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:
            if i == essais - 1:
                raise
            time.sleep(2 + 2 * i)


def cle(nom):
    return re.sub(r"[^a-z0-9]", "", norm(nom).replace("saint", "st").replace("sainte", "ste"))


def liste(chemin):
    """Entités PanneauPocket des 20 départements, rattachées à une commune (< 10 000 hab.) ou un EPCI
    (< 20 000 hab.) du référentiel."""
    r = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "referentiel.json"), encoding="utf-8"))
    communes = {}
    for s, c in r["communes"].items():
        if (c.get("population") or 0) < 10000:
            communes.setdefault((c["dept"], cle(c["nom"])), s)
    epcis = {cle(e["nom"]): s for s, e in r["epcis"].items() if (e.get("population") or 0) < 20000}
    out, total = {}, 0
    for d in sorted(DEPT2REG):
        try:
            data = json.loads(lire(API.format(d)))
        except Exception as e:
            print(d, "ERREUR", e)
            continue
        total += len(data)
        for x in data:
            k = cle(x["name"])
            s = communes.get((d, k)) or epcis.get(k)
            if s:
                out[s] = {"nom": x["name"], "cp": x.get("zipCode"), "url": x["url"], "dept": d}
        time.sleep(0.5)
    json.dump(out, open(chemin, "w"), ensure_ascii=False, indent=0)
    print(total, "entités PanneauPocket dans les 20 départements,", len(out), "communes ou EPCI éligibles rattachés")
    return out


def panneaux(page):
    """(date, titre, texte, images, id) de chaque panneau d'une page de commune."""
    s = page.decode("utf-8", "ignore")
    blocs = re.split(r'<div class="sign-carousel--item[^"]*" data-id="', s)[1:]
    for b in blocs:
        pid = b.split('"', 1)[0]
        m = re.search(r"(?:publiée|modifiée) le (\d{2})/(\d{2})/(\d{4})", b)
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None
        except ValueError:
            d = None
        t = re.search(r'(?s)<div class="title">(.*?)</div>', b)
        c = re.search(r'(?s)<div class="content">(.*?)</div>\s*</div>', b)
        txt = lambda x: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x or ""))).strip()  # noqa: E731
        images = list(dict.fromkeys(re.findall(r'<a href="(https://panneau-pocket[^"]+/sign_image/[^"]+)"', b)))
        docs = list(dict.fromkeys("https://app.panneaupocket.com" + x if x.startswith("/") else x
                                  for x in re.findall(r'href="((?:https://[^"]+)?/pdf/sign_pdf/[^"]+\.pdf)"', b)))
        yield {"id": pid, "date": d, "titre": txt(t.group(1) if t else ""), "texte": txt(c.group(1) if c else ""),
               "images": images, "documents": docs}


def ocr_image(octets):
    try:
        import io
        import budgets_pdf
        from PIL import Image
        m = budgets_pdf.moteur_ocr()
        if not m:
            return None
        im = Image.open(io.BytesIO(octets)).convert("RGB")
        if max(im.size) > 2200:
            im.thumbnail((2200, 2200))
        with budgets_pdf._verrou_ocr:
            res, _ = m(im)
        return " ".join(x[1] for x in res or [])
    except Exception:
        return None


def scan(chemin, jour, communes, epcis, entite, stats, jours=3, fils=4, duree_max=600, priorite=None):
    """Panneaux publiés ou modifiés depuis `jours` jours : ceux qui parlent d'emprunt ou de banque, et les
    annonces de conseil dont l'affiche (image ou PDF) en parle."""
    import mairies
    try:
        ents = json.load(open(chemin, encoding="utf-8"))
    except Exception as e:
        stats["PanneauPocket"] = f"ERREUR : liste illisible ({e})"
        return []
    t0, n_lus, n_recents, n_ocr = time.time(), 0, 0, 0
    lim = jour - timedelta(days=jours)

    def un(item):
        nonlocal n_lus, n_recents, n_ocr
        siren, e = item
        if time.time() - t0 > duree_max:
            return []
        try:
            page = lire(e["url"], essais=2)
        except Exception:
            return []
        n_lus += 1
        out = []
        for p in panneaux(page):
            if not p["date"] or not (lim <= p["date"] <= jour + timedelta(days=1)):
                continue
            n_recents += 1
            texte = f"{p['titre']} — {p['texte']}"
            ex, mots = mairies.extraits(texte)
            conseil = bool(CONSEIL.search(norm(texte)))
            if not ex and conseil:
                for u in (p["documents"] + p["images"])[:3]:
                    try:
                        b = lire(u, essais=2)
                    except Exception:
                        continue
                    if u.split("?")[0].lower().endswith(".pdf") or b[:4] == b"%PDF":
                        import budgets_pdf
                        tx = " ".join(budgets_pdf.pages_texte(b, max_pages=4, max_ocr=3)[0])
                    else:
                        tx = ocr_image(b)
                    if tx:
                        n_ocr += 1
                        tx = re.sub(r"\s+", " ", tx)
                        ex, mots = mairies.extraits(tx, large=True)
                        if not ex:
                            ex, mots = mairies.extraits_colles(tx)
                        if ex:
                            break
            if ex:
                out.append({"type": "PanneauPocket", "url": f"{e['url']}?panneau={p['id']}", "page": e["url"],
                            "titre": p["titre"][:160], "date_seance": None, "mis_en_ligne": p["date"].isoformat(),
                            "mots": mots, "extraits": ex[:4], "convocation": conseil,
                            "source": "PanneauPocket", "type_signal": "PanneauPocket", "siren": siren,
                            "entite": entite(siren, communes, epcis)})
        time.sleep(0.3)
        return out

    res = []
    with ThreadPoolExecutor(fils) as ex:
        # les plus probables d'abord : si le temps manque, ce sont les derniers de la liste qui ne sont pas lus
        ordre = sorted(ents.items(), key=lambda kv: -(priorite or {}).get(kv[0], 0))
        for r in ex.map(un, ordre):
            res += r
    stats["PanneauPocket"] = (f"{n_lus} pages de communes et EPCI lues sur {len(ents)}, {n_recents} panneaux "
                              f"publiés depuis {jours} jours, {n_ocr} affiches lues par OCR, {len(res)} parlant "
                              f"d'emprunt ou de banque ({round(time.time() - t0)} s)")
    return res


if __name__ == "__main__":
    if sys.argv[1] == "--liste":
        liste(sys.argv[2])
