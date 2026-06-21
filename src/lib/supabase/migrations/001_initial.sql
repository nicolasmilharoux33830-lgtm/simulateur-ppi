-- ============================================================
-- Migration 001 — CA Aire-sur-l'Adour — Schéma initial
-- Maquette de démonstration
-- ============================================================

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── TYPES ────────────────────────────────────────────────
CREATE TYPE user_role AS ENUM ('public', 'entreprise', 'referent', 'elu', 'agent', 'admin');
CREATE TYPE local_statut AS ENUM ('disponible', 'loue', 'en_travaux');
CREATE TYPE entreprise_statut AS ENUM ('active', 'recherche_local', 'en_difficulte', 'projet', 'a_reprendre');
CREATE TYPE pipeline_statut AS ENUM ('contact', 'qualification', 'proposition', 'decision', 'installe', 'abandonne');
CREATE TYPE reservation_statut AS ENUM ('demandee', 'confirmee', 'refusee', 'annulee');

-- ─── PROFILES ─────────────────────────────────────────────
CREATE TABLE profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  nom         TEXT NOT NULL,
  email       TEXT NOT NULL UNIQUE,
  role        user_role NOT NULL DEFAULT 'public',
  commune     TEXT,
  valide      BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "profiles_self_read" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_admin_all" ON profiles USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
);

-- ─── ZONES ────────────────────────────────────────────────
CREATE TABLE zones (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  nom           TEXT NOT NULL,
  type          TEXT NOT NULL DEFAULT 'ZAE',
  surface_ha    NUMERIC(8,2),
  prix_m2_min   NUMERIC(8,2),
  prix_m2_max   NUMERIC(8,2),
  acces         TEXT,
  dispo_texte   TEXT,
  lat           NUMERIC(10,7),
  lng           NUMERIC(10,7),
  maj_le        DATE NOT NULL DEFAULT CURRENT_DATE,
  source        TEXT NOT NULL DEFAULT 'CA Aire-sur-l''Adour'
);
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
CREATE POLICY "zones_public_read" ON zones FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "zones_agent_write" ON zones FOR ALL USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── LOCAUX ───────────────────────────────────────────────
CREATE TABLE locaux (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  designation   TEXT NOT NULL,
  commune       TEXT NOT NULL,
  surface_m2    NUMERIC(10,2),
  loyer         NUMERIC(10,2),
  statut        local_statut NOT NULL DEFAULT 'disponible',
  maj_le        DATE NOT NULL DEFAULT CURRENT_DATE
);
ALTER TABLE locaux ENABLE ROW LEVEL SECURITY;
CREATE POLICY "locaux_public_read" ON locaux FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "locaux_agent_write" ON locaux FOR ALL USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── ENTREPRISES ──────────────────────────────────────────
CREATE TABLE entreprises (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  nom               TEXT NOT NULL,
  siret             CHAR(14),
  secteur           TEXT NOT NULL,
  commune           TEXT NOT NULL,
  adresse           TEXT NOT NULL DEFAULT '',
  effectif_tranche  TEXT,
  statut            entreprise_statut NOT NULL DEFAULT 'active',
  lat               NUMERIC(10,7),
  lng               NUMERIC(10,7),
  site_web          TEXT,
  contact           TEXT,
  notes             TEXT,
  maj_le            DATE NOT NULL DEFAULT CURRENT_DATE,
  source            TEXT NOT NULL DEFAULT 'CA Aire-sur-l''Adour'
);
ALTER TABLE entreprises ENABLE ROW LEVEL SECURITY;
CREATE POLICY "entreprises_agent_read" ON entreprises FOR SELECT USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'elu', 'referent', 'admin'))
);
CREATE POLICY "entreprises_agent_write" ON entreprises FOR ALL USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── DOSSIERS ─────────────────────────────────────────────
CREATE TABLE dossiers (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  porteur         TEXT NOT NULL,
  besoin          TEXT,
  surface         NUMERIC(10,2),
  emplois         INTEGER DEFAULT 0,
  budget          NUMERIC(15,2),
  echeance        DATE,
  statut_pipeline pipeline_statut NOT NULL DEFAULT 'contact',
  historique      JSONB NOT NULL DEFAULT '[]',
  zone_id         UUID REFERENCES zones(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE dossiers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "dossiers_agent_all" ON dossiers USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── SALLES ───────────────────────────────────────────────
CREATE TABLE salles (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  nom                 TEXT NOT NULL,
  commune             TEXT NOT NULL,
  capacite            INTEGER NOT NULL DEFAULT 0,
  equipements         JSONB NOT NULL DEFAULT '{}',
  photo_url           TEXT,
  validation_requise  BOOLEAN NOT NULL DEFAULT true
);
ALTER TABLE salles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "salles_public_read" ON salles FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "salles_agent_write" ON salles FOR ALL USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── RESERVATIONS ─────────────────────────────────────────
CREATE TABLE reservations (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  salle_id    UUID NOT NULL REFERENCES salles(id) ON DELETE CASCADE,
  profile_id  UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  debut       TIMESTAMPTZ NOT NULL,
  fin         TIMESTAMPTZ NOT NULL,
  motif       TEXT NOT NULL,
  participants INTEGER NOT NULL DEFAULT 1,
  statut      reservation_statut NOT NULL DEFAULT 'demandee',
  recurrence  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT fin_apres_debut CHECK (fin > debut)
);
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "reservations_own" ON reservations FOR SELECT USING (auth.uid() = profile_id);
CREATE POLICY "reservations_own_write" ON reservations FOR INSERT WITH CHECK (auth.uid() = profile_id);
CREATE POLICY "reservations_agent_all" ON reservations USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── LEADS ────────────────────────────────────────────────
CREATE TABLE leads (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  nom           TEXT NOT NULL,
  entreprise    TEXT,
  besoin        TEXT,
  message       TEXT,
  consentement  BOOLEAN NOT NULL DEFAULT false,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "leads_insert_anon" ON leads FOR INSERT TO anon WITH CHECK (consentement = true);
CREATE POLICY "leads_agent_read" ON leads FOR SELECT USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role IN ('agent', 'admin'))
);

-- ─── AUDIT LOG ────────────────────────────────────────────
CREATE TABLE audit_log (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  profile_id    UUID REFERENCES profiles(id),
  action        TEXT NOT NULL,
  table_cible   TEXT NOT NULL,
  cible_id      UUID,
  details       JSONB NOT NULL DEFAULT '{}',
  horodatage    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "audit_admin_read" ON audit_log FOR SELECT USING (
  EXISTS (SELECT 1 FROM profiles p WHERE p.id = auth.uid() AND p.role = 'admin')
);

-- ─── TRIGGER D'AUDIT ──────────────────────────────────────
CREATE OR REPLACE FUNCTION log_audit()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO audit_log (profile_id, action, table_cible, cible_id, details)
  VALUES (
    auth.uid(),
    TG_OP,
    TG_TABLE_NAME,
    CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
    CASE WHEN TG_OP = 'DELETE' THEN row_to_json(OLD) ELSE row_to_json(NEW) END::jsonb
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE TRIGGER audit_zones     AFTER INSERT OR UPDATE OR DELETE ON zones     FOR EACH ROW EXECUTE FUNCTION log_audit();
CREATE TRIGGER audit_locaux    AFTER INSERT OR UPDATE OR DELETE ON locaux    FOR EACH ROW EXECUTE FUNCTION log_audit();
CREATE TRIGGER audit_dossiers  AFTER INSERT OR UPDATE OR DELETE ON dossiers  FOR EACH ROW EXECUTE FUNCTION log_audit();
CREATE TRIGGER audit_reservations AFTER INSERT OR UPDATE OR DELETE ON reservations FOR EACH ROW EXECUTE FUNCTION log_audit();

-- ─── DONNÉES DE TEST ──────────────────────────────────────
-- Zones d'activité (données indicatives)
INSERT INTO zones (nom, type, surface_ha, prix_m2_min, prix_m2_max, acces, dispo_texte, lat, lng, source) VALUES
('ZAE de Peyres', 'ZAE', 22, 17, 17, 'A65 sortie Aire-sur-l''Adour', 'Dernier terrain disponible : 3 324 m²', 43.7011, -0.2630, 'CA Aire-sur-l''Adour'),
('ZA de Bassia', 'ZA', 12, 30, 35, 'RD 824', 'Lots de 1 600 à 7 500 m² disponibles', 43.6890, -0.2510, 'CA Aire-sur-l''Adour'),
('ZA des Arrats', 'ZA', 8, NULL, NULL, 'RD 232', '~5 ha disponibles', 43.7150, -0.2350, 'CA Aire-sur-l''Adour');

-- Salles communautaires (données fictives)
INSERT INTO salles (nom, commune, capacite, equipements, validation_requise) VALUES
('Salle du Conseil', 'Aire-sur-l''Adour', 60, '{"vidéoprojecteur": true, "sono": true, "climatisation": true, "wifi": true}', true),
('Salle polyvalente des Arènes', 'Aire-sur-l''Adour', 200, '{"scène": true, "sono": true, "cuisine": true, "wifi": false}', true),
('Salle de réunion Bastide', 'Aire-sur-l''Adour', 20, '{"vidéoprojecteur": true, "tableau blanc": true, "wifi": true, "visioconférence": true}', false),
('Salle des fêtes de Maurrin', 'Maurrin', 100, '{"sono": true, "cuisine": true}', true);

-- Locaux (données fictives)
INSERT INTO locaux (designation, commune, surface_m2, loyer, statut) VALUES
('Atelier industriel — ZAE Peyres bât A', 'Aire-sur-l''Adour', 450, 1800, 'disponible'),
('Bureau 45 m² — centre-ville', 'Aire-sur-l''Adour', 45, 650, 'disponible'),
('Entrepôt logistique 800 m²', 'Aire-sur-l''Adour', 800, 3200, 'disponible'),
('Local commercial RDC', 'Aire-sur-l''Adour', 80, 900, 'loue'),
('Atelier artisanal 120 m²', 'Eugénie-les-Bains', 120, 600, 'disponible');
