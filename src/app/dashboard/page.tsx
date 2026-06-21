"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from "recharts";
import { TrendingUp, Users, Building2, MapPin, FileText, Download, AlertCircle, LogOut } from "lucide-react";

const COLORS = ["#103A30", "#2E6F63", "#E6A92E", "#F2C97A", "#6B7280"];

const PIPELINE_DATA = [
  { statut: "Contact", count: 8, color: "#6B7280" },
  { statut: "Qualification", count: 5, color: "#2E6F63" },
  { statut: "Proposition", count: 3, color: "#E6A92E" },
  { statut: "Décision", count: 2, color: "#103A30" },
  { statut: "Installé", count: 4, color: "#16A34A" },
  { statut: "Abandonné", count: 1, color: "#DC2626" },
];

const LEADS_PAR_MOIS = [
  { mois: "Jan", leads: 3 }, { mois: "Fév", leads: 5 }, { mois: "Mar", leads: 4 },
  { mois: "Avr", leads: 7 }, { mois: "Mai", leads: 6 }, { mois: "Juin", leads: 9 },
];

const FILIERES_DATA = [
  { name: "Aéronautique", value: 8 }, { name: "Agro-alimentaire", value: 14 },
  { name: "Logistique", value: 6 }, { name: "Tourisme", value: 5 },
  { name: "Commerce", value: 11 }, { name: "Autre", value: 7 },
];

const INDICATEURS = [
  { label: "Taux occupation ZA", val: "78 %", detail: "14,6 ha occupés / 18,8 ha viabilisés", trend: "+3% vs N-1", ok: true },
  { label: "Locaux disponibles", val: "12", detail: "Bureaux, entrepôts, ateliers", trend: "-2 vs N-1", ok: true },
  { label: "Leads reçus (2025)", val: "47", detail: "dont 34 qualifiés", trend: "+28% vs 2024", ok: true },
  { label: "Emplois suivis", val: "312", detail: "dans les entreprises accompagnées", trend: "+18 postes", ok: true },
];

export default function DashboardPage() {
  const router = useRouter();
  const [session, setSession] = useState<Record<string, string> | null>(null);

  useEffect(() => {
    const s = localStorage.getItem("session");
    if (!s) { router.push("/connexion"); return; }
    setSession(JSON.parse(s));
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("session");
    router.push("/connexion");
  };

  if (!session) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin w-8 h-8 border-4 border-pine border-t-transparent rounded-full" /></div>;

  const ROLE_LABEL: Record<string, string> = { admin: "Administrateur", agent: "Chargé de mission", elu: "Élu", referent: "Référent commune" };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-pine text-3xl">Tableau de bord</h1>
          <p className="text-ink/50 text-sm mt-1 font-body">
            Connecté en tant que <strong>{session.prenom}</strong> — {ROLE_LABEL[session.role] || session.role}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 bg-pine text-white px-4 py-2.5 rounded-xl font-display font-semibold text-sm hover:bg-pine-2 transition-colors">
            <Download size={15} /> Rapport élus (PDF)
          </button>
          <button onClick={handleLogout} className="flex items-center gap-2 text-ink/50 hover:text-pine px-3 py-2.5 rounded-xl font-body text-sm transition-colors border border-ink/10">
            <LogOut size={15} /> Déconnexion
          </button>
        </div>
      </div>

      {/* Alerte maquette */}
      <div className="bg-gold/10 border border-gold/30 rounded-xl p-4 flex items-start gap-3 mb-8">
        <AlertCircle size={18} className="text-gold flex-shrink-0 mt-0.5" />
        <p className="text-sm text-ink/70 font-body">
          <strong className="text-pine">Maquette de démonstration</strong> — Les données ci-dessous sont fictives et illustrent les capacités du tableau de bord. En production, elles seraient alimentées en temps réel par la base Supabase.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {INDICATEURS.map(ind => (
          <div key={ind.label} className="bg-card rounded-2xl border border-ink/5 shadow-sm p-5 hover:shadow-md transition-shadow">
            <p className="text-xs text-ink/50 font-body mb-1">{ind.label}</p>
            <p className="font-display font-bold text-pine text-3xl">{ind.val}</p>
            <p className="text-xs text-ink/40 mt-1 font-body">{ind.detail}</p>
            <p className={`text-xs mt-2 font-display font-semibold ${ind.ok ? "text-moss" : "text-red-500"}`}>{ind.trend}</p>
          </div>
        ))}
      </div>

      {/* Navigation rapide */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        {[
          { href: "/crm", icon: Users, label: "CRM & Dossiers", count: "23 dossiers" },
          { href: "/observatoire", icon: Building2, label: "Observatoire", count: "51 entreprises" },
          { href: "/salles", icon: MapPin, label: "Réservations", count: "8 salles" },
          { href: "/finance", icon: FileText, label: "Finance & PPI", count: "3 scénarios" },
        ].map(nav => (
          <Link key={nav.href} href={nav.href} className="bg-card rounded-xl border border-ink/5 p-4 hover:shadow-md hover:border-moss/30 transition-all group">
            <nav.icon size={20} className="text-moss mb-2 group-hover:text-pine transition-colors" />
            <p className="font-display font-semibold text-pine text-sm">{nav.label}</p>
            <p className="text-xs text-ink/40 font-body mt-0.5">{nav.count}</p>
          </Link>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Leads par mois */}
        <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
          <h2 className="font-display font-bold text-pine mb-4 text-sm">Contacts reçus par mois (2025)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={LEADS_PAR_MOIS}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e0d5" />
              <XAxis dataKey="mois" tick={{ fontFamily: "IBM Plex Mono", fontSize: 11 }} />
              <YAxis tick={{ fontFamily: "IBM Plex Mono", fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="leads" stroke="#103A30" strokeWidth={2} dot={{ fill: "#E6A92E", r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Filières */}
        <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
          <h2 className="font-display font-bold text-pine mb-4 text-sm">Entreprises par filière</h2>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={FILIERES_DATA} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={false} labelLine={false}>
                {FILIERES_DATA.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Pipeline */}
      <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6 mb-8">
        <h2 className="font-display font-bold text-pine mb-4 text-sm">Pipeline des porteurs de projet</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={PIPELINE_DATA} layout="vertical" margin={{ left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e0d5" horizontal={false} />
            <XAxis type="number" tick={{ fontFamily: "IBM Plex Mono", fontSize: 11 }} />
            <YAxis type="category" dataKey="statut" tick={{ fontFamily: "IBM Plex Sans", fontSize: 12 }} width={100} />
            <Tooltip />
            <Bar dataKey="count" name="Dossiers">
              {PIPELINE_DATA.map((entry, i) => <Cell key={i} fill={entry.color} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="mt-4 grid grid-cols-3 md:grid-cols-6 gap-2">
          {PIPELINE_DATA.map(p => (
            <div key={p.statut} className="text-center">
              <div className="text-2xl font-display font-bold" style={{ color: p.color }}>{p.count}</div>
              <div className="text-xs text-ink/50 font-body">{p.statut}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Derniers leads (mock) */}
      <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-ink/5 flex items-center justify-between">
          <h2 className="font-display font-bold text-pine text-sm">Derniers contacts reçus</h2>
          <Link href="/crm" className="text-xs text-moss hover:text-pine font-display font-semibold underline">Voir tous →</Link>
        </div>
        <div className="divide-y divide-ink/5">
          {[
            { nom: "Société LEBLANC & Fils", secteur: "Logistique", surface: "2 000 m²", statut: "Qualification", date: "18/06/2025" },
            { nom: "SARL Tournan", secteur: "Agro-alimentaire", surface: "500 m²", statut: "Contact", date: "16/06/2025" },
            { nom: "M. Bertrand (création)", secteur: "Artisanat / BTP", surface: "200 m²", statut: "Proposition", date: "14/06/2025" },
          ].map(l => (
            <div key={l.nom} className="px-6 py-4 flex items-center justify-between hover:bg-paper/50 transition-colors">
              <div>
                <p className="font-display font-semibold text-pine text-sm">{l.nom}</p>
                <p className="text-xs text-ink/50 font-body">{l.secteur} · {l.surface}</p>
              </div>
              <div className="text-right">
                <span className="inline-block text-xs font-display font-semibold px-2.5 py-1 rounded-full bg-moss/10 text-moss">{l.statut}</span>
                <p className="text-xs text-ink/40 font-mono mt-1">{l.date}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
