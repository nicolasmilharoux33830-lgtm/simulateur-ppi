"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, Search, ChevronRight, LogOut, User, Calendar, MapPin, Euro, Briefcase } from "lucide-react";

type Statut = "contact" | "qualification" | "proposition" | "decision" | "installe" | "abandonne";

interface Dossier {
  id: number;
  porteur: string;
  entreprise: string;
  secteur: string;
  besoin: string;
  surface: number;
  emplois: number;
  budget: number;
  echeance: string;
  statut: Statut;
  commune_cible?: string;
  notes: string;
  updated_at: string;
}

const STATUTS: { id: Statut; label: string; color: string; bg: string }[] = [
  { id: "contact", label: "Contact", color: "text-gray-600", bg: "bg-gray-100" },
  { id: "qualification", label: "Qualification", color: "text-blue-700", bg: "bg-blue-50" },
  { id: "proposition", label: "Proposition", color: "text-amber-700", bg: "bg-amber-50" },
  { id: "decision", label: "Décision", color: "text-purple-700", bg: "bg-purple-50" },
  { id: "installe", label: "Installé ✓", color: "text-green-700", bg: "bg-green-50" },
  { id: "abandonne", label: "Abandonné", color: "text-red-700", bg: "bg-red-50" },
];

const MOCK_DOSSIERS: Dossier[] = [
  { id: 1, porteur: "M. Dupont Jean", entreprise: "DUPONT Logistique SAS", secteur: "Logistique / Transport", besoin: "Entrepôt + bureaux", surface: 2000, emplois: 12, budget: 450000, echeance: "2025-09", statut: "qualification", commune_cible: "Aire-sur-l'Adour", notes: "Intéressé par ZAE Peyres. Dossier financement en cours.", updated_at: "2025-06-18" },
  { id: 2, porteur: "Mme Martin Sophie", entreprise: "SALS Bio SARL", secteur: "Agro-alimentaire", besoin: "Atelier de transformation", surface: 600, emplois: 5, budget: 180000, echeance: "2025-11", statut: "proposition", commune_cible: "Grenade-sur-l'Adour", notes: "Proposition ZA Bassia envoyée. Visite prévue 26/06.", updated_at: "2025-06-15" },
  { id: 3, porteur: "M. Bernard Luc", entreprise: "Création - Artisanat Bois", secteur: "Artisanat / BTP", besoin: "Local artisanal", surface: 150, emplois: 2, budget: 50000, echeance: "2025-07", statut: "contact", commune_cible: undefined, notes: "Premier contact téléphonique. Rendez-vous à planifier.", updated_at: "2025-06-20" },
  { id: 4, porteur: "M. Moreau Paul", entreprise: "AERO TECH SUD", secteur: "Aéronautique / Défense", besoin: "Hangar production", surface: 5000, emplois: 45, budget: 2200000, echeance: "2026-03", statut: "decision", commune_cible: "Aire-sur-l'Adour", notes: "Offre foncière ZAE Peyres formalisée. En attente décision CA groupe.", updated_at: "2025-06-10" },
  { id: 5, porteur: "Mme Leclerc Anne", entreprise: "Hotel & Spa Les Pins", secteur: "Tourisme / Hôtellerie", besoin: "Terrain hôtelier", surface: 3000, emplois: 18, budget: 1800000, echeance: "2026-06", statut: "installe", commune_cible: "Eugénie-les-Bains", notes: "Dossier validé. Permis de construire déposé. Ouverture prévue T2 2026.", updated_at: "2025-05-30" },
  { id: 6, porteur: "SARL Tursan Viandes", entreprise: "TURSAN VIANDES", secteur: "Agro-alimentaire", besoin: "Extension abattoir", surface: 1200, emplois: 8, budget: 600000, echeance: "2025-06", statut: "abandonne", commune_cible: undefined, notes: "Projet annulé — financement non obtenu.", updated_at: "2025-04-12" },
];

export default function CRMPage() {
  const router = useRouter();
  const [session, setSession] = useState<Record<string, string> | null>(null);
  const [vue, setVue] = useState<"kanban" | "liste">("kanban");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Dossier | null>(null);

  useEffect(() => {
    const s = localStorage.getItem("session");
    if (!s) { router.push("/connexion"); return; }
    const sess = JSON.parse(s);
    if (!["admin", "agent", "elu"].includes(sess.role)) { router.push("/dashboard"); return; }
    setSession(sess);
  }, [router]);

  if (!session) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-4 border-pine border-t-transparent rounded-full" /></div>;

  const filtered = MOCK_DOSSIERS.filter(d =>
    d.porteur.toLowerCase().includes(search.toLowerCase()) ||
    d.entreprise.toLowerCase().includes(search.toLowerCase()) ||
    d.secteur.toLowerCase().includes(search.toLowerCase())
  );

  const getStatut = (id: Statut) => STATUTS.find(s => s.id === id)!;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-pine text-3xl">Suivi des porteurs de projet</h1>
          <p className="text-ink/50 text-sm mt-1 font-body">{filtered.length} dossiers · Connecté en tant que {session.prenom}</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="text-ink/50 hover:text-pine text-sm font-body transition-colors">← Tableau de bord</Link>
          <button onClick={() => { localStorage.removeItem("session"); router.push("/connexion"); }} className="flex items-center gap-2 text-ink/40 hover:text-pine px-3 py-2 rounded-lg border border-ink/10 text-sm font-body transition-colors">
            <LogOut size={14} /> Déconnexion
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="relative flex-1 min-w-48">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/40" />
          <input
            type="search"
            placeholder="Rechercher un porteur, entreprise, secteur…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 border border-ink/20 rounded-xl text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss"
          />
        </div>
        <div className="flex gap-1">
          {(["kanban", "liste"] as const).map(v => (
            <button key={v} onClick={() => setVue(v)} className={`px-4 py-2 rounded-lg text-sm font-display font-semibold transition-colors ${vue === v ? "bg-pine text-white" : "bg-card border border-ink/10 text-ink/60 hover:text-pine"}`}>
              {v === "kanban" ? "Kanban" : "Liste"}
            </button>
          ))}
        </div>
        <button className="flex items-center gap-2 bg-gold text-pine px-4 py-2.5 rounded-xl font-display font-semibold text-sm hover:bg-gold-soft transition-colors">
          <Plus size={16} /> Nouveau dossier
        </button>
      </div>

      {vue === "kanban" && (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {STATUTS.map(statut => {
            const dossiers = filtered.filter(d => d.statut === statut.id);
            return (
              <div key={statut.id} className="flex-shrink-0 w-64">
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-xs font-display font-bold px-2.5 py-1 rounded-full ${statut.bg} ${statut.color}`}>{statut.label}</span>
                  <span className="text-xs text-ink/40 font-mono">{dossiers.length}</span>
                </div>
                <div className="space-y-3">
                  {dossiers.length === 0 ? (
                    <div className="bg-paper/60 border border-dashed border-ink/10 rounded-xl p-4 text-center text-xs text-ink/30 font-body">Aucun dossier</div>
                  ) : dossiers.map(d => (
                    <button
                      key={d.id}
                      onClick={() => setSelected(d)}
                      className="w-full text-left bg-card rounded-xl border border-ink/5 shadow-sm p-4 hover:shadow-md hover:border-pine/20 transition-all"
                    >
                      <p className="font-display font-semibold text-pine text-sm mb-1 line-clamp-1">{d.entreprise}</p>
                      <p className="text-xs text-ink/50 font-body mb-2">{d.porteur}</p>
                      <div className="flex flex-wrap gap-1 text-xs">
                        <span className="bg-paper text-ink/60 px-2 py-0.5 rounded font-body">{d.secteur.split(" / ")[0]}</span>
                        <span className="bg-paper text-ink/60 px-2 py-0.5 rounded font-mono">{d.surface.toLocaleString()} m²</span>
                      </div>
                      {d.commune_cible && (
                        <p className="text-xs text-ink/40 mt-2 flex items-center gap-1 font-body">
                          <MapPin size={10} /> {d.commune_cible}
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {vue === "liste" && (
        <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
          <table className="w-full text-sm" role="table">
            <thead>
              <tr className="bg-paper border-b border-ink/5">
                {["Porteur / Entreprise", "Secteur", "Surface", "Statut", "Échéance", ""].map(h => (
                  <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-display font-semibold text-ink/60">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-ink/30 font-body text-sm">Aucun dossier ne correspond à la recherche</td></tr>
              ) : filtered.map(d => {
                const st = getStatut(d.statut);
                return (
                  <tr key={d.id} className="border-b border-ink/5 hover:bg-paper/50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-display font-semibold text-pine text-sm">{d.entreprise}</p>
                      <p className="text-xs text-ink/50 font-body">{d.porteur}</p>
                    </td>
                    <td className="px-4 py-3 text-ink/60 text-xs font-body">{d.secteur}</td>
                    <td className="px-4 py-3 font-mono text-sm text-ink/70">{d.surface.toLocaleString()} m²</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-display font-bold px-2 py-0.5 rounded-full ${st.bg} ${st.color}`}>{st.label}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-ink/50">{d.echeance}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => setSelected(d)} className="text-moss hover:text-pine transition-colors" aria-label="Voir le dossier">
                        <ChevronRight size={16} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex" role="dialog" aria-modal aria-label={`Dossier ${selected.entreprise}`}>
          <div className="flex-1 bg-black/30 backdrop-blur-sm" onClick={() => setSelected(null)} />
          <div className="w-full max-w-lg bg-card shadow-2xl overflow-y-auto">
            <div className="p-6 border-b border-ink/5 flex items-start justify-between">
              <div>
                <h2 className="font-display font-bold text-pine text-xl">{selected.entreprise}</h2>
                <p className="text-ink/50 text-sm font-body mt-0.5">{selected.porteur}</p>
              </div>
              <button onClick={() => setSelected(null)} className="text-ink/40 hover:text-pine p-1 transition-colors" aria-label="Fermer">✕</button>
            </div>
            <div className="p-6 space-y-5">
              <div>
                <p className="text-xs text-ink/40 font-mono mb-1">Statut pipeline</p>
                <span className={`text-sm font-display font-bold px-3 py-1 rounded-full ${getStatut(selected.statut).bg} ${getStatut(selected.statut).color}`}>
                  {getStatut(selected.statut).label}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {[
                  { icon: Briefcase, label: "Secteur", val: selected.secteur },
                  { icon: MapPin, label: "Commune cible", val: selected.commune_cible || "Non définie" },
                  { icon: Calendar, label: "Échéance", val: selected.echeance },
                  { icon: User, label: "Emplois prévus", val: selected.emplois + " postes" },
                  { icon: Euro, label: "Budget", val: selected.budget.toLocaleString("fr-FR") + " €" },
                  { icon: MapPin, label: "Surface", val: selected.surface.toLocaleString() + " m²" },
                ].map(item => (
                  <div key={item.label}>
                    <p className="text-xs text-ink/40 font-mono mb-0.5 flex items-center gap-1"><item.icon size={10} /> {item.label}</p>
                    <p className="text-sm font-body text-ink">{item.val}</p>
                  </div>
                ))}
              </div>
              <div>
                <p className="text-xs text-ink/40 font-mono mb-1">Besoin exprimé</p>
                <p className="text-sm font-body text-ink/70 bg-paper rounded-lg p-3">{selected.besoin}</p>
              </div>
              <div>
                <p className="text-xs text-ink/40 font-mono mb-1">Notes internes</p>
                <p className="text-sm font-body text-ink/70 bg-paper rounded-lg p-3">{selected.notes}</p>
              </div>
              <p className="text-xs text-ink/30 font-mono">Mis à jour le {new Date(selected.updated_at).toLocaleDateString("fr-FR")}</p>
              <div className="flex gap-3 pt-2">
                <button className="flex-1 bg-pine text-white font-display font-semibold py-2.5 rounded-xl hover:bg-pine-2 transition-colors text-sm">
                  Modifier le dossier
                </button>
                <button className="px-4 py-2.5 border border-ink/20 text-ink/60 hover:text-pine rounded-xl text-sm font-body transition-colors">
                  Historique
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
