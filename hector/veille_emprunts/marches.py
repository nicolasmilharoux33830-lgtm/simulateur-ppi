"""Appels d'offres : consultations ouvertes ou tout juste closes sur les profils d'acheteur
(Mégalis Bretagne, Pays de la Loire, e-marchespublics, AWS marches-publics.info) et rattachement des
acheteurs (plateformes, BOAMP) aux collectivités du périmètre.

Le robot se présente sous son nom et respecte robots.txt. Les plateformes qui refusent les robots ou
imposent un défi anti-robot (achatpublic, centreofficielles, medialex) ne sont pas lues.
"""
import html
import http.cookiejar
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from net import get
from perimetre import DEPT2REG, norm

USER_AGENT = "Mozilla/5.0 (compatible; HectorVeille/1.0; veille des actes publics des collectivites)"

ATEXO = {
    "Mégalis Bretagne (marchés)": "https://marches.megalis.bretagne.bzh",
    "Marchés publics Pays de la Loire": "https://marchespublics.paysdelaloire.fr",
}
MOTS = ["emprunt", "prêt", "financement", "trésorerie", "bancaire", "banque", "crédit", "dette", "assurance emprunteur"]
# Objet qui parle vraiment d'un financement bancaire (et pas de « prêt de matériel » ou de « prétraitement »)
STRICT = re.compile(r"\b(emprunts?|prets? (bancaires?|a long terme|a moyen terme|relais|a taux)|financement bancaire|"
                    r"financements? (des|de l.|du) (investissement|programme|travaux)|lignes? de tresorerie|"
                    r"consultation bancaire|etablissements? (bancaires?|de credit|financiers?)|services? bancaires?|"
                    r"offres? de prets?|concours financiers?|refinancement|renegociation|reamenagement de (la )?dette|"
                    r"gestion de (la )?dette|credit[- ]bail)\b")
MOIS = {"janv": 1, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "aout": 8, "sept": 9,
        "oct": 10, "nov": 11, "dec": 12}


def _txt(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _date(bloc):
    j = re.search(r'class="day[^"]*">\s*<span>(\d+)</span>', bloc)
    m = re.search(r'class="month">\s*<span>([^<]+)</span>', bloc)
    a = re.search(r'class="year">\s*<span>(\d{4})</span>', bloc)
    if not (j and m and a):
        return None
    mois = MOIS.get(norm(m.group(1)).strip(". ")[:4].rstrip("."), 0) or MOIS.get(norm(m.group(1))[:3], 0)
    return f"{a.group(1)}-{mois:02d}-{int(j.group(1)):02d}" if mois else None


def atexo(base, mot):
    u = f"{base}/?page=Entreprise.EntrepriseAdvancedSearch&searchAnnCons&keyWord={urllib.parse.quote(mot)}"
    h = get(u, tries=6, timeout=60).decode("utf-8", "ignore")
    total = re.search(r'nombreElement">(\d+)', h)
    out = []
    for bloc in re.split(r'<div id="row-consultation-', h)[1:]:
        ref = re.search(r'refCons" value="(\d+)"', bloc)
        org = re.search(r'orgCons" value="([^"]+)"', bloc)
        intit = re.search(r'truncate">\s*<span[^>]*title="([^"]*)"', bloc)
        objet = re.search(r'panelBlocObjet".*?title="([^"]*)"', bloc, re.S)
        orga = re.search(r'panelBlocDenomination".*?title="([^"]*)"', bloc, re.S)
        refint = re.search(r'BEGIN REFERENCE \| INTITULE -->\s*<div[^>]*>\s*<div class="small pull-left">\s*([^<]+?)\s*</div>',
                           bloc)
        fin = bloc.split('cons_dateEnd', 1)
        heure = re.search(r'<label title="Durée"[^>]*>([^<]+)</label>', fin[1]) if len(fin) > 1 else None
        proc = re.search(r'cons_procedure">\s*<abbr[^>]*title="([^"]*)"', bloc)
        cat = re.search(r'cons_categorie">\s*<span>([^<]*)</span>', bloc)
        lieu = re.search(r'panelBlocLieuxExec".*?<span>\s*([^<]+)</span>', bloc, re.S)
        out.append({
            "reference": refint.group(1).strip() if refint else None,
            "intitule": _txt(intit.group(1)) if intit else None,
            "objet": _txt(objet.group(1)) if objet else None,
            "acheteur": _txt(orga.group(1)) if orga else None,
            "procedure": _txt(proc.group(1)) if proc else None,
            "categorie": _txt(cat.group(1)) if cat else None,
            "lieu": _txt(lieu.group(1)) if lieu else None,
            "date_publication": _date(fin[0]),
            "date_limite": ((_date(fin[1]) or "") + (" " + heure.group(1).strip() if heure else "")).strip()
            if len(fin) > 1 else None,
            "lien": f"{base}/entreprise/consultation/{ref.group(1)}?orgAcronyme={org.group(1)}" if ref and org else u,
        })
    return out, int(total.group(1)) if total else len(out)


def _session():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", USER_AGENT), ("Accept-Language", "fr")]
    return op


def _jj(s):
    """'16/11/2026 à 12h00' ou '30/10/26 à 12h00' -> '2026-11-16 12:00'."""
    m = re.search(r"(\d{2})/(\d{2})/(\d{2,4})(?:\s*à\s*(\d{1,2})h(\d{2}))?", s or "")
    if not m:
        return None
    a = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
    h = f" {int(m.group(4)):02d}:{m.group(5)}" if m.group(4) else ""
    return f"{a}-{m.group(2)}-{m.group(1)}{h}"


def emarches(mot, pages=4):
    """e-marchespublics.com : recherche par mot-clé (formulaire de session du site)."""
    op = _session()
    h = op.open("https://www.e-marchespublics.com/appel-offre", timeout=40).read().decode("utf-8", "ignore")
    csrf = re.search(r'data-csrf="([^"]+)"', h).group(1)

    def post(champ, valeur):
        data = urllib.parse.urlencode({"_token": csrf, champ: valeur}).encode()
        req = urllib.request.Request("https://www.e-marchespublics.com/notices/search/update", data=data,
                                     headers={"X-Requested-With": "XMLHttpRequest", "X-CSRF-TOKEN": csrf})
        return json.loads(op.open(req, timeout=60).read())

    j = post("what", mot)
    total, out = j.get("nbResult", 0), []
    for page in range(1, pages + 1):
        if page > 1:
            if (page - 1) * 10 >= total:
                break
            j = post("page", str(page))
        for bloc in j["view"].split('<div class="box">')[1:]:
            titre = re.search(r'texttruncate noselect[^>]*>\s*(.*?)\s*</div>', bloc, re.S)
            ach = re.search(r'box-body-top">\s*<span>(.*?)</span>', bloc, re.S)
            lieu = re.search(r'fa-map-marker-alt"></i>\s*([^<]*)', bloc)
            proc = re.search(r'fa-file-alt"></i>\s*([^<]*)', bloc)
            lim = re.findall(r'Date limite de l.offre :\s*<span class="pink">\s*([^<]*?)\s*</span>', bloc, re.S)
            lien = re.search(r'href=(/appel-offre/[^\s>]+)', bloc)
            cp = re.match(r"\s*(\d{2})", lieu.group(1)) if lieu else None
            out.append({"intitule": _txt(titre.group(1)) if titre else None, "objet": None,
                        "acheteur": _txt(ach.group(1)) if ach else None, "lieu": _txt(lieu.group(1)) if lieu else None,
                        "departements": [cp.group(1)] if cp else [], "procedure": _txt(proc.group(1)) if proc else None,
                        "date_publication": None, "date_limite": _jj(lim[0]) if lim else None,
                        "lien": "https://www.e-marchespublics.com" + lien.group(1) if lien else None})
    return out, total


AWS_DEPS = ",".join(str(int(d)) for d in sorted(DEPT2REG))


def aws(mot, etat="EC"):
    """AWS marches-publics.info : annonces en cours (EC) ou expirées (A) des 20 départements."""
    data = urllib.parse.urlencode({"txtLibre": mot, "IDE": etat, "IDN": "X", "IDP": "X", "IDR": AWS_DEPS,
                                   "Rechercher": "Rechercher"}).encode()
    req = urllib.request.Request("https://www.marches-publics.info/Annonces/lister", data=data,
                                 headers={"User-Agent": USER_AGENT, "Accept-Language": "fr"})
    h = _session().open(req, timeout=60).read().decode("utf-8", "ignore")
    out = []
    for bloc in re.split(r'fa fa-calendar', h)[1:]:
        pub = re.search(r"Publié le\s*([\d/]+)", bloc)
        lim = re.search(r"Date limite : le\s*([^<]+)", bloc)
        ach = re.search(r'<h2 class="h2-avis">\s*(.*?)\s*(?:\(\s*(\d[\dAB]\d{3})\s*\))?\s*</h2>', bloc, re.S)
        boite = re.search(r"id='titre_box'>(.*?)</div>\s*</div>\s*</div>", bloc, re.S)
        ref = re.search(r"ref-acheteur\">\s*(.*?)</div>", boite.group(1), re.S) if boite else None
        titre = re.sub(r'(?s)<div class="col-12 col-md-12 ref-acheteur">.*?</div>', " ", boite.group(1)) if boite else None
        lien = re.search(r'href="(/Annonces/MPI-pub-[^"]+)"', bloc)
        if not (ach and lien):
            continue
        insee = ach.group(2)
        out.append({"intitule": _txt(titre) if titre else None, "objet": None,
                    "reference": _txt(ref.group(1)) if ref else None,
                    "acheteur": _txt(ach.group(1)), "code_insee_acheteur": insee,
                    "departements": [insee[:2]] if insee else [], "procedure": None,
                    "date_publication": _jj(pub.group(1)) if pub else None,
                    "date_limite": _jj(lim.group(1)) if lim else None,
                    "lien": "https://www.marches-publics.info" + lien.group(1)})
    return out


def _cle(s):
    return re.sub(r"[^a-z0-9]+", " ", norm(s)).strip()


def index_acheteurs(communes, epcis):
    """Nom normalisé -> [(siren, département)] ; les EPCI aussi sous leur nom sans « CC », « CA »..."""
    idx = {}
    for s, c in communes.items():
        idx.setdefault(_cle(c["nom"]), []).append((s, c["dept"]))
    for s, e in epcis.items():
        k = _cle(e["nom"])
        idx.setdefault(k, []).append((s, e["dept"]))
        court = re.sub(r"^(cc|ca|cu|communaute (de communes|d agglomeration|urbaine)) (du |de la |de l |des |de |d )?",
                       "", k)
        idx.setdefault("epci " + court, []).append((s, e["dept"]))
    return idx


def rattacher(acheteur, deps, idx):
    """SIREN de la collectivité qui achète, ou None. deps : départements possibles (liste ou None)."""
    a = _cle(re.sub(r"\(.*?\)", " ", acheteur or ""))
    cp = re.search(r"\((\d{2})\d{3}", acheteur or "")
    deps = set(deps or []) | ({cp.group(1)} if cp else set())
    a = re.sub(r"^(mairie|ville|commune) (de la |de l |des |du |de |d )?", "", a)
    a = re.sub(r"^(la |le |les |l )", "", a)
    if re.search(r"\b(agglo|agglomeration|communaute|metropole|intercom)\b", a) and not a.startswith(("cc ", "ca ", "communaute ")):
        cands = idx.get("epci " + a, []) + idx.get(a, [])
        cands = list(dict.fromkeys(s for s, d in cands if not deps or d in deps))
        return cands[0] if len(cands) == 1 else None
    cands = []
    for k in (a, "le " + a, "la " + a, "les " + a, "l " + a):
        cands += idx.get(k, [])
    m = re.match(r"(communaute (de communes|d agglomeration|urbaine)|cc|ca) (du |de la |de l |des |de |d )?(.*)", a)
    if m:
        cands = idx.get("epci " + m.group(4), []) + cands
    elif not cands:
        cands = idx.get("epci " + a, [])
    cands = list(dict.fromkeys(s for s, d in cands if not deps or d in deps))
    return cands[0] if len(cands) == 1 or (cands and m) else None


def collecte(d, communes, epcis, entite, stats):
    """Consultations ouvertes (ou closes depuis moins de 15 jours) dont l'objet porte sur un emprunt,
    une ligne de trésorerie ou des services bancaires."""
    idx = index_acheteurs(communes, epcis)
    insee = {c["code_insee"]: s for s, c in communes.items()}
    out, vus = [], set()

    def garde(r, nom):
        if not r.get("lien") or r["lien"] in vus:
            return False
        vus.add(r["lien"])
        if not STRICT.search(norm(f"{r.get('intitule')} {r.get('objet')}")):
            return False
        lim = (r.get("date_limite") or "")[:10]
        if lim and lim < (d - timedelta(days=15)).isoformat():
            return False
        siren = insee.get(r.get("code_insee_acheteur")) or rattacher(r.get("acheteur"), r.get("departements"), idx)
        if not siren and r.get("departements") and not set(r["departements"]) & set(DEPT2REG):
            return False
        r.update(source=nom, plateforme=nom,
                 type_signal="consultation ouverte" if not lim or lim >= d.isoformat() else "consultation close il y a moins de 15 jours",
                 entite=entite(siren, communes, epcis) if siren else
                 {"eligible": False, "motif": "Acheteur non rattaché à une commune ou un EPCI du périmètre"})
        out.append(r)
        return True

    for nom, base in ATEXO.items():
        lus, err = 0, 0
        for mot in MOTS:
            try:
                rows, _ = atexo(base, mot)
            except Exception:
                err += 1
                continue
            for r in rows:
                lus += r["lien"] not in vus
                garde(r, nom)
        stats[nom] = (f"{len(MOTS)} recherches ({err} en échec), {lus} consultations ouvertes distinctes lues, "
                      f"{sum(1 for r in out if r['source'] == nom)} sur un financement bancaire")
    nom = "e-marchespublics.com"
    lus, err, tot = 0, 0, 0
    for mot in MOTS:
        try:
            rows, n = emarches(mot)
        except Exception:
            err += 1
            continue
        tot += n
        for r in rows:
            lus += r["lien"] not in vus
            garde(r, nom)
    stats[nom] = (f"{len(MOTS)} recherches ({err} en échec), {tot} annonces trouvées, {lus} lues, "
                  f"{sum(1 for r in out if r['source'] == nom)} sur un financement bancaire")
    nom = "AWS marches-publics.info"
    lus, err = 0, 0
    for mot in MOTS:
        for etat in ("EC", "A"):
            try:
                rows = aws(mot, etat)
            except Exception:
                err += 1
                continue
            for r in rows:
                lus += r["lien"] not in vus
                garde(r, nom)
    stats[nom] = (f"{2 * len(MOTS)} recherches en cours et expirées ({err} en échec), {lus} annonces des 20 "
                  f"départements lues, {sum(1 for r in out if r['source'] == nom)} sur un financement bancaire")
    return out
