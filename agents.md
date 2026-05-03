# FitCity - Agents Configuration

## Agentes Disponibles

### 1. explore (Recomendado - más económico)
**Use para:** Exploración de código, búsqueda de archivos, entender estructura.
**Patrones:** `*.py`, `*.ts`, `*.sql`, `*.yml`
**Limitaciones:** Solo lectura e investigación.

### 2. general
**Use para:** debugging multi-stack, tareas generales, investigación web.
**Accesos:** bash, read, glob, grep, websearch, webfetch

### 3. code-reviewer
**Use para:** Revisión de código, detección de bugs.
**Áreas:** backend/routers/*.py, backend/Services/*.py
**Focus:** Validación IA (lifting_prs.py), lógica de challenges.

---

## Quick Reference

| Tarea | Agente |
|-------|--------|
| Encontrar endpoint específico | explore |
| Debuggear error 500 | general |
| Revisar código validación IA | code-reviewer |
| Entender estructura | explore |