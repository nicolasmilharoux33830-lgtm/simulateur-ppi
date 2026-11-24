"""Délibérations publiées en open data au format national SCDL (« Délibérations ») sur data.gouv.fr.

Beaucoup de collectivités et de tiers de télétransmission (Gironde Numérique, opérateurs régionaux, communes
et syndicats qui publient eux-mêmes) déposent leurs délibérations sur data.gouv.fr dans ce format commun,
avec le SIRET de la collectivité, la date, l'objet et le code « matière » ACTES (7.3 = emprunts).
Aucun site n'est lu : seulement l'API publique de data.gouv.fr et les fichiers qu'elle indique.

Chaque jour, on ne relit que les fichiers mis à jour depuis la veille, et on garde les délibérations
récentes (moins de AGE_MAX jours) d'une collectivité du périmètre qui parlent d'emprunt, de banque ou de
trésorerie, ou qui sont classées 7.3.
"""
import csv
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta

from net import get, jget
from perimetre import norm

API = "https://www.data.gouv.fr/api/1/datasets/"
SCHEMA = "scdl/deliberations"
AGE_MAX = 45
MAX_FICHIERS = 80
MAX_OCTETS = 25_000_000
DUREE_MAX = 420
KW = re.compile(r"\b(emprunt|emprunts|pret|prets|tresorerie|refinanc|renegoci|reamenag|banque|bancaire|bancaires|"
                r"etablissements? financiers?|organismes? preteurs?|financement bancaire)\b")
KW_EXCLU = re.compile(r"virement|fongibilit|pret d.honneur|pret de (materiel|salle|vehicule|local)|garantie d.emprunt|"
                      r"mise a disposition|circulation|permis de construire")


def _date(s):
    s = (s or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def fichiers_recents(depuis, stats):
    """Ressources SCDL Délibérations (CSV ou JSON) modifiées depuis `depuis` : [(organisation, titre, url)]."""
    out, page, vus = [], 1, set()
    while page <= 15 and len(out) < MAX_FICHIERS:
        d = jget(API, {"schema": SCHEMA, "page_size": 100, "page": page, "sort": "-last_update"},
                 tries=6, timeout=60)
        rows = d.get("data") or []
        if not rows:
            break
        plus_ancien = None
        for ds in rows:
            maj = _date(ds.get("last_update") or ds.get("last_modified"))
            plus_ancien = maj if plus_ancien is None or (maj and maj < plus_ancien) else plus_ancien
            org = ((ds.get("organization") or {}).get("name")) or ((ds.get("owner") or {}).get("slug")) or ""
            for r in ds.get("resources") or []:
                sch = ((r.get("schema") or {}).get("name")) or ""
                fmt = (r.get("format") or "").lower()
                quand = _date(r.get("last_modified") or r.get("created_at"))
                if (sch and sch != SCHEMA) or fmt not in ("csv", "json") or not quand or quand < depuis:
                    continue
                if (r.get("filesize") or 0) > MAX_OCTETS or r["url"] in vus:
                    continue
                vus.add(r["url"])
                out.append((org, ds.get("title") or "", r["url"], fmt))
        if plus_ancien and plus_ancien < depuis:
            break
        page += 1
    stats["_scdl_fichiers"] = len(out)
    return out[:MAX_FICHIERS]


def lignes(contenu, fmt):
    """Lignes d'un fichier SCDL, clés en majuscules."""
    txt = contenu.decode("utf-8-sig", "ignore")
    if fmt == "json":
        try:
            d = json.loads(txt)
        except ValueError:
            return []
        rows = d if isinstance(d, list) else (d.get("data") or d.get("records") or d.get("results") or [])
        return [{str(k).upper(): v for k, v in (r.get("fields", r) if isinstance(r, dict) else {}).items()}
                for r in rows if isinstance(r, dict)]
    try:
        sep = csv.Sniffer().sniff(txt[:5000], delimiters=";,\t").delimiter
    except csv.Error:
        sep = ";"
    return [{str(k).strip().upper(): (v or "") for k, v in r.items() if k}
            for r in csv.DictReader(io.StringIO(txt), delimiter=sep)]


def candidat(r, org, d, communes, epcis, entite):
    siret = re.sub(r"\D", "", str(r.get("COLL_SIRET") or ""))
    siren = siret[:9]
    if len(siren) != 9 or not (siren in communes or siren in epcis):
        return None
    objet = str(r.get("DELIB_OBJET") or "").strip()
    matiere = str(r.get("DELIB_MATIERE_CODE") or "").strip()
    o = norm(objet)
    if not (matiere.startswith("7.3") or KW.search(o)) or KW_EXCLU.search(o):
        return None
    jour = _date(r.get("DELIB_DATE"))
    if not jour or jour > d + timedelta(days=1):
        return None
    age = (d - jour).days
    if age > AGE_MAX:
        return None
    lien = str(r.get("DELIB_URL") or "").strip()
    c = {"source": f"Open data délibérations (data.gouv.fr, {org})" if org else "Open data délibérations (data.gouv.fr)",
         "type_signal": "acte", "siren": siren, "objet": objet,
         "classification": f"{matiere} {r.get('DELIB_MATIERE_NOM') or ''}".strip(),
         "date_acte": jour.isoformat(), "date_publication": d.isoformat(),
         "publie_le": str(r.get("PREF_DATE") or "")[:10] or None, "id_publication": r.get("DELIB_ID"),
         "typologie": "Délibération", "lien": lien or None, "annexes": [], "budget_emprunt": None,
         "entite": entite(siren, communes, epcis), "age_jours": age,
         "budget": r.get("BUDGET_NOM") or None}
    return c


def collecte(d, outdir, communes, epcis, entite, stats):
    """Délibérations SCDL récentes d'une collectivité du périmètre sur l'emprunt ou la banque."""
    t0, out, vus, n_lignes, n_fichiers, err = time.time(), [], set(), 0, 0, 0
    try:
        res = fichiers_recents(d, stats)
    except Exception as e:
        stats["Open data délibérations (data.gouv.fr)"] = f"ERREUR : {str(e)[:120]}"
        return out
    for org, titre, url, fmt in res:
        if time.time() - t0 > DUREE_MAX:
            break
        try:
            rows = lignes(get(url, tries=4, timeout=90), fmt)
        except Exception:
            err += 1
            continue
        n_fichiers += 1
        n_lignes += len(rows)
        for r in rows:
            c = candidat(r, org, d, communes, epcis, entite)
            if not c:
                continue
            cle = (c["siren"], c["id_publication"] or c["objet"], c["date_acte"])
            if cle in vus:
                continue
            vus.add(cle)
            if c["lien"] and c["lien"].lower().endswith(".pdf") and c["entite"].get("eligible") and outdir:
                fn = f"{outdir}/pdf/{c['siren']}_scdl_{len(out)}.pdf"
                try:
                    open(fn, "wb").write(get(c["lien"], tries=4, timeout=90))
                    c["pdf_locaux"] = [fn]
                except Exception:
                    c["pdf_locaux"] = []
            out.append(c)
    stats["Open data délibérations (data.gouv.fr)"] = (
        f"{n_fichiers} fichiers mis à jour lus ({n_lignes} délibérations), {len(out)} sur l'emprunt ou la banque "
        f"dans le périmètre" + (f", {err} fichiers illisibles" if err else ""))
    stats.pop("_scdl_fichiers", None)
    return out


# ---------- plateformes qui publient les délibérations au format SCDL, un fichier par collectivité ----------
# département -> modèle d'URL (fichier public, sans compte). Gironde Numérique : communes, EPCI et syndicats
# girondins adhérents à son service Open Data (Licence Ouverte 2.0).
DIRECT = {
    "33": ("Gironde Numérique", "https://api-opendata.girondenumerique.fr/datasets/{siren}/deliberations.csv"),
}
ADHERENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adherents_scdl.json")
PAUSE = 2.1          # Gironde Numérique : 30 requêtes par minute au plus


def decouvrir(communes, epcis, sortie, duree_max=5400):
    """Collectivités du périmètre qui ont un fichier de délibérations sur une plateforme DIRECT (tâche de nuit)."""
    out, t0, n = {}, time.time(), 0
    for siren, e in list(communes.items()) + list(epcis.items()):
        if e.get("dept") not in DIRECT or time.time() - t0 > duree_max:
            continue
        nom, modele = DIRECT[e["dept"]]
        url = modele.format(siren=siren)
        n += 1
        try:
            tete = get(url, tries=2, timeout=40)[:400].decode("utf-8-sig", "ignore").upper()
            if "COLL_SIRET" in tete or "DELIB_OBJET" in tete:
                out[siren] = {"plateforme": nom, "url": url, "nom": e.get("nom")}
        except Exception:
            pass
        time.sleep(PAUSE)
    json.dump(out, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{len(out)} collectivités publient leurs délibérations ({n} testées)")


def collecte_directe(d, outdir, communes, epcis, entite, stats, duree_max=900):
    """Fichiers de délibérations des adhérents connus (adherents_scdl.json), lus un par un, poliment."""
    try:
        adh = json.load(open(ADHERENTS, encoding="utf-8"))
    except (OSError, ValueError):
        return []
    adh = {s: a for s, a in adh.items() if (communes.get(s) or epcis.get(s) or {}).get("dept") in DIRECT}
    if not adh:
        return []
    t0, out, lus, err, nom = time.time(), [], 0, 0, ""
    for siren, a in adh.items():
        if time.time() - t0 > duree_max:
            break
        nom = a.get("plateforme", "")
        try:
            rows = lignes(get(a["url"], tries=3, timeout=60), "csv")
            lus += 1
        except Exception:
            err += 1
            time.sleep(PAUSE)
            continue
        for r in rows:
            c = candidat(r, nom, d, communes, epcis, entite)
            if c and c["age_jours"] <= 10:      # le fichier contient tout l'historique : les décisions récentes seulement
                c["source"] = f"{nom} (délibérations open data)"
                if c["lien"] and c["lien"].lower().endswith(".pdf") and c["entite"].get("eligible") and outdir:
                    fn = f"{outdir}/pdf/{siren}_gn_{len(out)}.pdf"
                    try:
                        open(fn, "wb").write(get(c["lien"], tries=3, timeout=90))
                        c["pdf_locaux"] = [fn]
                    except Exception:
                        c["pdf_locaux"] = []
                out.append(c)
        time.sleep(PAUSE)
    stats[f"{nom} (délibérations open data)"] = (f"{lus} collectivités lues sur {len(adh)} adhérentes"
                                                 + (f", {err} injoignables" if err else "")
                                                 + f", {len(out)} délibérations récentes sur l'emprunt ou la banque")
    return out


def _test():
    """Contrôle hors réseau du découpage et du filtre."""
    csv_txt = ("COLL_NOM;COLL_SIRET;DELIB_ID;DELIB_DATE;DELIB_MATIERE_CODE;DELIB_MATIERE_NOM;DELIB_OBJET;DELIB_URL\n"
               "SIVOM X;25330001500011;D1;2026-11-20;7.3;Emprunts;Consultation des établissements bancaires pour un emprunt;"
               "https://x/d1.pdf\n"
               "Commune Y;21330001500011;D2;2026-11-20;1.1;Marchés;Attribution du marché de voirie;\n")
    rows = lignes(csv_txt.encode(), "csv")
    ent = (lambda s, c, e: {"siren": s, "eligible": True})
    got = [candidat(r, "Test", date(2026, 11, 24), {"213300015": {}}, {"253300015": {}}, ent) for r in rows]
    assert got[0] and got[0]["siren"] == "253300015" and got[1] is None, got
    gn = lignes(('"COLL_NOM","COLL_SIRET","DELIB_ID","DELIB_DATE","DELIB_MATIERE_CODE","DELIB_MATIERE_NOM","DELIB_OBJET"\n'
                 '"SIAEP TEST",25330001500011,X1,21/11/2026,7.3,"Emprunts","AUTORISATION DE CONSULTER LES BANQUES"\n').encode(), "csv")
    g = candidat(gn[0], "Gironde Numérique", date(2026, 11, 24), {}, {"253300015": {}}, ent)
    assert g and g["age_jours"] == 3, g
    print("scdl ok")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--decouvrir":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import veille
        c, e = veille.referentiel()
        decouvrir(c, e, sys.argv[2])
    else:
        _test()
