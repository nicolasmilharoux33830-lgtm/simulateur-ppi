"""Décisions budgétaires publiées en PDF (décisions modificatives, budgets supplémentaires) : un emprunt
nouveau inscrit en recettes d'investissement (compte 1641, chapitre 16), lu ligne à ligne.

Les trois quarts de ces documents sont des scans sans texte : ils passent alors par l'OCR (rapidocr et
pypdfium2, s'ils sont installés), page par page. Sans OCR, le document est signalé « à lire ».

Une ligne trouvée n'est qu'une piste : Hector relit la page avant de retenir la collectivité.

  python3 budgets_pdf.py fichier.pdf [...]      lignes d'emprunt trouvées dans chaque fichier
"""
import io
import json
import re
import sys
import threading
import unicodedata

# Objet d'un acte : décision qui modifie le budget en cours d'année
OBJET_BUDGET = re.compile(r"modificativ|\bdm\b|\bdm ?n?o? ?\d|\bdbm\b|\bdecision budgetaire|budget supplementaire|"
                          r"\bbs\b|virements? de credits?|ajustements? (?:budgetaires?|de credits)|budget rectificatif|"
                          r"\beprd\b")
OBJET_EXCLU = re.compile(r"primitif|\bbp\b|compte administratif|financier unique|\bcfu\b|affectation (?:du|des) resultat|"
                         r"non.valeur|irrecouvrable|creances|\btarif|amortissement|regie")
MONTANT = re.compile(r"(?<![\d,.])([+-]?\s?(?:\d{1,3}(?:[ .  ]\d{3})+|\d{4,9})(?:[,.]\d{1,2})?)\s*(?:€|eur\b|euros?\b)?")
COMPTE = re.compile(r"(?<![\d.,])1641\d{0,3}(?![\d.,]\d)")
CHAPITRE16 = re.compile(r"(?:chapitre|chap\.?)\s*16\b|\b16\s*[-:–]?\s*emprunts? et dettes")
LIBELLE_NEUF = re.compile(r"emprunts? (?:classique|relais|d.equilibre|nouveaux?|a long terme|a court terme|bancaires?|"
                          r"en euros|aupres)|pret relais|nouvel emprunt")
RECETTE = re.compile(r"\brecettes?\b")
DEPENSE = re.compile(r"\bdepenses?\b|rembours")
ORDRE = re.compile(r"\b04[01]\b|operations? patrimoniales?|operations? d.ordre")
NARRATIF = re.compile(r"(?:inscri\w*|recours a|recourir a|realis\w*|contract\w*|souscri\w*|mobilis\w*|prevoir|"
                      r"prevoit|necessite)\s+(?:un |d.un |l.|a l.|le |au )?(?:nouvel |nouveau )?"
                      r"(?:emprunt|pret)\w*(?:\s+\S+){0,6}?\s+(?:de|d.un montant de|pour|a hauteur de|d.environ)\s+"
                      r"(\d{1,3}(?:[ .  ]\d{3})+|\d{4,9})(?:[,.]\d{1,2})?\s*(?:€|euros?)")


def plat(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[ \t]+", " ", s)


def montants(s):
    """Montants en euros d'une ligne (sans les numéros de compte, d'article ni les années)."""
    out = []
    for m in MONTANT.finditer(s):
        brut = m.group(1)
        # un nombre nu suivi d'un libellé est un numéro de compte ou d'article (« 615228 Entretien »)
        nu = not re.search(r"[ .,\u00a0\u202f]", brut.strip().lstrip("+-").strip())
        apres = s[m.end(1):m.end(1) + 3]
        if nu and not re.match(r"\s*(?:€|eur)", apres) and re.match(r"\s?[a-zA-Z]", apres):
            continue
        chiffres = re.sub(r"[^\d,.]", "", brut)
        entier = re.split(r"[,.](?=\d{1,2}$)", chiffres)[0].replace(".", "").replace(",", "")
        if not entier:
            continue
        v = int(entier)
        if v in (1641, 16411, 16441) or 1990 <= v <= 2040 and not re.search(r"[ .,]", brut.strip()):
            continue
        if v < 100 or v > 500_000_000:
            continue
        out.append(-v if brut.strip().startswith("-") else v)
    return out


# ---------- texte des pages, OCR des scans ----------
_ocr, _verrou_init, _verrou_ocr = None, threading.Lock(), threading.Lock()


def moteur_ocr():
    global _ocr
    with _verrou_init:
        if _ocr is None:
            try:
                import logging
                logging.disable(logging.WARNING)
                __import__("pypdfium2")
                from rapidocr_onnxruntime import RapidOCR
                _ocr = RapidOCR()
            except Exception:
                _ocr = False
    return _ocr


def ocr_page(page, moteur, echelle=1.0):
    """Texte d'une page scannée, reconstitué ligne par ligne (les cellules d'un tableau restent sur leur ligne).
    À l'échelle 1, l'OCR sépare bien les mots ; au-delà il les colle (« souscrireunemprunt »)."""
    im = page.render(scale=echelle).to_pil().convert("RGB")
    with _verrou_ocr:
        res, _ = moteur(im)
    boites = []
    for box, txt, _score in res or []:
        ys, xs = [p[1] for p in box], [p[0] for p in box]
        boites.append(((min(ys) + max(ys)) / 2, max(ys) - min(ys), min(xs), txt))
    boites.sort()
    lignes, cur, cy, ch = [], [], 0, 0
    for y, h, x, t in boites:
        if cur and abs(y - cy) > max(ch, h) * 0.6:
            lignes.append(" ".join(t for _, t in sorted(cur)))
            cur = []
        if not cur:
            cy, ch = y, h
        cur.append((x, t))
    if cur:
        lignes.append(" ".join(t for _, t in sorted(cur)))
    return "\n".join(lignes)


def pages_texte(octets, max_pages=60, max_ocr=4, ocr=True):
    """(textes des pages, pages passées à l'OCR, pages scannées non lues)."""
    textes = []
    try:
        import logging
        import warnings
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.CRITICAL)
        warnings.filterwarnings("ignore")
        r = PdfReader(io.BytesIO(octets))
        for p in r.pages[:max_pages]:
            try:
                textes.append(p.extract_text() or "")
            except Exception:
                textes.append("")
    except Exception:
        textes = []
    vides = [i for i, t in enumerate(textes) if len(t.strip()) < 80]
    if not textes:
        vides = list(range(max_ocr))
    faits, restes = [], []
    moteur = moteur_ocr() if (ocr and vides) else None
    if moteur:
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(octets)
            n = len(doc)
            while len(textes) < min(n, max_pages):
                textes.append("")
            for i in [i for i in vides if i < n][:max_ocr]:
                try:
                    textes[i] = ocr_page(doc[i], moteur)
                    faits.append(i + 1)
                except Exception:
                    restes.append(i + 1)
            restes += [i + 1 for i in vides[max_ocr:] if i < n]
        except Exception:
            restes = [i + 1 for i in vides]
    else:
        restes = [i + 1 for i in vides]
    return textes, faits, restes


# ---------- lignes d'emprunt ----------
def _cote(lignes, i):
    """recette, depense, ordre ou inconnu pour la ligne i (compte 1641 ou chapitre 16)."""
    ici = " ".join(lignes[i:i + 2])
    if re.search(r"(?<![a-z])d\s?[-:]?\s?1641|\bdepense|en ?capital", ici) or "rembours" in ici:
        return "depense"
    if re.search(r"(?<![a-z])r\s?[-:]?\s?1641|\brecettes?\b", lignes[i]):
        cote = "recette"
    else:
        cote = "inconnu"
        for j in range(i - 1, max(-1, i - 30), -1):
            r, d = RECETTE.search(lignes[j]), DEPENSE.search(lignes[j])
            if r and d:
                break                       # en-tête de tableau à deux colonnes : la colonne ne se lit pas ici
            if r or d:
                cote = "recette" if r else "depense"
                avant = " ".join(lignes[j:i + 1])
                if ORDRE.search(avant[-300:]):
                    return "ordre"
                break
    if ORDRE.search(ici) and not LIBELLE_NEUF.search(ici):
        return "ordre"
    if cote == "inconnu" and LIBELLE_NEUF.search(ici):
        cote = "recette"
    return cote


def lignes_emprunt(textes):
    """Lignes d'un document budgétaire qui inscrivent un emprunt (compte 1641, chapitre 16, ou phrase)."""
    hits = []
    for p, brut in enumerate(textes, 1):
        lignes_b = [x.strip() for x in brut.split("\n") if x.strip()]
        lignes = [plat(x) for x in lignes_b]
        for i, l in enumerate(lignes):
            if not (COMPTE.search(l) or CHAPITRE16.search(l) or LIBELLE_NEUF.search(l)):
                continue
            if re.search(r"etat de la dette|sans objet|garanti|annexe", l):
                continue
            ms, k = montants(COMPTE.sub(" ", l)), i
            while not ms and k < min(i + 4, len(lignes) - 1):
                k += 1
                if re.search(r"\b(compte|article|chapitre)\b", lignes[k]) and not montants(lignes[k]):
                    break
                ms = montants(lignes[k])
            if not ms:
                continue
            texte = " ".join(lignes_b[i:k + 1])
            cote = _cote(lignes, i)
            # maquette : « 800 000,00 0,00 0,00 0,00 800 000,00 » = crédits déjà au budget, rien de nouveau voté
            zeros = len(re.findall(r"(?<![\d.,])0[,.]00(?!\d)", " ".join(lignes[i:k + 1])))
            if zeros >= 2 and len({abs(x) for x in ms}) == 1:
                cote = "deja au budget"
            hits.append({"page": p, "ligne": texte[:220], "montants": ms[:6], "cote": cote,
                         "compte_1641": bool(COMPTE.search(l))})
        flat = plat(" ".join(lignes_b))
        for m in NARRATIF.finditer(flat):
            v = montants(m.group(1) + " €")
            if v:
                a = max(0, m.start() - 60)
                hits.append({"page": p, "ligne": flat[a:m.end() + 40].strip()[:220], "montants": v,
                             "cote": "recette", "compte_1641": False, "phrase": True})
    # une même ligne lue deux fois (compte et chapitre) ne compte qu'une fois
    vus, out = set(), []
    for h in hits:
        k = (h["page"], h["ligne"][:80])
        if k not in vus:
            vus.add(k)
            out.append(h)
    return out


def verdict(hits):
    """Montant d'emprunt nouveau le plus probable et force de la piste (forte : recette lue ; à vérifier : colonne
    non lue ; None : seulement des remboursements ou des écritures d'ordre)."""
    recettes = [h for h in hits if h["cote"] == "recette" and max(h["montants"]) >= 1000]
    inconnus = [h for h in hits if h["cote"] == "inconnu" and max(h["montants"]) >= 1000]
    if recettes:
        return max(max(h["montants"]) for h in recettes), "forte"
    if inconnus:
        return max(max(h["montants"]) for h in inconnus), "à vérifier"
    return None, None


def analyse(octets_liste, ocr=True, max_ocr=4):
    """Analyse un acte (document principal et annexes) ; renvoie None s'il n'y a aucune ligne d'emprunt."""
    tous, ocr_faits, non_lus, n_pages = [], 0, 0, 0
    for n, b in enumerate(octets_liste):
        textes, faits, restes = pages_texte(b, ocr=ocr, max_ocr=max_ocr)
        ocr_faits += len(faits)
        non_lus += len(restes)
        n_pages += len(textes)
        for h in lignes_emprunt(textes):
            h["document"] = n
            tous.append(h)
    montant, force = verdict(tous)
    if force == "forte" and n_pages > 12:
        force = "à vérifier"          # maquette budgétaire complète : la colonne du vote se vérifie à l'œil
    return {"lignes": tous[:8], "montant": montant, "force": force, "pages_ocr": ocr_faits,
            "pages_scannees_non_lues": non_lus}


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print(f, json.dumps(analyse([open(f, "rb").read()]), ensure_ascii=False, indent=1))
