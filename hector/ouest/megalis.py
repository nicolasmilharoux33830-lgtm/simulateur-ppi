import sys, json
sys.path.insert(0, '.')
from net import jget
API = "https://data-publication.megalis.bretagne.bzh/mq_apis/actes/v1/search"

def search(**params):
    out, token = [], None
    params.setdefault("lignes", 100)
    while True:
        p = dict(params)
        if token:
            p["page_suivante"] = token
        d = jget(API, p, tries=8, timeout=40)
        res = d.get("resultats", [])
        out += res
        token = d.get("page_suivante")
        if not res or not token or len(out) >= d.get("nb_resultats", 0) or len(out) > 3000:
            return out, d.get("nb_resultats")
