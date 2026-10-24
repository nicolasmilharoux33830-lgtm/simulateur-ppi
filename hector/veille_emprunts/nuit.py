"""Tâche de nuit d'Hector (hors routine du matin, qui doit rester sous 50 minutes) : collectes lourdes,
fichiers déposés dans le dépôt pour que la routine les télécharge.

  python3 nuit.py [--tout]

Chaque nuit : marchés attribués (DECP) -> signaux_decp.json.
Le dimanche (ou --tout) : subventions (Fonds vert) -> subventions.json ; registre des prêts, lignes de
trésorerie et adhésions à l'Agence France Locale -> registre.json ; entités PanneauPocket ->
panneaupocket.json ; plan des sites des mairies -> plan_sites.json.
Le premier dimanche du mois (ou --tout) : recherche des sites absents de l'annuaire -> sites.json.
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


def decouverte():
    """Sites des communes absentes de l'annuaire : travail sur une copie, gardée si elle n'a rien perdu."""
    src, tmp = os.path.join(ICI, "sites.json"), os.path.join(ICI, "sites.travail.json")
    shutil.copy(src, tmp)
    try:
        subprocess.run([PY, "mairies.py", "--decouvrir", tmp], cwd=ICI, timeout=7200, capture_output=True)
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
    dimanche = jour.weekday() == 6
    bilan = {"jour": jour.isoformat()}
    bilan["decp"] = lance(lambda f: ["decp.py", f, "365"], "signaux_decp.json", 50_000, 1800)
    if dimanche or tout:
        bilan["subventions"] = lance(lambda f: ["subventions.py", f], "subventions.json", 20_000, 1200)
        bilan["registre"] = lance(lambda f: ["registre.py", f, "14"], "registre.json", 50_000, 7200)
        bilan["panneaupocket"] = lance(lambda f: ["panneaupocket.py", "--liste", f], "panneaupocket.json",
                                       50_000, 1800)
        if jour.day <= 7 or tout:
            bilan["sites"] = decouverte()
        bilan["plan"] = lance(lambda f: ["mairies.py", "--plan", "sites.json", f], "plan_sites.json", 500_000, 7200)
        for f in os.listdir(ICI):
            if f.endswith(".part"):
                os.remove(os.path.join(ICI, f))
    json.dump(bilan, open(os.path.join(ICI, "nuit.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(bilan, ensure_ascii=False))


if __name__ == "__main__":
    main()
