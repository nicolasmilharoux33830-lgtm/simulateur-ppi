"""Syndicats (SIVU, SIVOM, syndicats mixtes fermés et ouverts) dont le siège est dans les départements du
périmètre, à partir du répertoire SIRENE (API Recherche d'entreprises, ouverte et sans clé).

  python3 syndicats.py SORTIE.json      construit la liste (tâche de nuit)

Les autres scripts appellent ajoute(epcis) : les syndicats rejoignent le dictionnaire des groupements,
avec le type « Syndicat » et sans population (aucun seuil de population ne s'applique à eux).
"""
import json
import os
import re
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from net import jget  # noqa: E402
from perimetre import DEPT2REG, norm  # noqa: E402

API = "https://recherche-entreprises.api.gouv.fr/search"
FICHIER = os.path.join(ICI, "syndicats.json")
# catégories juridiques INSEE : 7345 SIVOM, 7353 SIVU, 7354 syndicat mixte fermé, 7355 syndicat mixte ouvert
NATURES = {"7345": "SIVOM", "7353": "SIVU", "7354": "Syndicat mixte fermé", "7355": "Syndicat mixte ouvert"}
# garde-fou si une catégorie ne renvoyait pas des syndicats : le nom doit alors le dire
NOM_SYNDICAT = re.compile(r"\b(syndicat|syndic|sivom|sivu|sivos|siaep|siep|sia|siae|siea|sictom|smictom|smirgeomes|"
                          r"sirp|sie|sde|sdeg|syded|sydec|sm|smo|smf|pole|petr|regie)\b")


def nom_de(r):
    nom = r.get("nom_raison_sociale") or r.get("nom_complet") or ""
    sigle = (r.get("sigle") or "").strip()
    return nom.strip(), sigle


def construire(pause=0.2, limite_s=1500):
    """{siren: fiche} de tous les syndicats actifs du périmètre (siège dans un des départements)."""
    out, t0, erreurs = {}, time.time(), 0
    for dept in sorted(DEPT2REG):
        for code, libelle in NATURES.items():
            page = 1
            while time.time() - t0 < limite_s:
                try:
                    d = jget(API, {"nature_juridique": code, "departement": dept, "etat_administratif": "A",
                                   "per_page": 25, "page": page}, tries=8, timeout=40)
                except Exception:
                    erreurs += 1
                    break
                for r in d.get("results") or []:
                    siren = r.get("siren")
                    nat = str(r.get("nature_juridique") or code)
                    nom, sigle = nom_de(r)
                    if not siren or not nom or nat not in NATURES:
                        continue
                    if nat in ("7345", "7353") and not NOM_SYNDICAT.search(norm(f"{nom} {sigle}")):
                        continue
                    siege = r.get("siege") or {}
                    dep = siege.get("departement") or dept
                    out[siren] = {"type": "Syndicat", "nom": nom, "sigle": sigle or None,
                                  "nature": NATURES[nat], "population": None,
                                  "dept": dep if dep in DEPT2REG else dept,
                                  "commune_siege": siege.get("libelle_commune")}
                if page >= int(d.get("total_pages") or 1) or not d.get("results"):
                    break
                page += 1
                time.sleep(pause)
            time.sleep(pause)
    return out, erreurs


_CACHE = None


def charge(construire_si_vide=True):
    """Syndicats du périmètre : fichier du dépôt, sinon construction à la volée (gardée pour la session)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        _CACHE = json.load(open(FICHIER, encoding="utf-8"))
    except (OSError, ValueError):
        _CACHE = {}
    if not _CACHE and construire_si_vide:   # fichier absent ou encore vide : construction à la volée
        try:
            _CACHE, _ = construire(limite_s=420)
            if _CACHE:
                json.dump(_CACHE, open(FICHIER, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            _CACHE = {}
    return _CACHE


def ajoute(epcis):
    """Ajoute les syndicats au dictionnaire des groupements (un EPCI déjà présent n'est jamais remplacé)."""
    for s, e in charge().items():
        epcis.setdefault(s, dict(e))
    return epcis


def main():
    sortie = sys.argv[1] if len(sys.argv) > 1 else FICHIER
    out, erreurs = construire()
    json.dump(out, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    par = {}
    for e in out.values():
        par[e["nature"]] = par.get(e["nature"], 0) + 1
    print(f"{len(out)} syndicats ({', '.join(f'{k} : {v}' for k, v in sorted(par.items()))}) ; "
          f"{erreurs} requêtes en échec")


if __name__ == "__main__":
    main()
