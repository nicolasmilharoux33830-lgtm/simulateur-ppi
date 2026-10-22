"""Télécharge les comptes OFGL (2019 à l'année la plus récente) des communes des 20 départements
et de tous les EPCI à fiscalité propre, pour le modèle prédictif.

Usage : python3 ofgl_export.py DOSSIER
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import get  # noqa: E402
from perimetre import DEPT2REG  # noqa: E402

BASE = "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets"
AGREGATS = ["Encours de dette", "Annuité de la dette", "Epargne brute", "Epargne nette",
            "Recettes de fonctionnement", "Dépenses d'équipement", "Emprunts hors GAD", "Dépôts au Trésor",
            "Fonds de roulement", "Capacité ou besoin de financement", "Remboursements d'emprunts hors GAD",
            "Dépenses totales", "Subventions reçues et participations", "Variation du fonds de roulement"]
LISTE = ",".join(f'"{a}"' for a in AGREGATS)


def export(ds, where, select, chemin):
    if os.path.exists(chemin) and os.path.getsize(chemin) > 1000:
        return
    b = get(f"{BASE}/{ds}/exports/csv", {"where": where, "select": select, "delimiter": ";"}, tries=20, timeout=180)
    open(chemin, "wb").write(b)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for d in sorted(DEPT2REG):
        export("ofgl-base-communes-consolidee", f'dep_code="{d}" and year(exer)>=2019 and agregat in ({LISTE})',
               "com_code,com_name,exer,agregat,montant,ptot", os.path.join(out, f"communes_{d}.csv"))
        print("communes", d, "ok", flush=True)
    export("ofgl-base-gfp-consolidee", f"year(exer)>=2019 and agregat in ({LISTE})",
           "epci_code,epci_name,dep_code,exer,agregat,montant,ptot", os.path.join(out, "epci_france.csv"))
    print("epci ok", flush=True)


if __name__ == "__main__":
    main()
