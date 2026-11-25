"""Tâche de nuit d'Hector (hors routine du matin, qui doit rester sous 50 minutes) : collectes lourdes,
fichiers déposés dans le dépôt pour que la routine les télécharge.

  python3 nuit.py [--tout]

Chaque nuit : marchés attribués (DECP) -> signaux_decp.json.
Le dimanche, ou si le fichier manque : syndicats du périmètre (SIRENE) -> syndicats.json.
Le dimanche (ou --tout) : subventions (Fonds vert) -> subventions.json ; registre des prêts, lignes de
trésorerie et adhésions à l'Agence France Locale -> registre.json ; entités PanneauPocket ->
panneaupocket.json ; plan des sites des mairies -> plan_sites.json.
Le premier dimanche du mois (ou --tout) : recherche des sites absents de l'annuaire -> sites.json ;
pages Facebook et applications officielles (Annuaire de l'administration) -> reseaux.json.
Un fichier n'est remplacé que si sa nouvelle version est complète (sinon l'ancien reste en place).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import date

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from perimetre import PLATEFORMES  # noqa: E402
PY = sys.executable


def lance(args, sortie, minimum, timeout):
    """Exécute une collecte dans un fichier temporaire ; ne remplace le fichier du dépôt que si le
    résultat dépasse `minimum` octets."""
    tmp = sortie + ".nouveau"
    t0 = time.time()
    try:
        r = subprocess.run([PY] + args(tmp), cwd=ICI, capture_output=True, text=True, timeout=timeout)
        log = (r.stdout or "")[-400:] + (r.stderr or "")[-400:]
    except subprocess.TimeoutExpired:
        log = "délai dépassé"
    ok = os.path.exists(tmp) and os.path.getsize(tmp) >= minimum
    if ok:
        shutil.move(tmp, os.path.join(ICI, sortie))
    elif os.path.exists(tmp):
        os.remove(tmp)
    print(f"{'OK' if ok else 'ÉCHEC'} {sortie} ({round(time.time() - t0)} s) : {log.strip()[-300:]}", flush=True)
    return ok


def plan_sites():
    """Nouveau plan des sites ; un site injoignable cette nuit garde ses pages de la fois précédente
    (un site refusant désormais la lecture, lui, les perd)."""
    ok = lance(lambda f: ["mairies.py", "--plan", "sites.json", f], "plan_sites.nouveau.json", 500_000, 7200)
    src, tmp = os.path.join(ICI, "plan_sites.json"), os.path.join(ICI, "plan_sites.nouveau.json")
    if not ok:
        return False
    ancien, nouveau = json.load(open(src)), json.load(open(tmp))
    gardes = 0
    for k, p in nouveau.items():
        if not p["pages"] and p["etat"].startswith("injoignable") and ancien.get(k, {}).get("pages"):
            nouveau[k] = ancien[k]
            gardes += 1
    json.dump(nouveau, open(src, "w"), ensure_ascii=False, indent=0)
    os.remove(tmp)
    print(f"plan_sites.json : {sum(1 for p in nouveau.values() if p['pages'])} sites avec pages utiles "
          f"({gardes} injoignables cette nuit gardés)", flush=True)
    return True


def decouverte(duree=7200):
    """Sites des communes absentes de l'annuaire : travail sur une copie, gardée si elle n'a rien perdu."""
    src, tmp = os.path.join(ICI, "sites.json"), os.path.join(ICI, "sites.travail.json")
    shutil.copy(src, tmp)
    try:
        subprocess.run([PY, "mairies.py", "--decouvrir", tmp], cwd=ICI, timeout=duree, capture_output=True)
    except subprocess.TimeoutExpired:
        pass
    avant, apres = len(json.load(open(src))), len(json.load(open(tmp))) if os.path.exists(tmp) else 0
    ok = apres >= avant
    if ok:
        shutil.move(tmp, src)
    for f in (tmp, tmp + ".decouverte"):
        if os.path.exists(f):
            os.remove(f)
    print(f"{'OK' if ok else 'ÉCHEC'} sites.json : {avant} -> {apres} sites", flush=True)
    return ok


def main():
    tout = "--tout" in sys.argv
    jour = date.today()
    # le bloc hebdomadaire tourne aussi s'il manque un fichier de base (région nouvelle ou fichier perdu)
    manque = any(not os.path.exists(os.path.join(ICI, f)) for f in
                 ("plan_sites.json", "panneaupocket.json", "reseaux.json", "subventions.json", "registre.json"))
    try:      # un plan qui ne couvre pas 80 % des sites connus est à refaire
        manque = manque or len(json.load(open(os.path.join(ICI, "plan_sites.json")))) < 0.8 * len(
            json.load(open(os.path.join(ICI, "sites.json"))))
    except (OSError, ValueError):
        manque = True
    dimanche = jour.weekday() == 6 or manque
    bilan = {"jour": jour.isoformat()}
    synd = os.path.join(ICI, "syndicats.json")
    if dimanche or tout or not os.path.exists(synd) or os.path.getsize(synd) < 1000:
        # syndicats (SIVU, SIVOM, syndicats mixtes) d'abord : les collectes suivantes les incluent
        bilan["syndicats"] = lance(lambda f: ["syndicats.py", f], "syndicats.json", 20_000, 1800)
    bilan["decp"] = lance(lambda f: ["decp.py", f, "365"], "signaux_decp.json", 50_000, 1800)
    if dimanche or tout:
        bilan["subventions"] = lance(lambda f: ["subventions.py", f], "subventions.json", 20_000, 1200)
        if PLATEFORMES:      # pas de registre des actes dans toutes les régions
            bilan["registre"] = lance(lambda f: ["registre.py", f, "14"], "registre.json", 50_000, 7200)
        bilan["panneaupocket"] = lance(lambda f: ["panneaupocket.py", "--liste", f], "panneaupocket.json",
                                       50_000, 1800)
        bilan["plan"] = plan_sites()          # le plus utile d'abord : la session de nuit a un temps limité
        if jour.day <= 7 or tout:
            # annuaire PUIS sites des mairies : sans la seconde étape, les fils Facebook recopiés sur les sites et
            # les pages trouvées sur les sites disparaissent (perte constatée le 01/11)
            bilan["reseaux"] = lance(lambda f: ["reseaux.py", f, "sites.json"], "reseaux.json", 20_000, 5400)
        for f in os.listdir(ICI):
            if f.endswith(".part"):
                os.remove(os.path.join(ICI, f))
    # chaque nuit : sites des communes, EPCI et syndicats encore inconnus (2 500 au plus, échecs retentés
    # après 30 jours), puis repérage des pages utiles des nouveaux sites
    bilan["sites"] = decouverte(3600)
    try:
        bilan["plan_nouveaux"] = subprocess.run([PY, "mairies.py", "--plan-nouveaux", "sites.json", "plan_sites.json"],
                                                cwd=ICI, capture_output=True, text=True, timeout=2400).returncode == 0
    except subprocess.TimeoutExpired:
        bilan["plan_nouveaux"] = False
    # Illiwap (stations repérées sur les sites des mairies) et Annuaire des Collectivités : 1 500 communes par nuit
    try:
        bilan["illiwap_annuaire"] = subprocess.run([PY, "applis.py", "--decouvrir", "1500"], cwd=ICI,
                                                   capture_output=True, text=True, timeout=3600).returncode == 0
    except subprocess.TimeoutExpired:
        bilan["illiwap_annuaire"] = False
    # communes présentes sur IntraMuros (actualités et agenda publics)
    im = os.path.join(ICI, "intramuros.json")
    if dimanche or tout or not os.path.exists(im) or os.path.getsize(im) < 50:
        bilan["intramuros"] = lance(lambda f: ["intramuros.py", "--liste", f], "intramuros.json", 1_000, 5400)
    # délibérations open data publiées collectivité par collectivité (Gironde Numérique...) : qui publie ?
    adh = os.path.join(ICI, "adherents_scdl.json")
    if dimanche or tout or not os.path.exists(adh) or os.path.getsize(adh) < 50:
        bilan["adherents_scdl"] = lance(lambda f: ["scdl.py", "--decouvrir", f], "adherents_scdl.json", 2, 5600)
    json.dump(bilan, open(os.path.join(ICI, "nuit.json"), "w"), ensure_ascii=False, indent=1)
    # les fichiers créés par les nouvelles collectes sont ajoutés à l'index git, pour que le commit de la
    # tâche de nuit les emporte même s'il ne liste que les fichiers historiques
    nouveaux = [f for f in ("syndicats.json", "intramuros.json", "illiwap.json", "collectivite.json", "applis_suivi.json",
                            "adherents_scdl.json", "decouverte_suivi.json", "sites.json", "plan_sites.json", "nuit.json",
                            "signaux_decp.json") if os.path.exists(os.path.join(ICI, f))]
    try:
        subprocess.run(["git", "add", "--"] + nouveaux, cwd=ICI, capture_output=True, timeout=120)
    except Exception:
        pass
    print(json.dumps(bilan, ensure_ascii=False))


if __name__ == "__main__":
    main()
