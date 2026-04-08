# Phase 3 Relocation Map — 2026-04-06

## Summary
Este mapa documenta qué contenido se reubica fuera de memory/user para sostener baja ocupación sin perder contexto útil.

## Relocations applied

| Origen | Acción | Destino | Razón |
|---|---|---|---|
| memory: referencia `gnekt/My-Brain-Is-Full-Crew` | remove | `fati-mini-control/data/idea-log.json` (ya existente) | Es referencia/idea, no hecho durable de memoria |
| memory: nota procedural de compaction cerca de límite | remove | `docs/memory-improvement/memory-policy-v2.md` | Procedimiento operativo, no preferencia durable |
| memory: quirk ANSI en logs | keep compact + doc-policy | `docs/memory-improvement/memory-policy-v2.md` | Quirk técnico útil; mantener versión breve en memory |
| memory: cron immediate-run quirk | keep compact + doc-policy | `docs/memory-improvement/memory-policy-v2.md` | Regla técnica recurrente; versión corta en memory |

## User profile compaction
Se compactaron frases largas preservando semántica:
- regla de cierre
- métricas por TASK ID
- preferencia OAuth/no Docker
- estilo operativo proactivo

## Nota
No se movieron guardrails críticos fuera de memory/user para evitar regresión de comportamiento.