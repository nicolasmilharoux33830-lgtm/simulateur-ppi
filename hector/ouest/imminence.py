"""Imminence : qui va délibérer sur un emprunt dans les toutes prochaines semaines.

1. Échéances de lignes de trésorerie : une ligne se renouvelle le plus souvent chaque année à la même date
   (historique Mégalis et GIP RECIA : 45 % des lignes renouvelées l'année suivante, médiane à 1 jour de
   l'anniversaire, moitié des cas à moins de 2 semaines). La date de l'acte de l'an dernier donne la
   date attendue du prochain.
2. Modèle mensuel (risque discret, régression logistique) appris sur les délibérations d'emprunt réelles
   de Bretagne (Mégalis, 2022-2026) : chaque mois, probabilité qu'une collectivité délibère sur un emprunt,
   selon ses comptes de l'année précédente (OFGL), ses marchés de travaux récents (BOAMP) et le mois
   (saisonnalité). Validation hors échantillon sur 2026. Le score s'applique aux 20 départements :
   il n'utilise que des données disponibles partout.

  python3 imminence.py --historique FICHIER        télécharge les actes « 7.3 Emprunts » (Mégalis, RECIA)
  python3 imminence.py --apprend DOSSIER_OFGL      apprend le modèle (pandas, scikit-learn) -> imminence.json
  (dans veille.py / rapport.py) echeances(...), proba_mois(...)
"""
import json
import math
import os
import re
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import jget  # noqa: E402
from perimetre import norm  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
GARANTIE = re.compile(r"garanti")
LIGNE = re.compile(r"ligne d[eu]s? tresorerie|ligne de credit|credit de tresorerie|ouverture de credit")
# Taux observés sur l'historique breton (Mégalis 2021-2026), recalculés par --taux
TAUX = {"ligne": 0.41, "emprunt": 0.22, "travaux_90j": 0.29, "base_90j": 0.11}
ANNUELLES = ["e0", "e1", "depuis", "emp_3", "lpop", "eq_rrf", "eq_moy", "eq_hausse", "fdr_j", "treso_j", "vfdr",
             "cbf", "teb", "ten", "dette_hab", "desend", "remb_enc", "gap"]
TRAVAUX = ["tv_1", "tv_2_3", "tv_4_6"]


# ---------- historique des actes « 7.3 Emprunts » ----------
def actes_emprunt(api, debut, fin):
    out, tok = [], None
    while True:
        p = {"lignes": 100, "classifications": "7.3", "date_de_publication_debut": debut, "date_de_publication_fin": fin}
        if tok:
            p["page_suivante"] = tok
        r = jget(api, p, tries=15, timeout=90)
        res = r.get("resultats", [])
        out += res
        tok = r.get("page_suivante")
        if not res or not tok or len(out) >= r.get("nb_resultats", 0) or len(out) > 20000:
            return out


def historique(plateformes, debut, fin):
    """Actes 7.3 publiés entre debut et fin (dates ISO), par semestres pour rester sous les limites de l'API."""
    a, b = date.fromisoformat(debut[:10]), date.fromisoformat(fin[:10])
    out, vus = [], set()
    for nom, api in plateformes.items():
        cur = a
        while cur <= b:
            nxt = min(b, cur + timedelta(days=180))
            for x in actes_emprunt(api, f"{cur}T00:00:00Z", f"{nxt}T23:59:59Z"):
                k = x.get("id") or x.get("url")
                if k in vus:
                    continue
                vus.add(k)
                out.append({"plateforme": nom, "siren": x.get("siren"), "date_acte": (x.get("date_acte") or "")[:10],
                            "date_publication": (x.get("date_publication") or "")[:10], "objet": x.get("objet"),
                            "url": x.get("url")})
            cur = nxt + timedelta(days=1)
    return out


AUTRE = re.compile(r"rembours|\brbt\b|transfert|reamenag|renegoci|avenant|cloture|solde|annul")


def type_acte(objet):
    o = norm(objet)
    if GARANTIE.search(o):
        return "garantie"
    if AUTRE.search(o):
        return "autre"
    if LIGNE.search(o):
        return "ligne"
    return "emprunt"


# ---------- 1. échéances de lignes de trésorerie ----------
def echeances(actes, jour, communes, epcis, entite, genre="ligne", avant=10, apres=45):
    """Lignes de trésorerie (genre « ligne ») ou emprunts (genre « emprunt ») dont l'anniversaire tombe
    entre jour-avant et jour+apres, sans nouvel acte publié depuis : le prochain est attendu maintenant."""
    par = {}
    for a in actes:
        if type_acte(a["objet"]) != genre or (a["siren"] not in communes and a["siren"] not in epcis):
            continue
        try:
            d = date.fromisoformat(a["date_acte"])
        except ValueError:
            continue
        par.setdefault(a["siren"], []).append((d, a))
    out = []
    for siren, lst in par.items():
        lst.sort(key=lambda x: x[0])
        d, a = lst[-1]
        attendu = d + timedelta(days=365)
        if not (jour - timedelta(days=avant) <= attendu <= jour + timedelta(days=apres)):
            continue
        ent = entite(siren, communes, epcis)
        if not ent.get("eligible"):
            continue
        anciens = [x for x, _ in lst[:-1] if 300 <= (d - x).days <= 430]
        out.append({"siren": siren, "entite": ent, "genre": genre, "dernier_acte": d.isoformat(), "attendu": attendu.isoformat(),
                    "objet": a["objet"], "lien": a["url"], "plateforme": a["plateforme"],
                    "deja_renouvele_avant": bool(anciens)})
    out.sort(key=lambda x: x["attendu"])
    return out


# ---------- 2. modèle mensuel ----------
def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def proba_mois(modele, annuelles, travaux_dates, mois_cible):
    """Probabilité d'une délibération d'emprunt dans le mois mois_cible (date du 1er du mois).
    annuelles : dict des variables ANNUELLES (comptes de l'année précédente) ; travaux_dates : dates ISO des
    avis de marchés de travaux récents de la collectivité."""
    x = {}
    for k in ANNUELLES:
        v = annuelles.get(k)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = None
        lo, hi, med = modele["bornes"][k]
        x[k] = med if v is None or v != v else min(max(v, lo), hi)
    ages = []
    for t in travaux_dates or []:
        try:
            ages.append((mois_cible - date.fromisoformat(t[:10])).days)
        except ValueError:
            pass
    x["tv_1"] = math.log1p(sum(1 for a in ages if 0 <= a <= 31))
    x["tv_2_3"] = math.log1p(sum(1 for a in ages if 31 < a <= 92))
    x["tv_4_6"] = math.log1p(sum(1 for a in ages if 92 < a <= 183))
    z = modele["intercept"] + modele["mois"][str(mois_cible.month)]
    for k, c in modele["coef"].items():
        z += c * (x[k] - modele["moyenne"][k]) / (modele["ecart"][k] or 1)
    return 1 / (1 + math.exp(-z))


def proba_periode(modele, annuelles, travaux_dates, jour, mois=2):
    """Probabilité d'au moins une délibération d'emprunt dans les `mois` prochains mois calendaires."""
    reste, m = 1.0, date(jour.year, jour.month, 1)
    for _ in range(mois):
        m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)
        reste *= 1 - proba_mois(modele, annuelles, travaux_dates, m)
    return 1 - reste


def apprend(dossier):
    import glob

    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.preprocessing import StandardScaler

    import marches
    import modele
    import veille
    communes, epcis = veille.referentiel()
    bretagne = {"22", "29", "35", "56"}
    w = modele.variables(modele.charge(dossier))
    insee2siren = {c["code_insee"]: s for s, c in communes.items()}
    w["siren"] = np.where(w["type"] == "Commune", w["code"].map(insee2siren), w["code"])
    # unités : communes et EPCI de Bretagne (Mégalis y couvre 766 communes sur 1 202)
    unites = {s for s, c in communes.items() if c["dept"] in bretagne} | {s for s, x in epcis.items() if x["dept"] in bretagne}
    # événements : délibérations d'emprunt (hors garanties et lignes de trésorerie)
    actes = json.load(open(os.path.join(dossier, "actes_73.json")))
    ev = set()
    for a in actes:
        if a["siren"] in unites and type_acte(a["objet"]) == "emprunt" and a["date_acte"][:4].isdigit():
            ev.add((a["siren"], int(a["date_acte"][:4]), int(a["date_acte"][5:7])))
    # marchés de travaux BOAMP par collectivité et par mois
    idx = marches.index_acheteurs(communes, epcis)
    tv = {}
    for f in sorted(glob.glob(os.path.join(dossier, "boamp_travaux_*.csv"))):
        d = pd.read_csv(f, sep=";", dtype=str)
        cache = {}
        for _, r in d.iterrows():
            deps = [x.strip() for x in str(r.get("code_departement") or "").strip("[]").replace("'", "").split(",") if x.strip()]
            cle = (r["nomacheteur"], tuple(deps))
            if cle not in cache:
                cache[cle] = marches.rattacher(r["nomacheteur"], deps, idx)
            s = cache[cle]
            if s in unites:
                tv.setdefault(s, []).append(date.fromisoformat(str(r["dateparution"])[:10]))
    lignes = []
    annuel = {(r["siren"], int(r["annee"])): r for _, r in w[w["siren"].isin(unites)].iterrows()}
    for s in unites:
        dates_tv = sorted(tv.get(s, []))
        for an in range(2022, 2027):
            a_prec = annuel.get((s, an - 1))
            if a_prec is None:
                continue
            for m in range(1, 13):
                if (an, m) > (2026, 9):
                    break
                debut = date(an, m, 1)
                ages = [(debut - t).days for t in dates_tv if t < debut]
                row = {"siren": s, "annee": an, "mois": m, "cible": int((s, an, m) in ev),
                       "tv_1": math.log1p(sum(1 for a in ages if 0 <= a <= 31)),
                       "tv_2_3": math.log1p(sum(1 for a in ages if 31 < a <= 92)),
                       "tv_4_6": math.log1p(sum(1 for a in ages if 92 < a <= 183))}
                for k in ANNUELLES:
                    row[k] = a_prec.get(k)
                lignes.append(row)
    p = pd.DataFrame(lignes)
    cols = ANNUELLES + TRAVAUX
    m = p[cols].astype(float).replace([np.inf, -np.inf], np.nan)
    app = p["annee"] <= 2025
    bornes = {c: (float(m.loc[app, c].quantile(0.01)), float(m.loc[app, c].quantile(0.99)), float(m.loc[app, c].median()))
              for c in cols}
    for c in cols:
        lo, hi, med = bornes[c]
        m[c] = m[c].clip(lo, hi).fillna(med)
    mois = pd.get_dummies(p["mois"].astype(int), prefix="m").astype(float)
    sc = StandardScaler().fit(m[app])
    X = np.hstack([sc.transform(m), mois.values])
    lr = LogisticRegression(C=0.5, max_iter=3000).fit(X[app], p.loc[app, "cible"])
    pr = lr.predict_proba(X[~app])[:, 1]
    y = p.loc[~app, "cible"].values
    o = np.argsort(-pr)
    top = o[: max(1, len(o) // 10)]
    qualite = {"lignes_apprentissage": int(app.sum()), "lignes_test_2026": int((~app).sum()),
               "taux_mensuel_moyen": round(float(y.mean()), 4), "auc_2026": round(float(roc_auc_score(y, pr)), 3),
               "taux_premier_decile_2026": round(float(y[top].mean()), 4)}
    # apprentissage final sur toutes les années
    sc = StandardScaler().fit(m)
    X = np.hstack([sc.transform(m), mois.values])
    lr = LogisticRegression(C=0.5, max_iter=3000).fit(X, p["cible"])
    k = len(cols)
    out = {"variables": cols, "bornes": {c: list(bornes[c]) for c in cols},
           "moyenne": {c: float(v) for c, v in zip(cols, sc.mean_)}, "ecart": {c: float(v) for c, v in zip(cols, sc.scale_)},
           "coef": {c: float(v) for c, v in zip(cols, lr.coef_[0][:k])},
           "mois": {str(int(c.split("_")[1])): float(v) for c, v in zip(mois.columns, lr.coef_[0][k:])},
           "intercept": float(lr.intercept_[0]), "qualite": qualite,
           "evenements": f"{len(ev)} délibérations d'emprunt (Mégalis, Bretagne, 2022-2026) sur {len(unites)} collectivités"}
    json.dump(out, open(os.path.join(ICI, "imminence.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("qualite", "evenements")}, ensure_ascii=False, indent=1))
    print("mois :", {k: round(v, 2) for k, v in out["mois"].items()})
    print("coef :", {k: round(v, 2) for k, v in out["coef"].items()})


if __name__ == "__main__":
    if sys.argv[1] == "--historique":
        import veille
        r = historique(veille.PLATEFORMES, "2021-01-01", date.today().isoformat())
        json.dump(r, open(sys.argv[2], "w"), ensure_ascii=False)
        print(len(r))
    elif sys.argv[1] == "--apprend":
        apprend(sys.argv[2])
