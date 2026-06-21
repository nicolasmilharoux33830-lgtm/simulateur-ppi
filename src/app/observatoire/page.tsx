"use client";
import { useState } from "react";
import { Search, Building2, MapPin, AlertTriangle, RefreshCw } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";

type Statut = "active" | "recherche_local" | "en_difficulte" | "projet" | "a_reprendre";

interface Entreprise {
  id: number;
  nom: string;
  secteur: string;
  commune: string;
  effectif: string;
  statut: Statut;
  adresse?: string;
  siret?: string;
}

const SECTEURS = ["Tous", "Aéronautique", "Agro-alimentaire", "Logistique", "Tourisme", "Commerce", "Artisanat", "Services", "Industrie"];
const COMMUNES = ["Toutes", "Aire-sur-l'Adour", "Grenade-sur-l'Adour", "Eugénie-les-Bains", "Barcelonne-du-Gers", "Saint-Sever"];

const STATUTS: Record<Statut, { label: string; color: string; bg: string; icon?: string }> = {
  active: { label: "Active", color: "text-green-700", bg: "bg-green-50", icon: "✓" },
  recherche_local: { label: "Cherche local", color: "text-blue-700", bg: "bg-blue-50", icon: "🔍" },
  en_difficulte: { label: "En difficulté", color: "text-red-700", bg: "bg-red-50", icon: "⚠️" },
  projet: { label: "En projet", color: "text-amber-700", bg: "bg-amber-50", icon: "💡" },
  a_reprendre: { label: "À reprendre", color: "text-purple-700", bg: "bg-purple-50", icon: "🤝" },
};

const ENTREPRISES: Entreprise[] = [
  { id: 1, nom: "POTEZ AÉRONAUTIQUE", secteur: "Aéronautique", commune: "Aire-sur-l'Adour", effectif: "250-499", statut: "active", adresse: "ZAE de Peyres", siret: "123456789" },
  { id: 2, nom: "LAUAK GROUPE", secteur: "Aéronautique", commune: "Aire-sur-l'Adour", effectif: "100-249", statut: "active" },
  { id: 3, nom: "CAVE DU TURSAN", secteur: "Agro-alimentaire", commune: "Geaune", effectif: "20-49", statut: "active" },
  { id: 4, nom: "QUALISUD", secteur: "Agro-alimentaire", commune: "Aire-sur-l'Adour", effectif: "50-99", statut: "active" },
  { id: 5, nom: "TRANSPORT BONNEFOY", secteur: "Logistique", commune: "Aire-sur-l'Adour", effectif: "10-19", statut: "active" },
  { id: 6, nom: "HOTEL EUGÉNIE LES BAINS", secteur: "Tourisme", commune: "Eugénie-les-Bains", effectif: "50-99", statut: "active" },
  { id: 7, nom: "BOUCHERIE ARTISAN CASTET", secteur: "Commerce", commune: "Grenade-sur-l'Adour", effectif: "1-9", statut: "a_reprendre", adresse: "12 rue du Centre" },
  { id: 8, nom: "MENUISERIE LAFON", secteur: "Artisanat", commune: "Aire-sur-l'Adour", effectif: "10-19", statut: "a_reprendre" },
  { id: 9, nom: "VOLAILLES DU GERS SAS", secteur: "Agro-alimentaire", commune: "Barcelonne-du-Gers", effectif: "20-49", statut: "en_difficulte" },
  { id: 10, nom: "PALMI'ADOUR", secteur: "Agro-alimentaire", commune: "Aire-sur-l'Adour", effectif: "10-19", statut: "en_difficulte" },
  { id: 11, nom: "ÉPICERIE FINE TASTET", secteur: "Commerce", commune: "Aire-sur-l'Adour", effectif: "1-9", statut: "recherche_local" },
  { id: 12, nom: "PROJET DATACENTRE SUDOUEST", secteur: "Services", commune: "Aire-sur-l'Adour", effectif: "0", statut: "projet" },
  { id: 13, nom: "GARAGE LEBLANC", secteur: "Artisanat", commune: "Eugénie-les-Bains", effectif: "1-9", statut: "a_reprendre" },
  { id: 14, nom: "DISTILLERIE ARMAGNAC MURAT", secteur: "Agro-alimentaire", commune: "Barcelonne-du-Gers", effectif: "10-19", statut: "active" },
  { id: 15, nom: "BTP SERVICES SAINT-SEVER", secteur: "Artisanat", commune: "Saint-Sever", effectif: "20-49", statut: "active" },
];

const COLORS_PIE = ["#103A30", "#2E6F63", "#E6A92E", "#6B7280", "#8B5CF6"];

export default function ObservatoirePage() {
  const [search, setSearch] = useState("");
  const [filterSecteur, setFilterSecteur] = useState("Tous");
  const [filterCommune, setFilterCommune] = useState("Toutes");
  const [filterStatut, setFilterStatut] = useState<Statut | "tous">("tous");
  const [onglet, setOnglet] = useState<"annuaire" | "stats" | "reprise" | "fragilites">("annuaire");

  const filtered = ENTREPRISES.filter(e => {
    const matchSearch = e.nom.toLowerCase().includes(search.toLowerCase()) ||
      e.secteur.toLowerCase().includes(search.toLowerCase()) ||
      e.commune.toLowerCase().includes(search.toLowerCase());
    const matchSecteur = filterSecteur === "Tous" || e.secteur === filterSecteur;
    const matchCommune = filterCommune === "Toutes" || e.commune === filterCommune;
    const matchStatut = filterStatut === "tous" || e.statut === filterStatut;
    return matchSearch && matchSecteur && matchCommune && matchStatut;
  });

  const secteurStats = SECTEURS.slice(1).map(s => ({
    name: s, count: ENTREPRISES.filter(e => e.secteur === s).length,
  })).filter(s => s.count > 0);

  const statutStats = Object.entries(STATUTS).map(([id, info]) => ({
    name: info.label, value: ENTREPRISES.filter(e => e.statut === id as Statut).length,
  }));

  const aReprendre = ENTREPRISES.filter(e => e.statut === "a_reprendre");
  const enDifficulte = ENTREPRISES.filter(e => e.statut === "en_difficulte");

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="font-display font-bold text-pine text-3xl mb-1">Observatoire des entreprises</h1>
        <p className="text-ink/50 text-sm font-body">{ENTREPRISES.length} entreprises référencées sur le territoire · Données indicatives (maquette)</p>
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {[
          { id: "annuaire", label: "Annuaire" },
          { id: "stats", label: "Statistiques" },
          { id: "reprise", label: `Transmission-reprise (${aReprendre.length})` },
          { id: "fragilites", label: `Veille fragilités (${enDifficulte.length})` },
        ].map(t => (
          <button
            key={t.id}
            onClick={() => setOnglet(t.id as typeof onglet)}
            className={`px-4 py-2 rounded-xl text-sm font-display font-semibold transition-colors ${onglet === t.id ? "bg-pine text-white" : "bg-card border border-ink/10 text-ink/60 hover:text-pine"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {onglet === "annuaire" && (
        <>
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-4 mb-6">
            <div className="flex flex-wrap gap-3">
              <div className="relative flex-1 min-w-48">
                <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/40" />
                <input
                  type="search"
                  placeholder="Rechercher une entreprise…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 border border-ink/20 rounded-lg text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss"
                />
              </div>
              <select value={filterSecteur} onChange={e => setFilterSecteur(e.target.value)} className="border border-ink/20 rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss bg-white">
                {SECTEURS.map(s => <option key={s}>{s}</option>)}
              </select>
              <select value={filterCommune} onChange={e => setFilterCommune(e.target.value)} className="border border-ink/20 rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss bg-white">
                {COMMUNES.map(c => <option key={c}>{c}</option>)}
              </select>
              <select
                value={filterStatut}
                onChange={e => setFilterStatut(e.target.value as Statut | "tous")}
                className="border border-ink/20 rounded-lg px-3 py-2 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss bg-white"
              >
                <option value="tous">Tous statuts</option>
                {Object.entries(STATUTS).map(([id, s]) => <option key={id} value={id}>{s.label}</option>)}
              </select>
              {(search || filterSecteur !== "Tous" || filterCommune !== "Toutes" || filterStatut !== "tous") && (
                <button onClick={() => { setSearch(""); setFilterSecteur("Tous"); setFilterCommune("Toutes"); setFilterStatut("tous"); }} className="flex items-center gap-1 text-sm text-ink/50 hover:text-pine font-body px-3 py-2 rounded-lg border border-ink/10">
                  <RefreshCw size={13} /> Réinitialiser
                </button>
              )}
            </div>
          </div>

          <p className="text-sm text-ink/40 font-body mb-4">{filtered.length} résultat{filtered.length > 1 ? "s" : ""}</p>

          {filtered.length === 0 ? (
            <div className="text-center py-16 text-ink/30">
              <Building2 size={40} className="mx-auto mb-3 opacity-30" />
              <p className="font-body">Aucune entreprise ne correspond à ces filtres.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map(e => {
                const st = STATUTS[e.statut];
                return (
                  <div key={e.id} className="bg-card rounded-2xl border border-ink/5 shadow-sm p-5 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between gap-2 mb-3">
                      <h3 className="font-display font-bold text-pine text-sm leading-tight">{e.nom}</h3>
                      <span className={`flex-shrink-0 text-xs font-display font-bold px-2 py-0.5 rounded-full ${st.bg} ${st.color}`}>
                        {st.icon} {st.label}
                      </span>
                    </div>
                    <div className="space-y-1 text-xs font-body text-ink/60">
                      <div className="flex items-center gap-1.5"><Building2 size={11} /> {e.secteur}</div>
                      <div className="flex items-center gap-1.5"><MapPin size={11} /> {e.commune}</div>
                      <div className="flex items-center gap-1.5">👥 {e.effectif} salariés</div>
                      {e.siret && <div className="font-mono text-ink/30">SIRET: {e.siret}</div>}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {onglet === "stats" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
            <h2 className="font-display font-bold text-pine mb-4 text-sm">Répartition par filière</h2>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={secteurStats} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e0d5" horizontal={false} />
                <XAxis type="number" tick={{ fontFamily: "IBM Plex Mono", fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontFamily: "IBM Plex Sans", fontSize: 11 }} width={90} />
                <Tooltip />
                <Bar dataKey="count" fill="#103A30" radius={[0, 4, 4, 0]} name="Entreprises" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
            <h2 className="font-display font-bold text-pine mb-4 text-sm">Répartition par statut</h2>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={statutStats.filter(s => s.value > 0)} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, value }) => `${name}: ${value}`}>
                  {statutStats.map((_, i) => <Cell key={i} fill={COLORS_PIE[i % COLORS_PIE.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {onglet === "reprise" && (
        <div className="space-y-4">
          <div className="bg-purple-50 border border-purple-200 rounded-xl p-4 flex items-start gap-3">
            <RefreshCw size={18} className="text-purple-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-purple-800 font-body">
              <strong>Enjeu territorial majeur</strong> — Le vieillissement des chefs d&apos;entreprise en milieu rural génère des risques de fermeture.
              Ces entreprises sont en recherche de repreneurs. Contact : chargé de mission dév. économique.
            </p>
          </div>
          {aReprendre.length === 0 ? (
            <p className="text-ink/40 text-center py-8 font-body">Aucune entreprise signalée « à reprendre »</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {aReprendre.map(e => (
                <div key={e.id} className="bg-card rounded-2xl border-2 border-purple-200 p-5 hover:shadow-md transition-shadow">
                  <span className="text-xs font-display font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full mb-3 inline-block">🤝 À reprendre</span>
                  <h3 className="font-display font-bold text-pine mb-1">{e.nom}</h3>
                  <p className="text-xs text-ink/60 font-body">{e.secteur} · {e.commune}</p>
                  {e.adresse && <p className="text-xs text-ink/40 font-body mt-1">{e.adresse}</p>}
                  <p className="text-xs text-ink/40 mt-2 font-body">{e.effectif} salarié(s)</p>
                  <a href="/#contact" className="mt-4 block text-center text-xs bg-purple-600 text-white py-2 rounded-lg font-display font-semibold hover:bg-purple-700 transition-colors">
                    Contacter le chargé de mission
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {onglet === "fragilites" && (
        <div className="space-y-4">
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle size={18} className="text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800 font-body">
              <strong>Accès restreint — Usage interne uniquement</strong> — Ces signalements permettent d&apos;anticiper les difficultés
              et d&apos;orienter vers les bons interlocuteurs (Tribunal de commerce, Commissaire aux restructurations, CCI, Urssaf…).
              Filières exposées : palmipèdes (influenza aviaire), aéronautique (sous-traitance de rang 2).
            </p>
          </div>
          {enDifficulte.map(e => (
            <div key={e.id} className="bg-card rounded-2xl border-2 border-red-200 p-5 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-display font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-full">⚠️ En difficulté</span>
                </div>
                <h3 className="font-display font-bold text-pine">{e.nom}</h3>
                <p className="text-xs text-ink/60 font-body">{e.secteur} · {e.commune} · {e.effectif} salarié(s)</p>
              </div>
              <button className="flex-shrink-0 text-sm bg-red-50 text-red-700 border border-red-200 px-3 py-2 rounded-lg font-display font-semibold hover:bg-red-100 transition-colors">
                Plan d&apos;action
              </button>
            </div>
          ))}
          {enDifficulte.length === 0 && <p className="text-ink/40 text-center py-8 font-body">Aucun signalement de fragilité</p>}
        </div>
      )}
    </div>
  );
}
