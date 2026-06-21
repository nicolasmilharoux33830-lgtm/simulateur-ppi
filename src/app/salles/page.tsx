"use client";
import { useState, useEffect } from "react";
import { MapPin, Users, Monitor, Wifi, Volume2, Calendar, Check, X, Clock, AlertCircle } from "lucide-react";
import { useForm } from "react-hook-form";
import { standardSchemaResolver } from "@hookform/resolvers/standard-schema";
import { z } from "zod";

const SALLES = [
  {
    id: 1,
    nom: "Salle du Conseil",
    commune: "Aire-sur-l'Adour",
    capacite: 50,
    equipements: { video: true, visio: true, sono: true, wifi: true, climatisation: true },
    photo: null,
    validation_requise: false,
    description: "Grande salle de réunion officielle, équipée pour les conseils communautaires.",
    couleur: "bg-pine",
  },
  {
    id: 2,
    nom: "Salle de réunion A",
    commune: "Aire-sur-l'Adour",
    capacite: 20,
    equipements: { video: true, visio: true, sono: false, wifi: true, climatisation: true },
    photo: null,
    validation_requise: false,
    description: "Salle modulable pour réunions de travail, formation, ateliers.",
    couleur: "bg-moss",
  },
  {
    id: 3,
    nom: "Salle de réunion B",
    commune: "Aire-sur-l'Adour",
    capacite: 12,
    equipements: { video: true, visio: false, sono: false, wifi: true, climatisation: false },
    photo: null,
    validation_requise: false,
    description: "Petite salle adaptée aux réunions restreintes et entretiens.",
    couleur: "bg-gold",
  },
  {
    id: 4,
    nom: "Salle communale de Grenade-sur-l'Adour",
    commune: "Grenade-sur-l'Adour",
    capacite: 80,
    equipements: { video: false, visio: false, sono: true, wifi: false, climatisation: false },
    photo: null,
    validation_requise: true,
    description: "Grande salle polyvalente communale. Validation par la mairie requise.",
    couleur: "bg-ink",
  },
  {
    id: 5,
    nom: "Médiathèque — Espace rencontre",
    commune: "Aire-sur-l'Adour",
    capacite: 30,
    equipements: { video: true, visio: false, sono: false, wifi: true, climatisation: true },
    photo: null,
    validation_requise: true,
    description: "Espace dédié aux animations culturelles et réunions associatives.",
    couleur: "bg-moss",
  },
];

const reservSchema = z.object({
  salle_id: z.number(),
  date: z.string().min(1, "Date requise"),
  heure_debut: z.string().min(1, "Heure de début requise"),
  heure_fin: z.string().min(1, "Heure de fin requise"),
  motif: z.string().min(5, "Motif requis (min. 5 caractères)"),
  participants: z.number().min(1, "Minimum 1 participant").max(200, "Maximum 200"),
  nom_contact: z.string().min(2, "Nom requis"),
  email_contact: z.string().email("Email invalide"),
}).refine(d => d.heure_fin > d.heure_debut, {
  message: "L'heure de fin doit être après le début",
  path: ["heure_fin"],
});

type ReservForm = z.infer<typeof reservSchema>;

const RESERV_EXISTANTES = [
  { salle_id: 1, date: "2025-06-23", debut: "09:00", fin: "12:00", motif: "Conseil communautaire", statut: "confirmee" },
  { salle_id: 1, date: "2025-06-25", debut: "14:00", fin: "17:00", motif: "Réunion commission finances", statut: "confirmee" },
  { salle_id: 2, date: "2025-06-23", debut: "14:00", fin: "16:00", motif: "Réunion de travail DGS", statut: "confirmee" },
  { salle_id: 3, date: "2025-06-24", debut: "10:00", fin: "11:00", motif: "Entretien recrutement", statut: "confirmee" },
];

const EQUIP_ICONS: Record<string, { icon: React.ReactNode; label: string }> = {
  video: { icon: <Monitor size={14} />, label: "Vidéoprojecteur" },
  visio: { icon: <Monitor size={14} />, label: "Visioconférence" },
  sono: { icon: <Volume2 size={14} />, label: "Sonorisation" },
  wifi: { icon: <Wifi size={14} />, label: "Wi-Fi" },
  climatisation: { icon: <Monitor size={14} />, label: "Climatisation" },
};

export default function SallesPage() {
  const [selectedSalle, setSelectedSalle] = useState<typeof SALLES[0] | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [conflictError, setConflictError] = useState<string | null>(null);
  const [session, setSession] = useState<Record<string, string> | null>(null);
  const [filterCommune, setFilterCommune] = useState("toutes");

  useEffect(() => {
    const s = localStorage.getItem("session");
    if (s) setSession(JSON.parse(s));
  }, []);

  const { register, handleSubmit, watch, formState: { errors, isSubmitting }, reset } = useForm<ReservForm>({
    resolver: standardSchemaResolver(reservSchema),
    defaultValues: { salle_id: 0, participants: 1 },
  });

  const watchDate = watch("date");
  const watchDebut = watch("heure_debut");
  const watchFin = watch("heure_fin");

  const communes = ["toutes", ...Array.from(new Set(SALLES.map(s => s.commune)))];
  const sallesFiltrees = filterCommune === "toutes" ? SALLES : SALLES.filter(s => s.commune === filterCommune);

  const checkConflict = (salleId: number, date: string, debut: string, fin: string) => {
    return RESERV_EXISTANTES.some(r =>
      r.salle_id === salleId &&
      r.date === date &&
      !(fin <= r.debut || debut >= r.fin)
    );
  };

  const onSubmit = async (data: ReservForm) => {
    setConflictError(null);
    await new Promise(r => setTimeout(r, 600));

    if (checkConflict(data.salle_id, data.date, data.heure_debut, data.heure_fin)) {
      setConflictError("Ce créneau est déjà réservé. Veuillez choisir une autre plage horaire.");
      return;
    }

    const salle = SALLES.find(s => s.id === data.salle_id);
    const needsValidation = salle?.validation_requise || !session;
    const statut = needsValidation ? "demandee" : "confirmee";

    const reservations = JSON.parse(localStorage.getItem("reservations") || "[]");
    reservations.push({ ...data, statut, id: Date.now(), created_at: new Date().toISOString() });
    localStorage.setItem("reservations", JSON.stringify(reservations));

    setSubmitted(true);
    reset();
    setSelectedSalle(null);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="mb-8">
        <h1 className="font-display font-bold text-pine text-3xl mb-2">Réservation de salles</h1>
        <p className="text-ink/50 font-body">
          Service mutualisé — {SALLES.length} salles disponibles sur le territoire des 22 communes.
        </p>
        {!session && (
          <div className="mt-4 bg-gold/10 border border-gold/30 rounded-xl p-4 flex items-start gap-3">
            <AlertCircle size={16} className="text-gold flex-shrink-0 mt-0.5" />
            <p className="text-sm text-ink/70 font-body">
              Vous consultez les disponibilités en mode public. Pour réserver,{" "}
              <a href="/connexion" className="text-moss font-semibold underline">connectez-vous</a> ou créez un compte.
              Les demandes sans compte sont soumises à validation administrative.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-6">
        {communes.map(c => (
          <button
            key={c}
            onClick={() => setFilterCommune(c)}
            className={`px-4 py-2 rounded-xl text-sm font-display font-semibold transition-colors ${filterCommune === c ? "bg-pine text-white" : "bg-card border border-ink/10 text-ink/60 hover:text-pine"}`}
          >
            {c === "toutes" ? "Toutes les communes" : c}
          </button>
        ))}
      </div>

      {submitted && (
        <div className="bg-moss/10 border border-moss/30 rounded-2xl p-6 mb-6 flex items-start gap-3">
          <Check size={20} className="text-moss flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-display font-bold text-pine">Demande enregistrée !</p>
            <p className="text-ink/60 text-sm font-body mt-1">
              {session ? "Votre réservation a été confirmée automatiquement." : "Votre demande sera examinée par un administrateur. Vous recevrez une confirmation par e-mail."}
            </p>
            <button onClick={() => setSubmitted(false)} className="text-xs text-moss underline mt-2 font-display">Nouvelle réservation</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <h2 className="font-display font-bold text-pine text-lg">Salles disponibles</h2>
          {sallesFiltrees.map(salle => {
            const hasConflict = watchDate && watchDebut && watchFin
              ? checkConflict(salle.id, watchDate, watchDebut, watchFin)
              : false;

            return (
              <div
                key={salle.id}
                className={`bg-card rounded-2xl border-2 transition-all cursor-pointer ${selectedSalle?.id === salle.id ? "border-pine shadow-md" : "border-ink/5 hover:border-ink/20 shadow-sm"}`}
                onClick={() => setSelectedSalle(salle)}
              >
                <div className={`h-1.5 ${salle.couleur} rounded-t-2xl`} />
                <div className="p-5">
                  <div className="flex items-start justify-between gap-3 mb-2">
                    <div>
                      <h3 className="font-display font-bold text-pine">{salle.nom}</h3>
                      <p className="text-xs text-ink/50 flex items-center gap-1 mt-0.5 font-body">
                        <MapPin size={11} /> {salle.commune}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className="flex items-center gap-1 text-xs font-mono text-ink/60">
                        <Users size={12} /> {salle.capacite} pers.
                      </span>
                      {salle.validation_requise ? (
                        <span className="text-xs font-display font-semibold text-gold bg-gold/10 px-2 py-0.5 rounded-full">Validation requise</span>
                      ) : (
                        <span className="text-xs font-display font-semibold text-moss bg-moss/10 px-2 py-0.5 rounded-full">Confirmation auto.</span>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-ink/60 font-body mb-3">{salle.description}</p>

                  <div className="flex flex-wrap gap-2">
                    {Object.entries(salle.equipements).filter(([, v]) => v).map(([k]) => (
                      <span key={k} className="flex items-center gap-1 text-xs bg-paper text-ink/60 px-2.5 py-1 rounded-full font-body">
                        {EQUIP_ICONS[k]?.icon}
                        {EQUIP_ICONS[k]?.label}
                      </span>
                    ))}
                  </div>

                  {hasConflict && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-red-600 bg-red-50 rounded-lg px-3 py-2">
                      <X size={13} /> Créneau indisponible pour les horaires sélectionnés
                    </div>
                  )}

                  {selectedSalle?.id !== salle.id && (
                    <button
                      onClick={(e) => { e.stopPropagation(); setSelectedSalle(salle); }}
                      className="mt-4 w-full text-center bg-paper border border-ink/10 text-pine hover:bg-pine hover:text-white py-2 rounded-lg text-sm font-display font-semibold transition-colors"
                    >
                      Réserver cette salle
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="lg:col-span-1">
          <div className="sticky top-20">
            <h2 className="font-display font-bold text-pine text-lg mb-4">
              {selectedSalle ? `Réserver : ${selectedSalle.nom}` : "Sélectionnez une salle"}
            </h2>

            {!selectedSalle ? (
              <div className="bg-paper rounded-2xl border border-ink/5 p-8 text-center">
                <Calendar size={32} className="text-ink/20 mx-auto mb-3" />
                <p className="text-ink/40 text-sm font-body">Cliquez sur une salle pour accéder au formulaire de réservation.</p>
              </div>
            ) : (
              <div className="bg-card rounded-2xl border border-ink/5 shadow-sm p-6">
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <p className="font-display font-bold text-pine">{selectedSalle.nom}</p>
                    <p className="text-xs text-ink/50 font-body">{selectedSalle.commune} · {selectedSalle.capacite} personnes max.</p>
                  </div>
                  <button onClick={() => setSelectedSalle(null)} className="text-ink/30 hover:text-ink transition-colors">
                    <X size={18} />
                  </button>
                </div>

                {conflictError && (
                  <div role="alert" className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-3 text-xs font-body mb-4 flex items-start gap-2">
                    <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
                    {conflictError}
                  </div>
                )}

                <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
                  <input type="hidden" value={selectedSalle.id} {...register("salle_id", { valueAsNumber: true })} />

                  <div>
                    <label htmlFor="date" className="block text-sm font-display font-semibold text-ink mb-1">
                      Date <span className="text-red-500" aria-hidden>*</span>
                    </label>
                    <input
                      id="date"
                      type="date"
                      min={new Date().toISOString().split("T")[0]}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-moss"
                      {...register("date")}
                    />
                    {errors.date && <p role="alert" className="text-red-500 text-xs mt-1">{errors.date.message}</p>}
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="heure-debut" className="block text-sm font-display font-semibold text-ink mb-1">Début *</label>
                      <input id="heure-debut" type="time" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-moss" {...register("heure_debut")} />
                      {errors.heure_debut && <p role="alert" className="text-red-500 text-xs mt-1">{errors.heure_debut.message}</p>}
                    </div>
                    <div>
                      <label htmlFor="heure-fin" className="block text-sm font-display font-semibold text-ink mb-1">Fin *</label>
                      <input id="heure-fin" type="time" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-moss" {...register("heure_fin")} />
                      {errors.heure_fin && <p role="alert" className="text-red-500 text-xs mt-1">{errors.heure_fin.message}</p>}
                    </div>
                  </div>

                  <div>
                    <label htmlFor="participants" className="block text-sm font-display font-semibold text-ink mb-1">
                      Nombre de participants * <span className="text-ink/40 font-body font-normal">(max. {selectedSalle.capacite})</span>
                    </label>
                    <input
                      id="participants"
                      type="number"
                      min={1}
                      max={selectedSalle.capacite}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-moss"
                      {...register("participants", { valueAsNumber: true })}
                    />
                    {errors.participants && <p role="alert" className="text-red-500 text-xs mt-1">{errors.participants.message}</p>}
                  </div>

                  <div>
                    <label htmlFor="motif" className="block text-sm font-display font-semibold text-ink mb-1">Motif de la réservation *</label>
                    <textarea
                      id="motif"
                      rows={3}
                      className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss resize-none"
                      placeholder="Réunion de travail, formation, conseil municipal…"
                      {...register("motif")}
                    />
                    {errors.motif && <p role="alert" className="text-red-500 text-xs mt-1">{errors.motif.message}</p>}
                  </div>

                  <div>
                    <label htmlFor="nom-contact" className="block text-sm font-display font-semibold text-ink mb-1">Votre nom *</label>
                    <input id="nom-contact" type="text" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...register("nom_contact")} />
                    {errors.nom_contact && <p role="alert" className="text-red-500 text-xs mt-1">{errors.nom_contact.message}</p>}
                  </div>

                  <div>
                    <label htmlFor="email-contact" className="block text-sm font-display font-semibold text-ink mb-1">E-mail de confirmation *</label>
                    <input id="email-contact" type="email" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...register("email_contact")} />
                    {errors.email_contact && <p role="alert" className="text-red-500 text-xs mt-1">{errors.email_contact.message}</p>}
                  </div>

                  {selectedSalle.validation_requise && (
                    <div className="flex items-start gap-2 bg-gold/10 rounded-lg p-3 text-xs text-ink/60 font-body">
                      <Clock size={13} className="flex-shrink-0 text-gold mt-0.5" />
                      Cette salle nécessite une validation. Vous serez notifié par e-mail sous 48h.
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full bg-pine text-white font-display font-bold py-3 rounded-xl hover:bg-pine-2 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                  >
                    <Calendar size={16} />
                    {isSubmitting ? "Envoi…" : selectedSalle.validation_requise ? "Soumettre la demande" : "Confirmer la réservation"}
                  </button>

                  <p className="text-xs text-ink/40 font-body text-center">
                    Base légale RGPD : exécution d&apos;une mission de service public. Conservation : 1 an.
                  </p>
                </form>
              </div>
            )}

            {watchDate && (
              <div className="mt-4 bg-paper rounded-xl border border-ink/5 p-4">
                <h3 className="font-display font-semibold text-pine text-sm mb-3 flex items-center gap-2">
                  <Calendar size={14} /> Créneaux occupés le {new Date(watchDate + "T00:00:00").toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}
                </h3>
                {RESERV_EXISTANTES.filter(r => r.date === watchDate).length === 0 ? (
                  <p className="text-xs text-ink/40 font-body">Aucune réservation ce jour.</p>
                ) : (
                  <div className="space-y-2">
                    {RESERV_EXISTANTES.filter(r => r.date === watchDate).map((r, i) => {
                      const salle = SALLES.find(s => s.id === r.salle_id);
                      return (
                        <div key={i} className="flex items-center justify-between text-xs font-body">
                          <span className="text-ink/60">{salle?.nom}</span>
                          <span className="font-mono text-ink/50">{r.debut}–{r.fin}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
