// Relais serveur vers l'API publique OFGL (comptes des communes), via fonction Vercel.
// Appelee en meme origine depuis /communes.html : supprime tout probleme de CORS cote navigateur.
const BASE =
  "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-communes";

module.exports = async (req, res) => {
  try {
    const q = req.query || {};
    let target;
    if (q.mode === "search") {
      const term = String(q.q || "").replace(/"/g, "").trim();
      if (!term) { res.status(400).json({ error: "parametre q requis" }); return; }
      const where = encodeURIComponent('search(com_name,"' + term + '")');
      target = BASE + "/records?where=" + where +
        "&select=siren,com_name,dep_name,ptot&limit=100";
    } else {
      const siren = String(q.siren || "").replace(/\D/g, "");
      if (siren.length !== 9) { res.status(400).json({ error: "siren invalide" }); return; }
      const sel = encodeURIComponent(
        "exer,agregat,montant,type_de_budget,lbudg,ptot,com_name,dep_name,dep_code,epci_name"
      );
      target = BASE + "/exports/json?where=siren%3D%22" + siren + "%22&select=" + sel;
    }
    const r = await fetch(target);
    const body = await r.text();
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.setHeader("cache-control", "public, max-age=3600");
    res.status(r.status).send(body);
  } catch (e) {
    res.status(502).json({ error: "OFGL injoignable" });
  }
};
