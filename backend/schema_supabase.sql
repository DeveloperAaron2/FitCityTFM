-- ═══════════════════════════════════════════════════════════════════
--  FitCity — Supabase Schema
--  Ejecuta este SQL en: Supabase Dashboard → SQL Editor → New query
-- ═══════════════════════════════════════════════════════════════════

-- ── 1. USERS ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    TEXT NOT NULL,
    handle      TEXT NOT NULL UNIQUE,
    avatar_url  TEXT,
    total_xp    INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── 2. GYM VISITS ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gym_visits (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gym_name     TEXT NOT NULL,
    gym_address  TEXT,
    gym_lat      DOUBLE PRECISION,
    gym_lon      DOUBLE PRECISION,
    visited_at   DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gym_visits_user_id ON gym_visits(user_id);
CREATE INDEX IF NOT EXISTS idx_gym_visits_visited_at ON gym_visits(visited_at DESC);

-- ── 3. LIFTING PRs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lifting_prs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    gym_name        TEXT NOT NULL,
    exercise_name   TEXT NOT NULL,
    exercise_emoji  TEXT NOT NULL DEFAULT '🏋️',
    weight_kg       NUMERIC(6,2) NOT NULL,
    reps            INTEGER NOT NULL DEFAULT 1,
    pr_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, gym_name, exercise_name)   -- PR is per user+gym+exercise
);

CREATE INDEX IF NOT EXISTS idx_lifting_prs_user_id ON lifting_prs(user_id);

-- ── 4. CHALLENGES ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS challenges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    goal        INTEGER NOT NULL DEFAULT 1,
    xp_reward   INTEGER NOT NULL DEFAULT 250,
    emoji       TEXT NOT NULL DEFAULT '⚔️',
    active_date DATE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_challenges_active_date ON challenges(active_date);

INSERT INTO challenges (title, description, goal, xp_reward, emoji, active_date)
VALUES
    ('Reto del día', 'Visita 2 gimnasios',        2, 250, '⚔️',  CURRENT_DATE),
    ('Powerlifter',  'Registra un nuevo PR',       1, 100, '🏋️', NULL),
    ('Explorador',   'Visita 5 gimnasios distintos', 5, 500, '🗺️', NULL)
ON CONFLICT DO NOTHING;

-- ── 5. USER CHALLENGES ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_challenges (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    challenge_id UUID NOT NULL REFERENCES challenges(id) ON DELETE CASCADE,
    progress     INTEGER NOT NULL DEFAULT 0,
    completed    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, challenge_id)
);

CREATE INDEX IF NOT EXISTS idx_user_challenges_user_id ON user_challenges(user_id);

-- ═══════════════════════════════════════════════════════════════════
--  RLS — Row Level Security
--  Usamos la service_role key desde la API, así que necesitamos
--  policies permisivas para que la anon key pueda operar.
--  En producción, restringe según auth.uid().
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE users           ENABLE ROW LEVEL SECURITY;
ALTER TABLE gym_visits      ENABLE ROW LEVEL SECURITY;
ALTER TABLE lifting_prs     ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenges      ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_challenges ENABLE ROW LEVEL SECURITY;

-- ── Policies para la anon key ──────────────────────────────────────
-- Permitir todas las operaciones desde la API (la API controla el acceso)

-- USERS
CREATE POLICY "allow_all_users" ON users
    FOR ALL USING (true) WITH CHECK (true);

-- GYM VISITS
CREATE POLICY "allow_all_gym_visits" ON gym_visits
    FOR ALL USING (true) WITH CHECK (true);

-- LIFTING PRs
CREATE POLICY "allow_all_lifting_prs" ON lifting_prs
    FOR ALL USING (true) WITH CHECK (true);

-- CHALLENGES
CREATE POLICY "allow_all_challenges" ON challenges
    FOR ALL USING (true) WITH CHECK (true);

-- USER CHALLENGES
CREATE POLICY "allow_all_user_challenges" ON user_challenges
    FOR ALL USING (true) WITH CHECK (true);

-- ── 6. USER LEVELS ───────────────────────────────────────────────────────────
-- Tabla que persiste el nivel calculado de cada usuario.
-- Se actualiza desde el backend cada vez que cambia el XP.
CREATE TABLE IF NOT EXISTS user_levels (
    id       BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id  UUID REFERENCES users(id) ON DELETE CASCADE,
    level    INTEGER,
    max_xp   INTEGER,
    UNIQUE(user_id)
);

ALTER TABLE user_levels ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_user_levels" ON user_levels
    FOR ALL USING (true) WITH CHECK (true);

-- ── 7. GYM BEST LIFTS ──────────────────────────────────────────────────────
-- Stores the best validated lift video per exercise per gym.
-- Max 3 rows per gym (bench press, squat, deadlift).
CREATE TABLE IF NOT EXISTS gym_best_lifts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gym_name        TEXT NOT NULL,
    exercise_name   TEXT NOT NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    weight_kg       NUMERIC(6,2) NOT NULL,
    reps            INTEGER NOT NULL DEFAULT 1,
    video_url       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(gym_name, exercise_name)   -- Solo un mejor vídeo por ejercicio+gimnasio
);

CREATE INDEX IF NOT EXISTS idx_gym_best_lifts_gym_name ON gym_best_lifts(gym_name);

ALTER TABLE gym_best_lifts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_gym_best_lifts" ON gym_best_lifts
    FOR ALL USING (true) WITH CHECK (true);

-- ── 8. PR REPORTS ──────────────────────────────────────────────────────────
-- Stores user reports on suspicious PR weights.
-- A user can only report each PR once.
CREATE TABLE IF NOT EXISTS pr_reports (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pr_id         UUID NOT NULL REFERENCES lifting_prs(id) ON DELETE CASCADE,
    reporter_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason        TEXT NOT NULL DEFAULT 'weight_mismatch',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(pr_id, reporter_id)
);

CREATE INDEX IF NOT EXISTS idx_pr_reports_pr_id ON pr_reports(pr_id);

ALTER TABLE pr_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_pr_reports" ON pr_reports
    FOR ALL USING (true) WITH CHECK (true);
