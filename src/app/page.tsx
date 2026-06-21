"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { z } from "zod";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import {
  MapPin, Zap, TrendingDown, ShieldCheck,
  ChevronRight, Phone, Mail, Building2, Check
} from "lucide-react";

/* ─── Zod schema ─────────────────────────────────────────── */
const leadSchema = z.object({
  nom: z.string().min(2, "Nom requis (min. 2 caractères)"),
  prenom: z.string().min(2, "Prénom requis"),
  email: z.string().email("Adresse e-mail invalide"),
  telephone: z.string().regex(/^(\+33|0)[1-9](\d{2}){4}$/, "Format invalide (ex : 0612345678)").optional().or(z.literal("")),
  entreprise: z.string().optional(),
  secteur: z.string().optional(),
  surface_recherchee: z.string().optional(),
  besoin: z.string().max(1000).optional(),
  consentement: z.literal(true, { error: "Vous devez accepter la politique de confidentialité" }),
});
type LeadForm = z.infer<typeof leadSchema>;

/* ─── Data ───────────────────────────────────────────────── */
const stats = [
  { value: "22", label: "communes" },
  { value: "A65", label: "Bordeaux–Pau direct" },
  { value: "17 €/m²", label: "Foncier dès" },
  { value: "5 ans", label: "Exonération CFE" },
];

const atouts = [
  { icon: MapPin, title: "Position géographique", desc: "Carrefour A65, A64 et N134. 1h de Bordeaux, 45 min de Pau, 1h15 de l'Espagne." },
  { icon: Building2, title: "Tissu productif", desc: "Aéronautique (Potez, Lauak), agro-alimentaire (Tursan, palmipèdes), tourisme et artisanat." },
  { icon: TrendingDown, title: "Coûts compétitifs", desc: "Foncier artisanal dès 17 €/m², location locaux professionnels, charges maîtrisées." },
  { icon: ShieldCheck, title: "Qualité de vie", desc: "Eugénie-les-Bains, thermalisme, Petites Villes de Demain, nature et patrimoine gascon." },
];

const zones = [
  { nom: "ZAE de Peyres", commune: "Aire-sur-l'Adour", surface: "22 ha", disponible: "dernier terrain 3 324 m²", prix: "17 €/m²", color: "bg-moss" },
  { nom: "ZA de Bassia", commune: "Commune limitrophe", surface: "lots 1 600–7 500 m²", disponible: "plusieurs lots", prix: "30–35 €/m²", color: "bg-pine" },
  { nom: "ZA des Arrats", commune: "Secteur Gers", surface: "~5 ha", disponible: "disponibles", prix: "sur demande", color: "bg-gold" },
];

const aides = [
  { titre: "Exonération CFE 5 ans", desc: "Zone de Revitalisation Rurale (ZRR). Exonération totale de Cotisation Foncière des Entreprises pendant 5 ans pour les nouvelles implantations.", badge: "ZRR" },
  { titre: "Immobilier d'entreprise", desc: "Aide directe à l'investissement pour l'acquisition ou la construction de locaux professionnels. Dossier à monter avec le chargé de mission.", badge: "Investissement" },
  { titre: "Initiative Landes", desc: "Prêts d'honneur à taux zéro jusqu'à 50 000 € pour renforcer les fonds propres des créateurs et repreneurs d'entreprise.", badge: "Prêt 0%" },
  { titre: "Interlocuteur unique", desc: "Guichet unique d'accompagnement : foncier, autorisations, RH, formation. Un seul contact pour toutes vos démarches.", badge: "Guichet unique" },
];

const filieres = [
  { emoji: "✈️", nom: "Aéronautique", detail: "Potez, Lauak" },
  { emoji: "🌾", nom: "Agro-alimentaire", detail: "Tursan, palmipèdes, Qualisud" },
  { emoji: "🚛", nom: "Logistique", detail: "Axe A65" },
  { emoji: "🌿", nom: "Tourisme", detail: "Eugénie-les-Bains" },
  { emoji: "🏪", nom: "Commerce & artisanat", detail: "Petites Villes de Demain" },
];

const etapes = [
  { num: "01", titre: "Contact initial", desc: "Remplissez le formulaire en ligne ou appelez-nous. Réponse sous 48h." },
  { num: "02", titre: "Diagnostic projet", desc: "Rendez-vous avec notre chargé de mission pour analyser votre besoin." },
  { num: "03", titre: "Proposition", desc: "Identification du foncier ou local adapté à votre activité." },
  { num: "04", titre: "Installation", desc: "Accompagnement complet jusqu'à l'ouverture de votre établissement." },
];

const partenaires = [
  "Région Nouvelle-Aquitaine", "Région Occitanie", "Département des Landes (40)",
  "Département du Gers (32)", "CCI Landes", "CMA Landes",
  "Initiative Landes", "Bpifrance", "France Travail",
];

const secteurs = [
  "Aéronautique / Défense", "Agro-alimentaire", "Logistique / Transport",
  "Tourisme / Hôtellerie", "Commerce / Distribution", "Artisanat / BTP",
  "Numérique / Services", "Industrie", "Autre",
];

export default function HomePage() {
  const [submitted, setSubmitted] = useState(false);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LeadForm>({
    resolver: standardSchemaResolver(leadSchema),
  });

  const onSubmit = async (data: LeadForm) => {
    const leads = JSON.parse(localStorage.getItem("leads") || "[]");
    leads.push({ ...data, id: crypto.randomUUID(), created_at: new Date().toISOString() });
    localStorage.setItem("leads", JSON.stringify(leads));
    setSubmitted(true);
  };

  return (
    <>
      {/* ── HERO ───────────────────────────────────────────── */}
      <section className="bg-pine text-white py-20 md:py-32 relative overflow-hidden">
        <div className="absolute inset-0 opacity-5" aria-hidden>
          <div className="absolute top-10 left-10 w-64 h-64 rounded-full bg-gold blur-3xl" />
          <div className="absolute bottom-10 right-10 w-80 h-80 rounded-full bg-moss blur-3xl" />
        </div>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative">
          <div className="max-w-3xl">
            <span className="inline-block bg-gold/20 text-gold text-sm font-display font-semibold px-3 py-1 rounded-full mb-6">
              Axe A65 Bordeaux–Pau
            </span>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold mb-6 leading-tight">
              Installez votre entreprise<br />
              <span className="text-gold">en Adour</span>
            </h1>
            <p className="text-xl text-white/80 mb-10 leading-relaxed">
              22 communes, un territoire dynamique entre Bordeaux et Pau. Foncier disponible,
              aides à l'implantation, tissu industriel structuré. Votre projet mérite le meilleur ancrage.
            </p>
            <div className="flex flex-wrap gap-4">
              <a href="#contact" className="bg-gold text-pine px-8 py-3.5 rounded-lg font-display font-semibold text-lg hover:bg-gold-soft transition-colors">
                Démarrer mon projet
              </a>
              <a href="#foncier" className="border border-white/30 text-white px-8 py-3.5 rounded-lg font-display font-semibold text-lg hover:bg-white/10 transition-colors">
                Voir le foncier
              </a>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-16">
            {stats.map((s) => (
              <div key={s.value} className="bg-white/10 rounded-2xl p-5 text-center backdrop-blur-sm border border-white/10">
                <div className="text-3xl font-display font-bold text-gold">{s.value}</div>
                <div className="text-sm text-white/70 mt-1">{s.label}</div>
              </div>
            ))}
          </div>

          {/* A65 axis animation */}
          <div className="mt-16 hidden md:block" aria-hidden="true">
            <div className="flex items-center gap-2 text-white/40 text-xs mb-3">
              <span>Axe A65</span>
            </div>
            <div className="relative h-12 flex items-center">
              <div className="absolute inset-x-0 h-0.5 bg-white/20 rounded" />
              {[
                { label: "Bordeaux", pos: "left-0" },
                { label: "Aire-sur-l'Adour", pos: "left-1/2 -translate-x-1/2" },
                { label: "Pau", pos: "right-0" },
              ].map(({ label, pos }) => (
                <div key={label} className={`absolute ${pos} flex flex-col items-center`}>
                  <div className="w-4 h-4 rounded-full bg-gold animate-dot-pulse border-2 border-pine" />
                  <span className="text-white/60 text-xs mt-2 whitespace-nowrap">{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── ATOUTS ─────────────────────────────────────────── */}
      <section id="implantez-vous" className="py-16 md:py-24 bg-paper">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-pine mb-4">
              Pourquoi choisir l&apos;Adour ?
            </h2>
            <p className="text-ink/60 text-lg max-w-2xl mx-auto">
              Un territoire qui combine accessibilité, compétitivité des coûts et qualité de vie exceptionnelle.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {atouts.map((a) => (
              <Card key={a.title} hover className="p-6">
                <div className="w-12 h-12 rounded-xl bg-pine/10 flex items-center justify-center mb-4">
                  <a.icon className="w-6 h-6 text-pine" />
                </div>
                <h3 className="font-display font-semibold text-pine mb-2">{a.title}</h3>
                <p className="text-ink/60 text-sm leading-relaxed">{a.desc}</p>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* ── FONCIER ────────────────────────────────────────── */}
      <section id="foncier" className="py-16 md:py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-pine mb-4">
              Foncier disponible
            </h2>
            <p className="text-ink/60 text-lg">
              Des zones d&apos;activité équipées et prêtes à accueillir votre projet.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {zones.map((z) => (
              <Card key={z.nom} hover className="p-6">
                <div className={`inline-block ${z.color} text-white text-xs font-display font-semibold px-3 py-1 rounded-full mb-4`}>
                  {z.commune}
                </div>
                <h3 className="font-display font-bold text-pine text-xl mb-2">{z.nom}</h3>
                <div className="space-y-2 text-sm text-ink/70">
                  <div className="flex items-center gap-2"><MapPin className="w-4 h-4 text-moss" /><span>Surface : {z.surface}</span></div>
                  <div className="flex items-center gap-2"><Check className="w-4 h-4 text-moss" /><span>Disponible : {z.disponible}</span></div>
                  <div className="flex items-center gap-2"><TrendingDown className="w-4 h-4 text-moss" /><span>Prix : {z.prix}</span></div>
                </div>
                <a href="#contact" className="mt-4 block text-center bg-paper text-pine hover:bg-gold hover:text-pine px-4 py-2 rounded-lg text-sm font-display font-semibold transition-colors border border-ink/10">
                  M&apos;informer
                </a>
              </Card>
            ))}
          </div>
          <div className="bg-gold/10 border border-gold/30 rounded-2xl p-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Building2 className="w-8 h-8 text-gold flex-shrink-0" />
              <div>
                <div className="font-display font-bold text-pine">12 locaux à louer</div>
                <div className="text-sm text-ink/60">Bureaux, entrepôts, ateliers disponibles à la location</div>
              </div>
            </div>
            <a href="#contact" className="flex-shrink-0 bg-pine text-white hover:bg-pine-2 px-5 py-2.5 rounded-lg text-sm font-display font-semibold transition-colors">
              Consulter le catalogue
            </a>
          </div>
          <p className="text-xs text-ink/40 mt-4 text-center">
            Données indicatives — source : CA Aire-sur-l&apos;Adour, mis à jour le 21/06/2025
          </p>
        </div>
      </section>

      {/* ── AIDES ──────────────────────────────────────────── */}
      <section className="py-16 md:py-24 bg-paper">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-pine mb-4">
              Aides à l&apos;implantation
            </h2>
            <p className="text-ink/60 text-lg">Bénéficiez d&apos;un dispositif complet d&apos;accompagnement financier et technique.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {aides.map((a) => (
              <Card key={a.titre} hover className="p-6">
                <div className="flex items-start gap-4">
                  <span className="flex-shrink-0 bg-gold/20 text-pine text-xs font-display font-bold px-2 py-1 rounded">
                    {a.badge}
                  </span>
                  <div>
                    <h3 className="font-display font-bold text-pine mb-2">{a.titre}</h3>
                    <p className="text-ink/60 text-sm leading-relaxed">{a.desc}</p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* ── FILIÈRES ───────────────────────────────────────── */}
      <section id="entreprises" className="py-16 md:py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-pine mb-4">
              Filières d&apos;excellence
            </h2>
            <p className="text-ink/60 text-lg">Un tissu économique diversifié et structuré autour de secteurs porteurs.</p>
          </div>
          <div className="flex flex-wrap gap-4 justify-center">
            {filieres.map((f) => (
              <Card key={f.nom} className="px-6 py-4 flex items-center gap-3 hover:shadow-md transition-shadow cursor-default">
                <span className="text-2xl">{f.emoji}</span>
                <div>
                  <div className="font-display font-semibold text-pine">{f.nom}</div>
                  <div className="text-xs text-ink/50">{f.detail}</div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* ── PARCOURS ───────────────────────────────────────── */}
      <section className="py-16 md:py-24 bg-pine text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-display font-bold mb-4">
              Votre parcours d&apos;implantation
            </h2>
            <p className="text-white/70 text-lg">4 étapes pour concrétiser votre projet en toute sérénité.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {etapes.map((e, i) => (
              <div key={e.num} className="relative">
                {i < etapes.length - 1 && (
                  <div className="hidden md:block absolute top-8 left-full w-full h-0.5 bg-gold/30 z-0" aria-hidden="true" />
                )}
                <div className="relative z-10 bg-white/10 rounded-2xl p-6 border border-white/10 backdrop-blur-sm">
                  <div className="text-4xl font-display font-bold text-gold/30 mb-2">{e.num}</div>
                  <h3 className="font-display font-bold text-white mb-2">{e.titre}</h3>
                  <p className="text-white/60 text-sm leading-relaxed">{e.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FORMULAIRE CONTACT ─────────────────────────────── */}
      <section id="contact" className="py-16 md:py-24 bg-paper">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-display font-bold text-pine mb-4">
              Démarrez votre projet
            </h2>
            <p className="text-ink/60 text-lg">Décrivez votre besoin, nous vous recontactons sous 48h.</p>
          </div>

          {submitted ? (
            <Card className="p-8 text-center">
              <div className="w-16 h-16 bg-moss/20 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-moss" />
              </div>
              <h3 className="font-display font-bold text-pine text-xl mb-2">Demande envoyée !</h3>
              <p className="text-ink/60">Notre équipe vous contactera dans les 48h ouvrées. Merci de votre intérêt pour le territoire d&apos;Aire-sur-l&apos;Adour.</p>
              <button onClick={() => setSubmitted(false)} className="mt-6 text-moss hover:text-pine text-sm font-display underline">
                Envoyer une autre demande
              </button>
            </Card>
          ) : (
            <Card className="p-8">
              <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <label htmlFor="nom" className="block text-sm font-display font-semibold text-ink mb-1">
                      Nom <span className="text-red-500" aria-hidden="true">*</span>
                    </label>
                    <input
                      id="nom"
                      type="text"
                      autoComplete="family-name"
                      aria-required="true"
                      aria-describedby={errors.nom ? "nom-error" : undefined}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
                      {...register("nom")}
                    />
                    {errors.nom && <p id="nom-error" role="alert" className="text-red-500 text-xs mt-1">{errors.nom.message}</p>}
                  </div>
                  <div>
                    <label htmlFor="prenom" className="block text-sm font-display font-semibold text-ink mb-1">
                      Prénom <span className="text-red-500" aria-hidden="true">*</span>
                    </label>
                    <input
                      id="prenom"
                      type="text"
                      autoComplete="given-name"
                      aria-required="true"
                      aria-describedby={errors.prenom ? "prenom-error" : undefined}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
                      {...register("prenom")}
                    />
                    {errors.prenom && <p id="prenom-error" role="alert" className="text-red-500 text-xs mt-1">{errors.prenom.message}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <label htmlFor="email" className="block text-sm font-display font-semibold text-ink mb-1">
                      E-mail <span className="text-red-500" aria-hidden="true">*</span>
                    </label>
                    <input
                      id="email"
                      type="email"
                      autoComplete="email"
                      aria-required="true"
                      aria-describedby={errors.email ? "email-error" : undefined}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
                      {...register("email")}
                    />
                    {errors.email && <p id="email-error" role="alert" className="text-red-500 text-xs mt-1">{errors.email.message}</p>}
                  </div>
                  <div>
                    <label htmlFor="telephone" className="block text-sm font-display font-semibold text-ink mb-1">Téléphone</label>
                    <input
                      id="telephone"
                      type="tel"
                      autoComplete="tel"
                      aria-describedby={errors.telephone ? "tel-error" : "tel-hint"}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
                      placeholder="0612345678"
                      {...register("telephone")}
                    />
                    <p id="tel-hint" className="text-xs text-ink/40 mt-1">Format : 0612345678</p>
                    {errors.telephone && <p id="tel-error" role="alert" className="text-red-500 text-xs mt-1">{errors.telephone.message}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <label htmlFor="entreprise" className="block text-sm font-display font-semibold text-ink mb-1">Entreprise</label>
                    <input
                      id="entreprise"
                      type="text"
                      autoComplete="organization"
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
                      {...register("entreprise")}
                    />
                  </div>
                  <div>
                    <label htmlFor="secteur" className="block text-sm font-display font-semibold text-ink mb-1">Secteur d&apos;activité</label>
                    <select
                      id="secteur"
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss bg-white"
                      {...register("secteur")}
                    >
                      <option value="">— Choisir —</option>
                      {secteurs.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                </div>

                <div>
                  <label htmlFor="surface_recherchee" className="block text-sm font-display font-semibold text-ink mb-1">Surface recherchée (m²)</label>
                  <input
                    id="surface_recherchee"
                    type="text"
                    className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss"
                    placeholder="ex : 500–1000 m²"
                    {...register("surface_recherchee")}
                  />
                </div>

                <div>
                  <label htmlFor="besoin" className="block text-sm font-display font-semibold text-ink mb-1">Description de votre besoin</label>
                  <textarea
                    id="besoin"
                    rows={4}
                    className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-moss resize-none"
                    placeholder="Décrivez votre projet, vos contraintes, votre calendrier…"
                    {...register("besoin")}
                  />
                </div>

                <div>
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      aria-required="true"
                      aria-describedby={errors.consentement ? "consent-error" : "consent-hint"}
                      className="mt-0.5 w-4 h-4 accent-moss"
                      {...register("consentement")}
                    />
                    <span className="text-sm text-ink/70">
                      J&apos;accepte que mes données soient traitées pour traiter ma demande d&apos;implantation.{" "}
                      <a href="/politique-confidentialite" className="text-moss underline hover:text-pine">
                        Politique de confidentialité
                      </a>{" "}
                      <span className="text-red-500" aria-hidden="true">*</span>
                    </span>
                  </label>
                  <p id="consent-hint" className="text-xs text-ink/40 mt-2 ml-7">
                    Base légale : intérêt légitime. Conservation : 3 ans. Droits :{" "}
                    <a href="mailto:rgpd@ca-airesuradour.fr" className="underline">rgpd@ca-airesuradour.fr</a>
                  </p>
                  {errors.consentement && (
                    <p id="consent-error" role="alert" className="text-red-500 text-xs mt-1 ml-7">{errors.consentement.message}</p>
                  )}
                </div>

                <Button type="submit" variant="primary" size="lg" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? "Envoi en cours…" : "Envoyer ma demande"}
                </Button>
              </form>
            </Card>
          )}
        </div>
      </section>

      {/* ── PARTENAIRES ────────────────────────────────────── */}
      <section className="py-12 bg-white border-t border-ink/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <p className="text-center text-xs text-ink/40 mb-6">
            Territoire à cheval sur 2 régions (Nouvelle-Aquitaine &amp; Occitanie) et 2 départements (Landes 40 &amp; Gers 32)
          </p>
          <div className="flex flex-wrap gap-3 justify-center">
            {partenaires.map((p) => (
              <span
                key={p}
                className="px-4 py-2 border border-ink/10 rounded-full text-sm text-ink/60 font-body hover:border-moss hover:text-moss transition-colors"
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
