-- ============================================================================
-- FitCity — Challenges System Migration
-- Adds daily/monthly challenge types with difficulty levels and XP rewards.
-- Run this in the Supabase SQL Editor.
-- ============================================================================

-- ── 1. Add new columns to challenges ──────────────────────────────────────────

ALTER TABLE challenges
  ADD COLUMN IF NOT EXISTS type       text NOT NULL DEFAULT 'daily',
  ADD COLUMN IF NOT EXISTS difficulty text NOT NULL DEFAULT 'easy',
  ADD COLUMN IF NOT EXISTS category   text NOT NULL DEFAULT 'general',
  ADD COLUMN IF NOT EXISTS auto_track boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS month      text;  -- 'YYYY-MM' for monthly challenges

-- ── 2. Add claimed_at to user_challenges ──────────────────────────────────────

ALTER TABLE user_challenges
  ADD COLUMN IF NOT EXISTS claimed_at timestamptz;

-- ── 3. Clean existing seed data (optional — only if you want a fresh start) ──
-- DELETE FROM user_challenges;
-- DELETE FROM challenges;

-- ── 4. Seed: Daily Challenges ─────────────────────────────────────────────────
-- These use active_date. Set to today or rotate them.

INSERT INTO challenges (title, description, goal, xp_reward, emoji, type, difficulty, category, auto_track, active_date)
VALUES
  -- ── Easy (daily) ─────────────────────────────────────────────────────────────
  ('Primera visita del día',
   'Visita cualquier gimnasio hoy',
   1, 50, '🏃', 'daily', 'easy', 'gym_visits', true, CURRENT_DATE),

  ('Registra un PR',
   'Registra al menos 1 marca personal hoy',
   1, 75, '💪', 'daily', 'easy', 'prs', true, CURRENT_DATE),

  ('Calentamiento completo',
   'Haz check-in en un gimnasio hoy',
   1, 50, '🔥', 'daily', 'easy', 'gym_visits', true, CURRENT_DATE),

  -- ── Medium (daily) ──────────────────────────────────────────────────────────
  ('Doble sesión',
   'Visita 2 gimnasios distintos hoy',
   2, 150, '⚡', 'daily', 'medium', 'gym_visits', true, CURRENT_DATE),

  ('PR Hunter',
   'Registra PRs en 2 ejercicios distintos hoy',
   2, 200, '🎯', 'daily', 'medium', 'prs', true, CURRENT_DATE),

  ('Explorador urbano',
   'Visita un gimnasio nuevo (que no hayas visitado antes)',
   1, 175, '🗺️', 'daily', 'medium', 'exploration', false, CURRENT_DATE),

  -- ── Hard (daily) ────────────────────────────────────────────────────────────
  ('Triple amenaza',
   'Visita 3 gimnasios distintos en un solo día',
   3, 350, '🔱', 'daily', 'hard', 'gym_visits', true, CURRENT_DATE),

  ('Máquina de PRs',
   'Registra PRs en 3 ejercicios distintos hoy',
   3, 400, '🏆', 'daily', 'hard', 'prs', true, CURRENT_DATE),

  ('Bestia del hierro',
   'Registra un PR de más de 100 kg',
   1, 300, '🦾', 'daily', 'hard', 'prs', false, CURRENT_DATE);

-- ── 5. Seed: Monthly Challenges ───────────────────────────────────────────────
-- These use the month column.

INSERT INTO challenges (title, description, goal, xp_reward, emoji, type, difficulty, category, auto_track, month)
VALUES
  -- ── Easy (monthly) ──────────────────────────────────────────────────────────
  ('Rutina básica',
   'Visita el gimnasio al menos 5 días este mes',
   5, 300, '📅', 'monthly', 'easy', 'gym_visits', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Primeros pasos en PRs',
   'Registra al menos 3 marcas personales este mes',
   3, 250, '🌱', 'monthly', 'easy', 'prs', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Constancia inicial',
   'Visita el gimnasio al menos 8 días este mes',
   8, 400, '✨', 'monthly', 'easy', 'gym_visits', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  -- ── Medium (monthly) ────────────────────────────────────────────────────────
  ('Deportista comprometido',
   'Visita el gimnasio al menos 12 días este mes',
   12, 750, '💎', 'monthly', 'medium', 'gym_visits', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Cazador de récords',
   'Registra al menos 5 PRs este mes',
   5, 600, '🎖️', 'monthly', 'medium', 'prs', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Explorador del mes',
   'Visita al menos 3 gimnasios distintos este mes',
   3, 500, '🧭', 'monthly', 'medium', 'exploration', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Variedad de hierro',
   'Registra PRs en al menos 4 ejercicios diferentes este mes',
   4, 650, '🔄', 'monthly', 'medium', 'prs', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  -- ── Hard (monthly) ─────────────────────────────────────────────────────────
  ('Atleta dedicado',
   'Visita el gimnasio al menos 20 días este mes',
   20, 1500, '🦁', 'monthly', 'hard', 'gym_visits', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Maestro de los PRs',
   'Supera 10 marcas personales este mes',
   10, 1200, '👑', 'monthly', 'hard', 'prs', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Trotamundos fitness',
   'Visita al menos 5 gimnasios distintos este mes',
   5, 1000, '🌍', 'monthly', 'hard', 'exploration', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Fuerza bruta',
   'Registra 3 PRs de más de 80 kg este mes',
   3, 1100, '🐻', 'monthly', 'hard', 'prs', false, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  -- ── Legendary (monthly) ────────────────────────────────────────────────────
  ('Imparable',
   'Visita el gimnasio TODOS los días del mes (30 días)',
   30, 3000, '🔥', 'monthly', 'legendary', 'gym_visits', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Leyenda del hierro',
   'Registra 20 marcas personales en un solo mes',
   20, 2500, '⚔️', 'monthly', 'legendary', 'prs', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Rey de los gimnasios',
   'Visita al menos 8 gimnasios distintos este mes',
   8, 2000, '🏰', 'monthly', 'legendary', 'exploration', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM')),

  ('Máquina total',
   'Registra PRs en al menos 6 ejercicios diferentes y visita 15 días',
   15, 2800, '🤖', 'monthly', 'legendary', 'consistency', true, TO_CHAR(CURRENT_DATE, 'YYYY-MM'));

-- ============================================================================
-- Done! You should now have 9 daily + 15 monthly challenges in the database.
-- ============================================================================
