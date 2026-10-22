"""Appels d'offres : consultations ouvertes sur les profils d'acheteur Atexo (Mégalis Bretagne,
Pays de la Loire) et rattachement des acheteurs (Atexo, BOAMP) aux collectivités du périmètre.

Les plateformes qui refusent les robots (achatpublic, centreofficielles, medialex) ne sont pas lues.
"""
import html
import re
import urllib.parse

from net import get
from perimetre import norm

ATEXO = {
    "Mégalis Bretagne (marchés)": "https://marches.megalis.bretagne.bzh",
    "Marchés publics Pays de la Loire": "https://marchespublics.paysdelaloire.fr",
}
MOTS = ["emprunt", "prêt", "financement", "trésorerie", "bancaire", "banque", "crédit", "dette"]
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
    a = re.sub(r"^(la |le |les )", "", a)
    cands = idx.get(a, [])
    m = re.match(r"(communaute (de communes|d agglomeration|urbaine)|cc|ca) (du |de la |de l |des |de |d )?(.*)", a)
    if m:
        cands = idx.get("epci " + m.group(4), []) + cands
    cands = [s for s, d in cands if not deps or d in deps]
    return cands[0] if len(cands) == 1 or (cands and m) else None


def collecte(d, communes, epcis, entite, stats):
    """Consultations encore ouvertes au jour d dont l'objet porte sur un emprunt ou un financement bancaire."""
    idx = index_acheteurs(communes, epcis)
    out, vus = [], set()
    for nom, base in ATEXO.items():
        lus, err = 0, 0
        for mot in MOTS:
            try:
                rows, _ = atexo(base, mot)
            except Exception:
                err += 1
                continue
            for r in rows:
                if r["lien"] in vus:
                    continue
                vus.add(r["lien"])
                lus += 1
                if not STRICT.search(norm(f"{r['intitule']} {r['objet']}")):
                    continue
                siren = rattacher(r["acheteur"], None, idx)
                r.update(source=nom, type_signal="consultation ouverte", plateforme=nom,
                         entite=entite(siren, communes, epcis) if siren else
                         {"eligible": False, "motif": "Acheteur non rattaché à une commune ou un EPCI du périmètre"})
                out.append(r)
        stats[nom] = (f"{len(MOTS)} recherches ({err} en échec), {lus} consultations ouvertes distinctes lues, "
                      f"{sum(1 for r in out if r['source'] == nom)} sur un financement bancaire")
    return out
