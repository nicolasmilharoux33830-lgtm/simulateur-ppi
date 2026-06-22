"use client";
import { useState, useMemo } from "react";
import * as XLSX from "xlsx";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from "recharts";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import MaquetteBadge from "@/components/ui/MaquetteBadge";
import { Lock, Download, Plus, Trash2 } from "lucide-react";

function LoginGate({ onLogin }: { onLogin: () => void }) {
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState("");
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (pwd === "demo2025") { onLogin(); }
    else { setErr("Mot de passe incorrect. (Indice : demo2025)"); }
  };
  return (
    <div className="min-h-[60vh] flex items-center justify-center bg-paper py-20 px-4">
      <Card className="p-8 max-w-sm w-full text-center">
        <div className="w-16 h-16 bg-pine/10 rounded-full flex items-center justify-center mx-auto mb-4">
          <Lock className="w-8 h-8 text-pine" />
        </div>
        <h1 className="font-display font-bold text-pine text-2xl mb-2">Espace professionnel</h1>
        <p className="text-ink/60 text-sm mb-6">Réservé aux agents et élus de la CA Aire-sur-l&apos;Adour</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="text-left">
            <label htmlFor="password" className="block text-sm font-display font-semibold text-ink mb-1">
              Mot de passe
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={pwd}
              onChange={e => setPwd(e.target.value)}
              className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
              aria-describedby={err ? "pwd-error" : undefined}
            />
            {err && <p id="pwd-error" role="alert" className="text-red-500 text-xs mt-1">{err}</p>}
          </div>
          <Button type="submit" variant="secondary" className="w-full">Accéder</Button>
        </form>
        <p className="text-xs text-ink/40 mt-4">
          Maquette — mot de passe de démo : <code className="font-mono">demo2025</code>
        </p>
      </Card>
      <MaquetteBadge />
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();

function computeLoan(capital: number, tauxAnnuel: number, dureeAns: number) {
  const t = tauxAnnuel / 100;
  const n = dureeAns;
  let annuite: number;
  if (t === 0) { annuite = capital / n; }
  else { annuite = capital * t / (1 - Math.pow(1 + t, -n)); }

  const table = [];
  let remaining = capital;
  for (let i = 1; i <= n; i++) {
    const interets = remaining * t;
    const amortissement = annuite - interets;
    table.push({
      annee: CURRENT_YEAR + i - 1,
      capital_debut: remaining,
      interets,
      amortissement,
      annuite,
      capital_fin: Math.max(0, remaining - amortissement),
    });
    remaining = Math.max(0, remaining - amortissement);
  }
  return { annuite, table };
}

function fmt(n: number) {
  return n.toLocaleString("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
}

function SimulateurEmprunt() {
  const [capital, setCapital] = useState(500000);
  const [taux, setTaux] = useState(3.5);
  const [duree, setDuree] = useState(15);

  const { annuite, table } = useMemo(() => computeLoan(capital, taux, duree), [capital, taux, duree]);
  const totalPaye = annuite * duree;
  const coutCredit = totalPaye - capital;

  const exportExcel = () => {
    const wb = XLSX.utils.book_new();
    const rows = [
      ["Paramètres", "", ""],
      ["Capital", capital, "€"],
      ["Taux annuel", taux, "%"],
      ["Durée", duree, "ans"],
      ["Annuité", annuite, "€"],
      ["Mensualité", annuite / 12, "€"],
      ["Coût total crédit", coutCredit, "€"],
      ["Total remboursé", totalPaye, "€"],
      [],
      ["Année", "Capital début", "Intérêts", "Amortissement", "Annuité", "Capital fin"],
      ...table.map(r => [r.annee, r.capital_debut.toFixed(2), r.interets.toFixed(2), r.amortissement.toFixed(2), r.annuite.toFixed(2), r.capital_fin.toFixed(2)]),
    ];
    const ws = XLSX.utils.aoa_to_sheet(rows);
    XLSX.utils.book_append_sheet(wb, ws, "Emprunt");
    XLSX.writeFile(wb, `simulateur-emprunt-${Date.now()}.xlsx`);
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="capital" className="block text-sm font-display font-semibold text-ink mb-1">Capital (€)</label>
          <input id="capital" type="number" min={0} step={10000}
            value={capital} onChange={e => setCapital(Number(e.target.value))}
            className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss" />
        </div>
        <div>
          <label htmlFor="taux" className="block text-sm font-display font-semibold text-ink mb-1">Taux annuel (%)</label>
          <input id="taux" type="number" min={0} max={20} step={0.1}
            value={taux} onChange={e => setTaux(Number(e.target.value))}
            className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss" />
        </div>
        <div>
          <label htmlFor="duree" className="block text-sm font-display font-semibold text-ink mb-1">Durée (années)</label>
          <input id="duree" type="number" min={1} max={50}
            value={duree} onChange={e => setDuree(Number(e.target.value))}
            className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss" />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Annuité", value: fmt(annuite) },
          { label: "Mensualité", value: fmt(annuite / 12) },
          { label: "Coût total du crédit", value: fmt(coutCredit) },
          { label: "Total remboursé", value: fmt(totalPaye) },
        ].map(item => (
          <Card key={item.label} className="p-4 text-center">
            <div className="text-xl font-display font-bold text-pine">{item.value}</div>
            <div className="text-xs text-ink/50 mt-1">{item.label}</div>
          </Card>
        ))}
      </div>

      <div className="flex justify-between items-center">
        <h3 className="font-display font-semibold text-pine">Tableau d&apos;amortissement</h3>
        <Button variant="ghost" size="sm" onClick={exportExcel}>
          <Download className="w-4 h-4 mr-1" /> Export Excel
        </Button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-ink/10">
        <table className="w-full text-sm text-left" aria-label="Tableau d'amortissement annuel">
          <thead className="bg-pine text-white">
            <tr>
              {["Année", "Capital début", "Intérêts", "Amortissement", "Annuité", "Capital fin"].map(h => (
                <th key={h} className="px-4 py-3 font-display font-semibold text-xs">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.map((row, i) => (
              <tr key={row.annee} className={i % 2 === 0 ? "bg-white" : "bg-paper"}>
                <td className="px-4 py-2.5 font-mono font-medium">{row.annee}</td>
                <td className="px-4 py-2.5 font-mono">{fmt(row.capital_debut)}</td>
                <td className="px-4 py-2.5 font-mono text-red-600">{fmt(row.interets)}</td>
                <td className="px-4 py-2.5 font-mono text-moss">{fmt(row.amortissement)}</td>
                <td className="px-4 py-2.5 font-mono font-semibold">{fmt(row.annuite)}</td>
                <td className="px-4 py-2.5 font-mono">{fmt(row.capital_fin)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type PPIRow = { id: string; label: string; n: number; n1: number; n2: number; n3: number };

function newRow(label = ""): PPIRow {
  return { id: crypto.randomUUID(), label, n: 0, n1: 0, n2: 0, n3: 0 };
}

const DEFAULT_DEPENSES: PPIRow[] = [
  { id: "1", label: "Rénovation bâtiment communautaire", n: 250000, n1: 150000, n2: 0, n3: 0 },
  { id: "2", label: "Voirie ZAE de Peyres", n: 80000, n1: 120000, n2: 60000, n3: 0 },
  { id: "3", label: "Équipements numériques", n: 30000, n1: 0, n2: 0, n3: 0 },
];

const DEFAULT_RESSOURCES: PPIRow[] = [
  { id: "r1", label: "Subvention État (DETR)", n: 100000, n1: 80000, n2: 20000, n3: 0 },
  { id: "r2", label: "Région Nouvelle-Aquitaine", n: 50000, n1: 40000, n2: 10000, n3: 0 },
  { id: "r3", label: "Département des Landes", n: 30000, n1: 20000, n2: 0, n3: 0 },
  { id: "r4", label: "Emprunt", n: 150000, n1: 100000, n2: 30000, n3: 0 },
  { id: "r5", label: "Autofinancement", n: 30000, n1: 30000, n2: 0, n3: 0 },
];

const YEARS = ["N", "N+1", "N+2", "N+3"];

function sumCol(rows: PPIRow[], col: "n" | "n1" | "n2" | "n3") {
  return rows.reduce((acc, r) => acc + (Number(r[col]) || 0), 0);
}

function PPIModule() {
  const [depenses, setDepenses] = useState<PPIRow[]>(DEFAULT_DEPENSES);
  const [ressources, setRessources] = useState<PPIRow[]>(DEFAULT_RESSOURCES);

  const totDepenses = { n: sumCol(depenses, "n"), n1: sumCol(depenses, "n1"), n2: sumCol(depenses, "n2"), n3: sumCol(depenses, "n3") };
  const totRessources = { n: sumCol(ressources, "n"), n1: sumCol(ressources, "n1"), n2: sumCol(ressources, "n2"), n3: sumCol(ressources, "n3") };
  const equilibre = {
    n: totRessources.n - totDepenses.n,
    n1: totRessources.n1 - totDepenses.n1,
    n2: totRessources.n2 - totDepenses.n2,
    n3: totRessources.n3 - totDepenses.n3,
  };

  const chartData = YEARS.map((y, i) => {
    const col = (["n", "n1", "n2", "n3"] as const)[i];
    return {
      year: `${CURRENT_YEAR + i}`,
      Dépenses: totDepenses[col],
      Ressources: totRessources[col],
    };
  });

  function updateRow(rows: PPIRow[], setRows: (r: PPIRow[]) => void, id: string, field: keyof PPIRow, val: string | number) {
    setRows(rows.map(r => r.id === id ? { ...r, [field]: field === "label" ? val : Number(val) } : r));
  }

  function exportPPI() {
    const wb = XLSX.utils.book_new();
    const depSheet = [
      ["Plan Pluriannuel d'Investissement — Dépenses"],
      ["Opération", CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2, CURRENT_YEAR + 3],
      ...depenses.map(r => [r.label, r.n, r.n1, r.n2, r.n3]),
      ["TOTAL DÉPENSES", totDepenses.n, totDepenses.n1, totDepenses.n2, totDepenses.n3],
      [],
      ["Plan de financement — Ressources"],
      ["Source", CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2, CURRENT_YEAR + 3],
      ...ressources.map(r => [r.label, r.n, r.n1, r.n2, r.n3]),
      ["TOTAL RESSOURCES", totRessources.n, totRessources.n1, totRessources.n2, totRessources.n3],
      [],
      ["EQUILIBRE (R-D)", equilibre.n, equilibre.n1, equilibre.n2, equilibre.n3],
    ];
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(depSheet), "PPI");
    XLSX.writeFile(wb, `ppi-${CURRENT_YEAR}-${Date.now()}.xlsx`);
  }

  function saveScenario() {
    const scenario = { depenses, ressources, savedAt: new Date().toISOString() };
    localStorage.setItem("ppi_scenario", JSON.stringify(scenario));
    alert("Scénario sauvegardé localement (maquette)");
  }

  const cols: Array<"n" | "n1" | "n2" | "n3"> = ["n", "n1", "n2", "n3"];

  function renderTable(rows: PPIRow[], setRows: (r: PPIRow[]) => void, totals: Record<string, number>, title: string) {
    return (
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-display font-semibold text-pine">{title}</h4>
          <button
            onClick={() => setRows([...rows, newRow()])}
            className="flex items-center gap-1 text-xs text-moss hover:text-pine font-display font-semibold"
          >
            <Plus className="w-3 h-3" /> Ajouter une ligne
          </button>
        </div>
        <div className="overflow-x-auto rounded-xl border border-ink/10">
          <table className="w-full text-sm" aria-label={title}>
            <thead className="bg-pine text-white">
              <tr>
                <th className="px-3 py-2 text-left font-display text-xs w-1/2">Opération / Source</th>
                {YEARS.map((y, i) => (
                  <th key={y} className="px-3 py-2 text-right font-display text-xs">{CURRENT_YEAR + i}</th>
                ))}
                <th className="px-3 py-2 w-8" aria-label="Supprimer" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={row.id} className={ri % 2 === 0 ? "bg-white" : "bg-paper"}>
                  <td className="px-2 py-1.5">
                    <input
                      value={row.label}
                      onChange={e => updateRow(rows, setRows, row.id, "label", e.target.value)}
                      className="w-full border-0 bg-transparent text-sm focus:outline-none focus:ring-1 focus:ring-moss rounded px-1"
                      aria-label={`Libellé ligne ${ri + 1}`}
                    />
                  </td>
                  {cols.map(col => (
                    <td key={col} className="px-2 py-1.5">
                      <input
                        type="number"
                        value={row[col] as number}
                        onChange={e => updateRow(rows, setRows, row.id, col, e.target.value)}
                        className="w-full text-right border-0 bg-transparent text-sm font-mono focus:outline-none focus:ring-1 focus:ring-moss rounded px-1"
                        aria-label={`Montant ${col} pour ${row.label || "ligne " + (ri + 1)}`}
                      />
                    </td>
                  ))}
                  <td className="px-2 py-1.5">
                    <button
                      onClick={() => setRows(rows.filter(r => r.id !== row.id))}
                      className="text-ink/30 hover:text-red-500 transition-colors"
                      aria-label={`Supprimer ${row.label || "cette ligne"}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="bg-pine text-white font-semibold">
                <td className="px-3 py-2 text-sm font-display">Total</td>
                {cols.map(col => (
                  <td key={col} className="px-3 py-2 text-right text-sm font-mono">{fmt(totals[col])}</td>
                ))}
                <td />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {renderTable(depenses, setDepenses, { n: totDepenses.n, n1: totDepenses.n1, n2: totDepenses.n2, n3: totDepenses.n3 }, "Dépenses d'investissement")}
      {renderTable(ressources, setRessources, { n: totRessources.n, n1: totRessources.n1, n2: totRessources.n2, n3: totRessources.n3 }, "Plan de financement — Ressources")}

      <div className="rounded-xl border-2 border-pine p-4">
        <h4 className="font-display font-bold text-pine mb-3">Équilibre (Ressources − Dépenses)</h4>
        <div className="grid grid-cols-4 gap-3">
          {cols.map((col, i) => {
            const val = equilibre[col];
            return (
              <div key={col} className={`text-center p-3 rounded-xl font-mono font-bold text-sm ${val >= 0 ? "bg-moss/10 text-moss" : "bg-red-50 text-red-600"}`}>
                <div className="text-xs font-body text-ink/50 mb-1">{CURRENT_YEAR + i}</div>
                {fmt(val)}
              </div>
            );
          })}
        </div>
      </div>

      <div>
        <h4 className="font-display font-semibold text-pine mb-3">Visualisation pluriannuelle</h4>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 0, right: 0, left: 20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#13211C11" />
              <XAxis dataKey="year" tick={{ fontSize: 12, fontFamily: "IBM Plex Sans" }} />
              <YAxis tick={{ fontSize: 11, fontFamily: "IBM Plex Mono" }} tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(val) => fmt(val as number)} />
              <Legend />
              <Bar dataKey="Dépenses" fill="#103A30" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Ressources" fill="#E6A92E" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Button variant="primary" onClick={exportPPI}>
          <Download className="w-4 h-4 mr-1" /> Export Excel
        </Button>
        <Button variant="ghost" onClick={saveScenario}>
          Sauvegarder le scénario
        </Button>
      </div>
    </div>
  );
}

export default function FinancePage() {
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState<"emprunt" | "ppi">("emprunt");

  if (!authed) return <LoginGate onLogin={() => setAuthed(true)} />;

  return (
    <div className="py-12 px-4 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="font-display font-bold text-pine text-3xl mb-2">Finance &amp; PPI</h1>
        <p className="text-ink/60">Simulateur d&apos;emprunt et Plan Pluriannuel d&apos;Investissement — espace réservé aux agents.</p>
      </div>

      <div className="flex gap-2 mb-8 border-b border-ink/10">
        {([
          { key: "emprunt", label: "Simulateur d'emprunt" },
          { key: "ppi", label: "Plan Pluriannuel d'Investissement" },
        ] as const).map(t => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`px-5 py-2.5 font-display font-semibold text-sm border-b-2 -mb-px transition-colors ${
              tab === t.key ? "border-pine text-pine" : "border-transparent text-ink/50 hover:text-pine"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "emprunt" ? <SimulateurEmprunt /> : <PPIModule />}
    </div>
  );
}
