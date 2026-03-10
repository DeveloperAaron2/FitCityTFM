-- ═══════════════════════════════════════════════════════════════════
--  FitCity — Script de corrección de RLS
--  Ejecuta esto SI ya tenías las tablas creadas pero sin policies.
--  Supabase Dashboard → SQL Editor → New query → Pega y ejecuta
-- ═══════════════════════════════════════════════════════════════════

-- Eliminar policies existentes (por si acaso)
DROP POLICY IF EXISTS "allow_all_users"            ON users;
DROP POLICY IF EXISTS "allow_all_gym_visits"       ON gym_visits;
DROP POLICY IF EXISTS "allow_all_lifting_prs"      ON lifting_prs;
DROP POLICY IF EXISTS "allow_all_challenges"       ON challenges;
DROP POLICY IF EXISTS "allow_all_user_challenges"  ON user_challenges;

-- Crear policies permisivas
CREATE POLICY "allow_all_users" ON users
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_gym_visits" ON gym_visits
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_lifting_prs" ON lifting_prs
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_challenges" ON challenges
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "allow_all_user_challenges" ON user_challenges
    FOR ALL USING (true) WITH CHECK (true);
