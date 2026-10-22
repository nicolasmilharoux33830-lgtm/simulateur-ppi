"""Modèle prédictif : probabilité qu'une commune ou un EPCI emprunte dans l'année qui suit ses derniers comptes.

Données : comptes OFGL 2019 à 2025 (ofgl_export.py), communes des 20 départements et EPCI de France.
Cible : « Emprunts hors GAD » de l'année t+1 d'au moins 20 000 €.
Variables (année t et années précédentes) : historique d'emprunt, effort d'équipement, fonds de roulement,
trésorerie, épargne, dette, remboursements, subventions, taille.
Validation : apprentissage sur les cibles 2020 à 2024, test sur 2025 (AUC, part des emprunteurs dans le
premier décile). Puis apprentissage sur toutes les années et score des comptes 2025 -> probabilité 2026.

Usage (pandas et scikit-learn requis) : python3 modele.py DOSSIER_OFGL
Écrit scores.csv (lu par veille.py et rapport.py) et modele.json (qualité, coefficients).
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veille  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
SEUIL = 20000
COURT = {"Encours de dette": "enc", "Annuité de la dette": "ann", "Epargne brute": "eb", "Epargne nette": "en",
         "Recettes de fonctionnement": "rrf", "Dépenses d'équipement": "eq", "Emprunts hors GAD": "emp",
         "Dépôts au Trésor": "treso", "Fonds de roulement": "fdr", "Capacité ou besoin de financement": "cbf",
         "Remboursements d'emprunts hors GAD": "remb", "Dépenses totales": "dep",
         "Subventions reçues et participations": "subv", "Variation du fonds de roulement": "vfdr"}
# Libellé d'une variable selon qu'elle est haute ou basse pour la collectivité (pour expliquer un score)
HAUT = {"e0": "a emprunté l'année des derniers comptes", "e1": "a emprunté l'année précédente",
        "e2": "a emprunté il y a deux ans", "depuis": "pas d'emprunt depuis plusieurs années",
        "emp_3": "beaucoup emprunté ces 3 dernières années", "lpop": "taille importante",
        "eq_rrf": "investissement élevé par rapport aux recettes", "eq_moy": "investissement soutenu sur 3 ans",
        "eq_hausse": "investissement en hausse", "fdr_j": "fonds de roulement élevé", "treso_j": "trésorerie abondante",
        "vfdr": "fonds de roulement en baisse", "cbf": "besoin de financement",
        "teb": "épargne brute élevée", "ten": "épargne nette élevée", "dette_hab": "dette par habitant élevée",
        "desend": "désendettement long", "remb_enc": "dette qui s'amortit vite",
        "subv_eq": "investissement très subventionné", "gap": "investissement non couvert par l'épargne et les subventions"}
BAS = {"e0": "pas d'emprunt l'année des derniers comptes", "e1": "pas d'emprunt l'année précédente",
       "e2": "pas d'emprunt il y a deux ans", "depuis": "emprunt récent", "emp_3": "peu emprunté ces 3 dernières années",
       "lpop": "petite taille", "eq_rrf": "investissement faible", "eq_moy": "investissement faible sur 3 ans",
       "eq_hausse": "investissement en baisse", "fdr_j": "fonds de roulement faible", "treso_j": "trésorerie faible",
       "vfdr": "fonds de roulement reconstitué", "cbf": "capacité de financement", "teb": "épargne brute faible",
       "ten": "épargne nette faible", "dette_hab": "peu de dette", "desend": "désendettement court",
       "remb_enc": "dette qui s'amortit lentement", "subv_eq": "investissement peu subventionné",
       "gap": "investissement couvert par l'épargne et les subventions"}


def charge(dossier):
    rows = []
    for f in sorted(glob.glob(os.path.join(dossier, "communes_*.csv"))):
        d = pd.read_csv(f, sep=";", dtype={"com_code": str})
        d = d.rename(columns={"com_code": "code", "com_name": "nom"})
        d["type"] = "Commune"
        rows.append(d)
    e = pd.read_csv(os.path.join(dossier, "epci_france.csv"), sep=";", dtype={"epci_code": str, "dep_code": str})
    e = e.rename(columns={"epci_code": "code", "epci_name": "nom"}).drop(columns=["dep_code"], errors="ignore")
    e["type"] = "EPCI"
    rows.append(e)
    d = pd.concat(rows, ignore_index=True)
    d["annee"] = d["exer"].astype(str).str[:4].astype(int)
    d["agregat"] = d["agregat"].map(COURT)
    w = d.pivot_table(index=["type", "code", "annee"], columns="agregat", values="montant", aggfunc="sum").reset_index()
    pop = d.groupby(["type", "code", "annee"])["ptot"].max().reset_index()
    noms = d.groupby(["type", "code"])["nom"].last().reset_index()
    w = w.merge(pop, on=["type", "code", "annee"]).merge(noms, on=["type", "code"])
    return w.fillna({c: 0.0 for c in COURT.values()})


def variables(w):
    w = w.sort_values(["type", "code", "annee"]).copy()
    g = w.groupby(["type", "code"])
    w["emprunte"] = (w["emp"] >= SEUIL).astype(int)
    for k in (1, 2):
        w[f"e{k}"] = g["emprunte"].shift(k)
    w["e0"] = w["emprunte"]
    # années depuis le dernier emprunt (5 si aucun dans l'historique disponible)
    dern = w["annee"].where(w["emprunte"] == 1)
    w["dern"] = dern.groupby([w["type"], w["code"]]).ffill()
    w["depuis"] = (w["annee"] - w["dern"]).fillna(5).clip(0, 5)
    w["emp_3"] = (g["emp"].rolling(3, min_periods=1).sum().reset_index(level=[0, 1], drop=True)) / w["rrf"].where(w["rrf"] > 0)
    rrf = w["rrf"].where(w["rrf"] > 0)
    dep = w["dep"].where(w["dep"] > 0)
    pop = w["ptot"].where(w["ptot"] > 0)
    w["lpop"] = np.log(pop)
    w["eq_rrf"] = w["eq"] / rrf
    eq_moy = g["eq"].rolling(3, min_periods=1).mean().reset_index(level=[0, 1], drop=True)
    w["eq_moy"] = eq_moy / rrf
    w["eq_hausse"] = (w["eq"] - g["eq"].shift(1)) / rrf
    w["fdr_j"] = w["fdr"] / dep * 365
    w["treso_j"] = w["treso"] / dep * 365
    w["vfdr"] = -w["vfdr"] / rrf
    w["cbf"] = -w["cbf"] / rrf
    w["teb"] = w["eb"] / rrf
    w["ten"] = w["en"] / rrf
    w["dette_hab"] = w["enc"] / pop
    w["desend"] = (w["enc"] / w["eb"].where(w["eb"] > 0)).fillna(30).clip(0, 30)
    w["remb_enc"] = (w["remb"] / w["enc"].where(w["enc"] > 0)).fillna(0)
    w["subv_eq"] = (w["subv"] / w["eq"].where(w["eq"] > 0)).fillna(0).clip(0, 3)
    w["gap"] = (w["eq"] - w["en"] - w["subv"]) / rrf
    w["cible"] = g["emprunte"].shift(-1)
    return w


X = ["e0", "e1", "e2", "depuis", "emp_3", "lpop", "eq_rrf", "eq_moy", "eq_hausse", "fdr_j", "treso_j", "vfdr", "cbf",
     "teb", "ten", "dette_hab", "desend", "remb_enc", "subv_eq", "gap"]


def prepare(d, bornes=None):
    m = d[X].astype(float).replace([np.inf, -np.inf], np.nan)
    if bornes is None:
        bornes = {c: (m[c].quantile(0.01), m[c].quantile(0.99), m[c].median()) for c in X}
    for c in X:
        lo, hi, med = bornes[c]
        m[c] = m[c].clip(lo, hi).fillna(med)
    return m, bornes


def apprend(d):
    m, bornes = prepare(d)
    sc = StandardScaler().fit(m)
    lr = LogisticRegression(C=0.5, max_iter=2000).fit(sc.transform(m), d["cible"])
    gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                        min_samples_leaf=60, l2_regularization=1.0).fit(m, d["cible"])
    return {"bornes": bornes, "sc": sc, "lr": lr, "gb": gb}


def predit(mod, d):
    m, _ = prepare(d, mod["bornes"])
    z = mod["sc"].transform(m)
    p_lr = mod["lr"].predict_proba(z)[:, 1]
    p_gb = mod["gb"].predict_proba(m)[:, 1]
    return (p_lr + p_gb) / 2, p_lr, p_gb, z


def qualite(y, p):
    o = np.argsort(-p)
    top = o[: max(1, len(o) // 10)]
    return {"auc": round(float(roc_auc_score(y, p)), 3), "taux_moyen": round(float(np.mean(y)), 3),
            "taux_premier_decile": round(float(np.mean(np.asarray(y)[top])), 3)}


def facteurs(mod, z, k=3):
    coef = mod["lr"].coef_[0]
    out = []
    for row in z:
        contrib = coef * row
        idx = [i for i in np.argsort(-contrib)[:k] if contrib[i] > 0.15]
        out.append(" ; ".join((HAUT if row[i] > 0 else BAS)[X[i]] for i in idx))
    return out


def main():
    dossier = sys.argv[1]
    w = variables(charge(dossier))
    base = w.dropna(subset=["cible", "e1"])
    base = base[(base["rrf"] > 0) & (base["ptot"] > 0)]
    rapport = {"cible": f"Emprunts hors GAD >= {SEUIL} € l'année suivante", "variables": X, "types": {}}
    sortie = []
    communes, epcis = veille.referentiel()
    insee2siren = {c["code_insee"]: s for s, c in communes.items()}
    for typ in ("Commune", "EPCI"):
        b = base[base["type"] == typ]
        app, test = b[b["annee"] <= 2023], b[b["annee"] == 2024]
        mod = apprend(app)
        p, p_lr, p_gb = predit(mod, test)[:3]
        q = {"apprentissage": f"cibles {int(app['annee'].min()) + 1}-{int(app['annee'].max()) + 1}, {len(app)} lignes",
             "test": f"cible {int(test['annee'].max()) + 1}, {len(test)} lignes",
             "ensemble": qualite(test["cible"], p), "logistique": qualite(test["cible"], p_lr),
             "gradient_boosting": qualite(test["cible"], p_gb)}
        mod = apprend(b)
        der = w[(w["type"] == typ) & (w["annee"] == w["annee"].max()) & (w["rrf"] > 0)]
        p, _, _, z = predit(mod, der)
        q["coefficients_logistique"] = {X[i]: round(float(c), 3) for i, c in enumerate(mod["lr"].coef_[0])}
        rapport["types"][typ] = q
        fac = facteurs(mod, z)
        an = int(der["annee"].max())
        for (_, r), pr, f in zip(der.iterrows(), p, fac):
            siren = insee2siren.get(r["code"]) if typ == "Commune" else r["code"]
            if typ == "EPCI" and siren not in epcis:
                continue
            if not siren:
                continue
            ent = (communes if typ == "Commune" else epcis)[siren]
            sortie.append({"siren": siren, "code_insee": ent.get("code_insee", ""), "nom": ent["nom"], "type": typ, "dept": ent["dept"],
                           "population": ent.get("population") or int(r["ptot"]), "annee_comptes": an, "annee_prevue": an + 1,
                           "proba": round(float(pr), 3), "emprunte_derniere_annee": int(r["e0"]),
                           "emprunts_derniere_annee": round(float(r["emp"])),
                           "depense_equipement": round(float(r["eq"])), "fonds_roulement": round(float(r["fdr"])),
                           "facteurs": f})
    s = pd.DataFrame(sortie)
    s["rang_departement"] = s.groupby(["dept", "type"])["proba"].rank(ascending=False, method="min").astype(int)
    s.sort_values("proba", ascending=False).to_csv(os.path.join(ICI, "scores.csv"), sep=";", index=False)
    json.dump(rapport, open(os.path.join(ICI, "modele.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(rapport, ensure_ascii=False, indent=1))
    print(s.sort_values("proba", ascending=False).head(15).to_string())


if __name__ == "__main__":
    main()
