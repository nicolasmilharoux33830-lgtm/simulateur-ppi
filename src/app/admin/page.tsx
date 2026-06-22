"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Users, Building2, MapPin, Calendar, FileText, Settings, LogOut, Check, X, Shield, AlertTriangle, Eye } from "lucide-react";

interface UserAccount {
  id: number;
  prenom: string;
  nom: string;
  email: string;
  role: string;
  commune?: string;
  valide: boolean;
  created_at: string;
}

const MOCK_USERS: UserAccount[] = [
  { id: 1, prenom: "Directeur", nom: "Martin", email: "dgs@ca-airesuradour.fr", role: "admin", valide: true, created_at: "2025-01-15" },
  { id: 2, prenom: "Chargé de mission", nom: "Dupont", email: "agent@ca-airesuradour.fr", role: "agent", valide: true, created_at: "2025-01-20" },
  { id: 3, prenom: "Élu", nom: "Bernard", email: "elu@ca-airesuradour.fr", role: "elu", valide: true, created_at: "2025-02-01" },
  { id: 4, prenom: "Référent", nom: "Lefebvre", email: "commune@ca-airesuradour.fr", role: "referent", commune: "Aire-sur-l'Adour", valide: true, created_at: "2025-02-10" },
  { id: 5, prenom: "Jean", nom: "Durand", email: "j.durand@entreprise.com", role: "entreprise", valide: false, created_at: "2025-06-19" },
  { id: 6, prenom: "Marie", nom: "Fontaine", email: "m.fontaine@association.fr", role: "public", valide: false, created_at: "2025-06-20" },
];

const AUDIT_LOG = [
  { id: 1, user: "dgs@ca-airesuradour.fr", action: "UPDATE", table: "zones", details: "ZAE Peyres — surface mise à jour", ts: "2025-06-21 09:12" },
  { id: 2, user: "agent@ca-airesuradour.fr", action: "INSERT", table: "dossiers", details: "Nouveau dossier : DUPONT Logistique", ts: "2025-06-20 14:37" },
  { id: 3, user: "agent@ca-airesuradour.fr", action: "UPDATE", table: "dossiers", details: "Statut SALS Bio → proposition", ts: "2025-06-19 11:22" },
  { id: 4, user: "dgs@ca-airesuradour.fr", action: "INSERT", table: "profiles", details: "Compte validé : j.durand@entreprise.com", ts: "2025-06-18 16:05" },
  { id: 5, user: "agent@ca-airesuradour.fr", action: "INSERT", table: "entreprises", details: "Fiche entreprise : TRANSPORT BONNEFOY", ts: "2025-06-17 10:48" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "Administrateur",
  agent: "Chargé de mission",
  elu: "Élu",
  referent: "Référent commune",
  entreprise: "Entreprise / Porteur",
  public: "Public",
};

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-pine text-white",
  agent: "bg-moss text-white",
  elu: "bg-gold text-pine",
  referent: "bg-blue-100 text-blue-800",
  entreprise: "bg-purple-100 text-purple-800",
  public: "bg-gray-100 text-gray-600",
};

type AdminTab = "comptes" | "zones" | "reservations" | "leads" | "audit";

export default function AdminPage() {
  const router = useRouter();
  const [session, setSession] = useState<Record<string, string> | null>(null);
  const [tab, setTab] = useState<AdminTab>("comptes");
  const [users, setUsers] = useState<UserAccount[]>(MOCK_USERS);

  useEffect(() => {
    const s = localStorage.getItem("session");
    if (!s) { router.push("/connexion"); return; }
    const sess = JSON.parse(s);
    if (sess.role !== "admin") { router.push("/dashboard"); return; }
    setSession(sess);

    const pending = JSON.parse(localStorage.getItem("pending_users") || "[]");
    if (pending.length > 0) {
      const newUsers = pending.map((u: Record<string, string>, i: number) => ({
        id: 100 + i,
        prenom: u.prenom,
        nom: u.nom,
        email: u.email,
        role: u.role_souhaite || "public",
        valide: false,
        created_at: u.created_at?.split("T")[0] || new Date().toISOString().split("T")[0],
      }));
      setUsers(prev => [...prev.filter(u => u.id < 100), ...newUsers]);
    }
  }, [router]);

  const handleValidate = (id: number) => {
    setUsers(users.map(u => u.id === id ? { ...u, valide: true } : u));
  };

  const handleRoleChange = (id: number, role: string) => {
    setUsers(users.map(u => u.id === id ? { ...u, role } : u));
  };

  if (!session) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-4 border-pine border-t-transparent rounded-full" /></div>;

  const pending = users.filter(u => !u.valide);

  return (
    <div className="min-h-screen bg-paper">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-pine rounded-xl flex items-center justify-center">
              <Shield size={20} className="text-gold" />
            </div>
            <div>
              <h1 className="font-display font-bold text-pine text-2xl">Espace Administration</h1>
              <p className="text-ink/50 text-xs font-body">Connecté en tant que {session.prenom} {session.nom} — Administrateur</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/dashboard" className="text-ink/50 hover:text-pine text-sm font-body transition-colors">← Tableau de bord</Link>
            <button
              onClick={() => { localStorage.removeItem("session"); router.push("/connexion"); }}
              className="flex items-center gap-2 text-ink/40 hover:text-pine px-3 py-2 rounded-lg border border-ink/10 text-sm font-body transition-colors"
            >
              <LogOut size={14} /> Déconnexion
            </button>
          </div>
        </div>

        {pending.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3 mb-6">
            <AlertTriangle size={18} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-display font-semibold text-amber-900 text-sm">{pending.length} compte{pending.length > 1 ? "s" : ""} en attente de validation</p>
              <p className="text-xs text-amber-700 font-body mt-0.5">Rendez-vous dans l&apos;onglet « Comptes & rôles » pour les examiner.</p>
            </div>
          </div>
        )}

        <div className="flex flex-wrap gap-2 mb-6">
          {[
            { id: "comptes" as AdminTab, label: "Comptes & rôles", icon: Users, badge: pending.length > 0 ? pending.length : null },
            { id: "zones" as AdminTab, label: "Zones & locaux", icon: MapPin, badge: null },
            { id: "reservations" as AdminTab, label: "Réservations", icon: Calendar, badge: null },
            { id: "leads" as AdminTab, label: "Leads reçus", icon: FileText, badge: null },
            { id: "audit" as AdminTab, label: "Journal d'audit", icon: Eye, badge: null },
          ].map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-display font-semibold transition-colors relative ${tab === t.id ? "bg-pine text-white shadow-sm" : "bg-card border border-ink/10 text-ink/60 hover:text-pine hover:border-ink/20"}`}
            >
              <t.icon size={15} />
              {t.label}
              {t.badge !== null && t.badge! > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center font-mono">{t.badge}</span>
              )}
            </button>
          ))}
        </div>

        {tab === "comptes" && (
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-ink/5 flex items-center justify-between">
              <h2 className="font-display font-bold text-pine">Comptes utilisateurs ({users.length})</h2>
              <span className="text-xs text-ink/40 font-body">Permissions vérifiées côté serveur via RLS Supabase (prototype)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" role="table">
                <thead>
                  <tr className="bg-paper border-b border-ink/5">
                    {["Nom / Email", "Rôle", "Commune", "Créé le", "Statut", "Actions"].map(h => (
                      <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-display font-semibold text-ink/60">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map(user => (
                    <tr key={user.id} className={`border-b border-ink/5 hover:bg-paper/50 transition-colors ${!user.valide ? "bg-amber-50/30" : ""}`}>
                      <td className="px-4 py-3">
                        <p className="font-display font-semibold text-pine text-sm">{user.prenom} {user.nom}</p>
                        <p className="text-xs text-ink/40 font-mono">{user.email}</p>
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={user.role}
                          onChange={e => handleRoleChange(user.id, e.target.value)}
                          className="text-xs border border-ink/10 rounded-lg px-2 py-1 font-body bg-white focus:outline-none focus:ring-1 focus:ring-moss"
                          aria-label={`Rôle de ${user.prenom} ${user.nom}`}
                        >
                          {Object.entries(ROLE_LABELS).map(([id, label]) => (
                            <option key={id} value={id}>{label}</option>
                          ))}
                        </select>
                        <span className={`ml-2 text-xs font-display font-bold px-2 py-0.5 rounded-full ${ROLE_COLORS[user.role]}`}>
                          {ROLE_LABELS[user.role]}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-ink/50 font-body">{user.commune || "—"}</td>
                      <td className="px-4 py-3 text-xs font-mono text-ink/40">{user.created_at}</td>
                      <td className="px-4 py-3">
                        {user.valide ? (
                          <span className="flex items-center gap-1 text-xs text-green-700 font-display font-semibold">
                            <Check size={12} /> Validé
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-amber-600 font-display font-semibold">
                            <AlertTriangle size={12} /> En attente
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          {!user.valide && (
                            <button
                              onClick={() => handleValidate(user.id)}
                              className="flex items-center gap-1 text-xs bg-moss text-white px-2.5 py-1 rounded-lg font-display font-semibold hover:bg-pine transition-colors"
                            >
                              <Check size={11} /> Valider
                            </button>
                          )}
                          <button className="text-xs text-ink/40 hover:text-red-600 px-2 py-1 rounded-lg border border-ink/10 transition-colors" aria-label="Suspendre le compte">
                            <X size={11} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "zones" && (
          <div className="space-y-6">
            <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display font-bold text-pine">Zones d&apos;activité</h2>
                <button className="flex items-center gap-2 bg-gold text-pine px-4 py-2 rounded-xl text-sm font-display font-semibold hover:bg-gold-soft transition-colors">
                  + Ajouter une zone
                </button>
              </div>
              {[
                { nom: "ZAE de Peyres", commune: "Aire-sur-l'Adour", surface: "22 ha", prix: "17 €/m²", dispo: "3 324 m²", maj: "21/06/2025" },
                { nom: "ZA de Bassia", commune: "Aire-sur-l'Adour", surface: "8 ha", prix: "30–35 €/m²", dispo: "Lots 1 600–7 500 m²", maj: "21/06/2025" },
                { nom: "ZA des Arrats", commune: "Barcelonne-du-Gers", surface: "5 ha", prix: "Sur demande", dispo: "~5 ha", maj: "01/06/2025" },
              ].map(zone => (
                <div key={zone.nom} className="flex items-center justify-between py-4 border-b border-ink/5 last:border-0">
                  <div>
                    <p className="font-display font-semibold text-pine">{zone.nom}</p>
                    <p className="text-xs text-ink/50 font-body">{zone.commune} · Surface : {zone.surface} · Prix : {zone.prix}</p>
                    <p className="text-xs text-moss font-mono">Disponible : {zone.dispo} · Mis à jour : {zone.maj}</p>
                  </div>
                  <div className="flex gap-2">
                    <button className="text-xs border border-ink/10 text-ink/60 hover:text-pine px-3 py-1.5 rounded-lg font-body transition-colors">Modifier</button>
                    <button className="text-xs text-red-500 hover:text-red-700 px-2 py-1.5 rounded-lg font-body transition-colors">Supprimer</button>
                  </div>
                </div>
              ))}
            </div>
            <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display font-bold text-pine">Locaux à louer (12)</h2>
                <button className="flex items-center gap-2 bg-gold text-pine px-4 py-2 rounded-xl text-sm font-display font-semibold hover:bg-gold-soft transition-colors">
                  + Ajouter un local
                </button>
              </div>
              <p className="text-ink/50 text-sm font-body bg-paper rounded-xl p-4">
                12 locaux référencés (bureaux, ateliers, entrepôts). En production, ce module permet l&apos;édition en ligne de chaque fiche (surface, loyer, statut, photos) avec sauvegarde en base et mise à jour instantanée de la vitrine.
              </p>
            </div>
          </div>
        )}

        {tab === "reservations" && (
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-ink/5">
              <h2 className="font-display font-bold text-pine">Demandes de réservation</h2>
            </div>
            <div className="divide-y divide-ink/5">
              {[
                { nom: "M. Dubois (Mairie Barcelonne)", salle: "Salle de réunion B", date: "25/06/2025", horaire: "14h–16h", statut: "demandee" },
                { nom: "Association Sportive Adour", salle: "Médiathèque — Espace rencontre", date: "27/06/2025", horaire: "18h–21h", statut: "demandee" },
                { nom: "Conseil communautaire", salle: "Salle du Conseil", date: "23/06/2025", horaire: "09h–12h", statut: "confirmee" },
              ].map((r, i) => (
                <div key={i} className="px-6 py-4 flex items-center justify-between gap-4">
                  <div>
                    <p className="font-display font-semibold text-pine text-sm">{r.nom}</p>
                    <p className="text-xs text-ink/50 font-body">{r.salle} · {r.date} · {r.horaire}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-display font-bold px-2.5 py-1 rounded-full ${r.statut === "confirmee" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}`}>
                      {r.statut === "confirmee" ? "Confirmée" : "En attente"}
                    </span>
                    {r.statut === "demandee" && (
                      <>
                        <button className="text-xs bg-moss text-white px-3 py-1.5 rounded-lg font-display font-semibold hover:bg-pine transition-colors flex items-center gap-1">
                          <Check size={12} /> Valider
                        </button>
                        <button className="text-xs text-red-500 hover:text-red-700 border border-red-200 px-3 py-1.5 rounded-lg font-body transition-colors flex items-center gap-1">
                          <X size={12} /> Refuser
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "leads" && (
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-ink/5 flex items-center justify-between">
              <h2 className="font-display font-bold text-pine">Leads reçus</h2>
              <button className="text-xs text-moss hover:text-pine font-display font-semibold underline">Exporter Excel</button>
            </div>
            <div className="p-6">
              <p className="text-ink/50 text-sm font-body bg-paper rounded-xl p-4 mb-4">
                Les leads soumis via le formulaire de la vitrine s&apos;affichent ici en temps réel. En mode prototype, ils sont stockés dans localStorage. En production : base Supabase, RLS, notification e-mail immédiate au chargé de mission.
              </p>
              <div className="space-y-3">
                {[
                  { nom: "Jean MARTIN", email: "j.martin@logistique.fr", secteur: "Logistique", surface: "1 500–5 000 m²", date: "20/06/2025" },
                  { nom: "Société AGRI+", email: "contact@agriplus.com", secteur: "Agro-alimentaire", surface: "500–1 500 m²", date: "19/06/2025" },
                ].map((lead, i) => (
                  <div key={i} className="flex items-center justify-between py-3 px-4 bg-paper rounded-xl">
                    <div>
                      <p className="font-display font-semibold text-pine text-sm">{lead.nom}</p>
                      <p className="text-xs text-ink/50 font-body">{lead.email} · {lead.secteur} · {lead.surface}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-ink/40">{lead.date}</span>
                      <button className="text-xs bg-pine text-white px-3 py-1.5 rounded-lg font-display font-semibold hover:bg-pine-2 transition-colors">
                        Créer dossier CRM
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "audit" && (
          <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-ink/5">
              <h2 className="font-display font-bold text-pine">Journal d&apos;audit</h2>
              <p className="text-xs text-ink/40 font-body mt-0.5">Table <code className="font-mono bg-paper px-1 rounded">audit_log</code> — toutes les actions traçées avec horodatage et auteur</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" role="table">
                <thead>
                  <tr className="bg-paper border-b border-ink/5">
                    {["Horodatage", "Utilisateur", "Action", "Table", "Détails"].map(h => (
                      <th key={h} scope="col" className="px-4 py-3 text-left text-xs font-display font-semibold text-ink/60">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {AUDIT_LOG.map(log => (
                    <tr key={log.id} className="border-b border-ink/5 hover:bg-paper/50">
                      <td className="px-4 py-3 font-mono text-xs text-ink/50">{log.ts}</td>
                      <td className="px-4 py-3 font-mono text-xs text-ink/70">{log.user}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-display font-bold px-2 py-0.5 rounded font-mono ${log.action === "INSERT" ? "bg-green-100 text-green-700" : log.action === "UPDATE" ? "bg-blue-100 text-blue-700" : "bg-red-100 text-red-700"}`}>
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-ink/50">{log.table}</td>
                      <td className="px-4 py-3 text-xs font-body text-ink/70">{log.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
