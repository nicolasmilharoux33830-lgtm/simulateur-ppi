export type Role = 'public' | 'entreprise' | 'referent' | 'elu' | 'agent' | 'admin'

export interface Profile { id: string; nom: string; email: string; role: Role; commune?: string; valide: boolean; created_at: string; }
export interface Zone { id: string; nom: string; type: string; surface_ha: number; prix_m2_min: number; prix_m2_max: number; acces: string; dispo_texte: string; lat: number; lng: number; maj_le: string; source: string; }
export interface Local { id: string; designation: string; commune: string; surface_m2: number; loyer: number; statut: 'disponible' | 'loue' | 'en_travaux'; maj_le: string; }
export interface Entreprise { id: string; nom: string; siret?: string; secteur: string; commune: string; adresse: string; effectif_tranche: string; statut: 'active' | 'recherche_local' | 'en_difficulte' | 'projet' | 'a_reprendre'; lat?: number; lng?: number; site_web?: string; contact?: string; notes?: string; maj_le: string; source: string; }
export interface Dossier { id: string; porteur: string; besoin: string; surface: number; emplois: number; budget: number; echeance: string; statut_pipeline: 'contact' | 'qualification' | 'proposition' | 'decision' | 'installe' | 'abandonne'; historique: Record<string, unknown>[]; zone_id?: string; created_at: string; }
export interface Salle { id: string; nom: string; commune: string; capacite: number; equipements: Record<string, boolean>; photo_url?: string; validation_requise: boolean; }
export interface Reservation { id: string; salle_id: string; profile_id: string; debut: string; fin: string; motif: string; participants: number; statut: 'demandee' | 'confirmee' | 'refusee' | 'annulee'; recurrence?: string; created_at: string; }
export interface Lead { id: string; nom: string; entreprise: string; besoin: string; message: string; consentement: boolean; created_at: string; }
export interface AuditLog { id: string; profile_id: string; action: string; table_cible: string; cible_id: string; details: Record<string, unknown>; horodatage: string; }
