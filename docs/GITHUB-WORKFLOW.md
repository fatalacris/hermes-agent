# GitHub Workflow — Local-First + Mirror

> **Repo:** [fatalacris/hermes-agent](https://github.com/fatalacris/hermes-agent)
> **Upstream:** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
> **Last updated:** 2026-04-08 (TASK ID 0021)

## Principio Fundamental

**Los archivos viven en la máquina local.** GitHub es un espejo de backup/tracking
histórico, no la fuente de verdad del estado local. Sirve para:

- Volver atrás (rollback) ante un cambio roto
- Ver diffs y auditar cambios entre versiones
- Mantener un snapshot recuperable del proyecto
- Trazabilidad de qué se hizo, cuándo y por qué

---

## Estructura de Remotes

```
origin    → fatalacris/hermes-agent.git   (nuestro fork — push aquí)
upstream  → NousResearch/hermes-agent.git (fuente upstream — solo fetch)
```

**Regla:** nunca push a upstream. Siempre fetch upstream, merge/rebase local, push a origin.

---

## Política de Ramas

| Rama | Propósito | Quién pushea | Lifetime |
|------|-----------|-------------|----------|
| `main` | Baseline estable y recuperable | Solo merges validados | Permanente |
| `develop` | Integración de cambios antes de promover a main | FATI / Cris | Permanente |
| `feature/*` | Rama por cambio real/funcionalidad | FATI / Cris | Corta — eliminar tras merge |
| `fix/*` | Corrección puntual | FATI / Cris | Corta — eliminar tras merge |
| `release/*` | Congelar y validar una versión antes de main | FATI / Cris | Temporal |

### Reglas clave

- **NO** una branch por sesión. **SÍ** una branch por cambio relevante.
- Branches mergeadas se eliminan (local y remoto).
- Branches huérfanas o abandonadas > 2 semanas se eliminan en la limpieza nocturna/semanal.
- Solo `main` y `develop` son permanentes.

### Flujo típico

```
1. git checkout develop
2. git checkout -b feature/mi-cambio
3. ... commits ...
4. git checkout develop && git merge --no-ff feature/mi-cambio
5. git branch -d feature/mi-cambio
6. git push origin develop
7. (cuando develop sea estable) git checkout main && git merge develop
8. git push origin main && git tag v0.X.Y
```

---

## Qué se Versiona y Qué No

### SÍ (goes to GitHub)

- Código fuente de Hermes Agent
- Mission Control (dashboard, server, assets)
- Documentación (docs/, GITHUB-WORKFLOW.md, post-mortems)
- Skills y scripts reutilizables
- Configs plantilla/sanitizados (sin secretos)
- Releases y tags
- Resúmenes de sesiones relevantes / incidentes

### NO (excluido via .gitignore)

- Secretos, tokens, API keys (.env, auth.json, *.token)
- Sesiones crudas (sessions/, *.jsonl)
- State databases (state.db, *.sqlite)
- Caches y tool responses
- node_modules, .venv, __pycache__
- Builds y artefactos temporales
- Datos de procesos en runtime

---

## Sync con Upstream

Cuando NousResearch publica una nueva release:

```bash
git fetch upstream
git checkout main
git merge upstream/main --ff-only   # Si hay conflictos, resolver en develop primero
git push origin main
git checkout develop
git merge main                       # Llevar los cambios upstream a develop
git push origin develop
```

**Frecuencia:** cuando hay release relevante (no cada commit del upstream).

---

## Checkpoints y Rollback

### Crear checkpoint antes de cambio riesgoso

```bash
git tag checkpoint/pre-<cambio>-$(date +%Y%m%d)
git push origin --tags
```

### Rollback a un estado anterior

```bash
# Ver tags disponibles
git tag -l 'checkpoint/*' --sort=-creatordate

# Volver al checkpoint
git checkout main
git reset --hard <tag>
git push origin main --force-with-lease
```

### Tags de release

```bash
git tag v0.X.Y -m "Release: descripción breve"
git push origin --tags
```

---

## Periodicidad de Operaciones

| Operación | Frecuencia | Ejecutor |
|-----------|-----------|----------|
| Commit/push cambios relevantes | Por evento | FATI (automático) |
| Sync upstream → main | Por release | FATI (manual/cron) |
| Limpieza de branches | Nocturno | Cron + dream cycle |
| Revisión de tags y basura | Semanal | Cris + FATI |
| Checkpoint pre-riesgo | Por evento | FATI (antes de cambios grandes) |

---

## Guardrails para FATI

1. **GitHub NO es la fuente de verdad del estado local.** Si algo no coincide entre local y GitHub, el local manda.
2. **No crear branches por sesión.** Solo por cambio real que amerite trazabilidad.
3. **No pushear secretos.** Revisar .gitignore antes de cualquier push nuevo.
4. **No force-push a develop o main** sin checkpoint previo.
5. **Antes de merge a main:** validar que develop funciona (tests, smoke check).
6. **Si hay duda sobre si algo va a GitHub:** no va. Preguntar a Cris.

---

## Comandos de Referencia Rápida

```bash
# Ver estado
git status
git branch -vv                     # Ver tracking de cada branch
git remote -v                      # Confirmar remotes
git log --oneline -10              # Últimos commits

# Sync upstream
git fetch upstream && git merge upstream/main --ff-only

# Push cambios
git push origin <branch>

# Limpiar branch mergeada
git branch -d <branch> && git push origin --delete <branch>

# Crear tag
git tag v0.X.Y -m "msg" && git push origin --tags
```
