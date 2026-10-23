"""Modèle prédictif : probabilité qu'une commune ou un EPCI emprunte dans l'année qui suit ses derniers comptes.

Données : comptes OFGL 2019 à 2025 (ofgl_export.py), communes des 20 départements et EPCI de France ;
avis de marchés de travaux publiés au BOAMP par les communes des 20 départements (2019 à aujourd'hui).
Cibles : « Emprunts hors GAD » d'au moins 20 000 € l'année t+1 (horizon 1) et l'année t+2 (horizon 2).
Variables (année t et années précédentes) : historique d'emprunt, effort d'équipement, fonds de roulement,
trésorerie, épargne, dette, remboursements, subventions, taille ; pour les communes, marchés de travaux
lancés l'année t et de janvier à octobre de l'année t+1 (« nowcasting » : un chantier lancé appelle un
financement dans les mois qui suivent).
Validation : apprentissage sur les années passées, test sur la cible 2025 (AUC, part des emprunteurs dans
le premier décile). Puis apprentissage sur toutes les années et score des comptes 2025 et des marchés
2026 -> probabilité d'emprunter en 2026 et en 2027.

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
        "emp_3": "beaucoup emprunté ces 3 dernières années", "lpop": "population au-dessus de la moyenne",
        "eq_rrf": "investissement élevé par rapport aux recettes", "eq_moy": "investissement soutenu sur 3 ans",
        "eq_hausse": "investissement en hausse", "fdr_j": "fonds de roulement élevé", "treso_j": "trésorerie abondante",
        "vfdr": "fonds de roulement en baisse", "cbf": "besoin de financement",
        "teb": "épargne brute élevée", "ten": "épargne nette élevée", "dette_hab": "dette par habitant élevée",
        "desend": "désendettement long", "remb_enc": "dette qui s'amortit vite",
        "subv_eq": "investissement très subventionné", "gap": "investissement non couvert par l'épargne et les subventions",
        "tv": "marchés de travaux lancés l'an dernier", "tv_gros": "gros marchés de travaux (plus de 90 k€) l'an dernier",
        "tv_suiv": "marchés de travaux lancés cette année", "tv_suiv_gros": "gros marchés de travaux (plus de 90 k€) lancés cette année"}
BAS = {"e0": "pas d'emprunt l'année des derniers comptes", "e1": "pas d'emprunt l'année précédente",
       "e2": "pas d'emprunt il y a deux ans", "depuis": "emprunt récent", "emp_3": "peu emprunté ces 3 dernières années",
       "lpop": "petite population", "eq_rrf": "investissement faible", "eq_moy": "investissement faible sur 3 ans",
       "eq_hausse": "investissement en baisse", "fdr_j": "fonds de roulement faible", "treso_j": "trésorerie faible",
       "vfdr": "fonds de roulement reconstitué", "cbf": "capacité de financement", "teb": "épargne brute faible",
       "ten": "épargne nette faible", "dette_hab": "peu de dette", "desend": "désendettement court",
       "remb_enc": "dette qui s'amortit lentement", "subv_eq": "investissement peu subventionné",
       "gap": "investissement couvert par l'épargne et les subventions",
       "tv": "aucun marché de travaux lancé", "tv_gros": "pas de gros marché de travaux",
       "tv_suiv": "aucun marché de travaux lancé cette année", "tv_suiv_gros": "pas de gros marché de travaux cette année"}


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


def travaux(dossier, communes, epcis):
    """Avis de marchés de travaux BOAMP rattachés aux communes : (code INSEE, année) -> comptages."""
    import marches
    idx = marches.index_acheteurs(communes, epcis)
    rows, cache = [], {}
    for f in sorted(glob.glob(os.path.join(dossier, "boamp_travaux_*.csv"))):
        d = pd.read_csv(f, sep=";", dtype=str)
        for _, r in d.iterrows():
            deps = [x for x in str(r.get("code_departement") or "").replace("[", "").replace("]", "").replace("'", "").split(",") if x.strip()]
            cle = (r["nomacheteur"], tuple(deps))
            if cle not in cache:
                cache[cle] = marches.rattacher(r["nomacheteur"], [x.strip() for x in deps], idx)
            siren = cache[cle]
            if siren in communes:
                dt = str(r["dateparution"])[:10]
                rows.append({"code": communes[siren]["code_insee"], "annee": int(dt[:4]), "mois": int(dt[5:7]),
                             "gros": r["famille"] in ("FNS", "JOUE"), "date": dt, "objet": r["objet"]})
    t = pd.DataFrame(rows)
    print("avis de travaux rattachés à une commune :", len(t), "sur", sum(1 for _ in cache), "acheteurs distincts", flush=True)
    return t


def ajoute_travaux(w, t):
    w = w.copy()
    c = t.groupby(["code", "annee"]).agg(tv=("gros", "size"), tv_gros=("gros", "sum")).reset_index()
    y = t[t["mois"] <= 10].groupby(["code", "annee"]).agg(tv_suiv=("gros", "size"), tv_suiv_gros=("gros", "sum")).reset_index()
    y["annee"] -= 1
    w = w.merge(c.assign(type="Commune"), on=["type", "code", "annee"], how="left")
    w = w.merge(y.assign(type="Commune"), on=["type", "code", "annee"], how="left")
    for k in ("tv", "tv_gros", "tv_suiv", "tv_suiv_gros"):
        w[k] = np.log1p(w[k].fillna(0))
    return w


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
    w["cible2"] = g["emprunte"].shift(-2)
    return w


X = ["e0", "e1", "e2", "depuis", "emp_3", "lpop", "eq_rrf", "eq_moy", "eq_hausse", "fdr_j", "treso_j", "vfdr", "cbf",
     "teb", "ten", "dette_hab", "desend", "remb_enc", "subv_eq", "gap"]
TV = ["tv", "tv_gros", "tv_suiv", "tv_suiv_gros"]
COLS = {"Commune": X + TV, "EPCI": X}


def prepare(d, bornes=None, cols=None):
    cols = cols or (list(bornes) if bornes else X)
    m = d[cols].astype(float).replace([np.inf, -np.inf], np.nan)
    if bornes is None:
        bornes = {c: (m[c].quantile(0.01), m[c].quantile(0.99), m[c].median()) for c in cols}
    for c in cols:
        lo, hi, med = bornes[c]
        m[c] = m[c].clip(lo, hi).fillna(med)
    return m, bornes


def apprend(d, cols, cible="cible"):
    m, bornes = prepare(d, cols=cols)
    sc = StandardScaler().fit(m)
    lr = LogisticRegression(C=0.5, max_iter=2000).fit(sc.transform(m), d[cible])
    gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                        min_samples_leaf=60, l2_regularization=1.0).fit(m, d[cible])
    return {"bornes": bornes, "sc": sc, "lr": lr, "gb": gb, "cols": cols}


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
    coef, cols = mod["lr"].coef_[0], mod["cols"]
    out = []
    for row in z:
        contrib = coef * row
        idx = [i for i in np.argsort(-contrib)[:k] if contrib[i] > 0.15]
        out.append(", ".join((HAUT if row[i] > 0 else BAS)[cols[i]] for i in idx))
    return out


def main():
    dossier = sys.argv[1]
    communes, epcis = veille.referentiel()
    insee2siren = {c["code_insee"]: s for s, c in communes.items()}
    t = travaux(dossier, communes, epcis)
    w = ajoute_travaux(variables(charge(dossier)), t)
    an = int(w["annee"].max())
    rapport = {"cible": f"Emprunts hors GAD >= {SEUIL} € l'année t+1 (horizon 1) et t+2 (horizon 2)",
               "variables": COLS, "types": {}}
    probas = {}
    for typ in ("Commune", "EPCI"):
        cols = COLS[typ]
        q = {}
        der = w[(w["type"] == typ) & (w["annee"] == an) & (w["rrf"] > 0)]
        for h, cible in ((1, "cible"), (2, "cible2")):
            base = w[(w["type"] == typ) & (w["rrf"] > 0) & (w["ptot"] > 0)].dropna(subset=[cible, "e1"])
            dern = int(base["annee"].max())
            app, test = base[base["annee"] < dern], base[base["annee"] == dern]
            mod = apprend(app, cols, cible)
            p, p_lr, p_gb = predit(mod, test)[:3]
            q[f"horizon_{h}"] = {
                "apprentissage": f"cibles {int(app['annee'].min()) + h}-{int(app['annee'].max()) + h}, {len(app)} lignes",
                "test": f"cible {dern + h}, {len(test)} lignes", "ensemble": qualite(test[cible], p),
                "logistique": qualite(test[cible], p_lr), "gradient_boosting": qualite(test[cible], p_gb)}
            mod = apprend(base, cols, cible)
            p, _, _, z = predit(mod, der)
            q[f"horizon_{h}"]["coefficients_logistique"] = {cols[i]: round(float(c), 3)
                                                           for i, c in enumerate(mod["lr"].coef_[0])}
            probas[(typ, h)] = (der, p, facteurs(mod, z))
        q["ensemble"] = q["horizon_1"]["ensemble"]
        rapport["types"][typ] = q
    # derniers marchés de travaux de l'année en cours (pour la liste « vont emprunter »)
    t_cour = t[t["annee"] == an + 1].sort_values("date") if len(t) else t
    dernier = {r["code"]: r for _, r in t_cour.iterrows()}
    nb_cour = t_cour.groupby("code").size().to_dict() if len(t_cour) else {}
    sortie = []
    for typ in ("Commune", "EPCI"):
        der, p1, f1 = probas[(typ, 1)]
        _, p2, _ = probas[(typ, 2)]
        for (_, r), a, b, f in zip(der.iterrows(), p1, p2, f1):
            siren = insee2siren.get(r["code"]) if typ == "Commune" else r["code"]
            if not siren or (typ == "EPCI" and siren not in epcis):
                continue
            ent = (communes if typ == "Commune" else epcis)[siren]
            dm = dernier.get(r["code"]) if typ == "Commune" else None
            sortie.append({"siren": siren, "code_insee": ent.get("code_insee", ""), "nom": ent["nom"], "type": typ,
                           "dept": ent["dept"], "population": ent.get("population") or int(r["ptot"]),
                           "annee_comptes": an, "annee_prevue": an + 1, "proba": round(float(a), 3),
                           "proba_annee_suivante": round(float(b), 3),
                           "emprunte_derniere_annee": int(r["e0"]), "emprunts_derniere_annee": round(float(r["emp"])),
                           "depense_equipement": round(float(r["eq"])), "fonds_roulement": round(float(r["fdr"])),
                           "tresorerie": round(float(r["treso"])), "epargne_nette": round(float(r["en"])),
                           "tresorerie_jours": round(float(r["treso"]) / float(r["dep"]) * 365) if r["dep"] > 0 else "",
                           "marches_travaux_annee": int(nb_cour.get(r["code"], 0)) if typ == "Commune" else "",
                           "dernier_marche_date": dm["date"] if dm is not None else "",
                           "dernier_marche_objet": str(dm["objet"])[:160].replace(";", ",") if dm is not None else "",
                           "facteurs": f})
    s = pd.DataFrame(sortie)
    s["rang_departement"] = s.groupby(["dept", "type"])["proba"].rank(ascending=False, method="min").astype(int)
    s.sort_values("proba", ascending=False).to_csv(os.path.join(ICI, "scores.csv"), sep=";", index=False)
    json.dump(rapport, open(os.path.join(ICI, "modele.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: {h: v[h]["ensemble"] for h in ("horizon_1", "horizon_2")} for k, v in rapport["types"].items()},
                     indent=1))
    print(s.sort_values("proba", ascending=False).head(10).to_string())


if __name__ == "__main__":
    main()
