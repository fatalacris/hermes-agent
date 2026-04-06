# Memory Policy v2 (Phase 3)

## Objetivo
Mantener memoria durable y liviana, evitando que contenido operativo vuelva a inflarla.

## Buckets (source of truth)
- `memory` (agent notes): hechos durables de entorno y guardrails anti-regresión.
- `user profile`: preferencias estables de Cris (estilo, reglas de cierre, formato).
- `skills/docs`: procedimientos repetibles, playbooks y quirks operativos.
- `shared task queue`: estado, progreso, decisiones de ejecución y métricas por TASK ID.
- `idea-log.json`: ideas/referencias candidatas (no tareas activas).

## Reglas de escritura
1. Si describe *cómo hacer algo* => no va a memory; va a skill/doc.
2. Si describe *estado temporal o progreso* => va a task log.
3. Si es una *idea o referencia* => va a idea-log.json.
4. Memory/User guardan solo lo que evita repetir correcciones del usuario.
5. Antes de `memory add`, intentar `memory replace` para compactar.

## Guardrails mínimos que sí deben quedar en memoria
- Regla de cierre (no cerrar sin prueba/aprobación explícita).
- Contrato de métricas de cierre por TASK ID.
- Convención TASK/IDEA.
- Regla provider/model (`model.provider` + `model.default` juntos).
- Hechos de entorno realmente estables.

## Anti-regresión
Checklist previo a cada escritura en memory/user:
- ¿Es durable por semanas/meses?
- ¿Evita un error recurrente real?
- ¿No pertenece mejor a tasks/ideas/docs/skills?
- ¿Puede fusionarse con una entrada existente?
