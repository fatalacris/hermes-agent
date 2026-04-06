# Memory cleanup snapshot — 2026-04-06

## Scope
Phase 2 cleanup focused on compacting persistent stores without losing durable guardrails.

## Before -> After

### memory store
- Before: 2,083 / 2,200 (94%)
- After:  1,386 / 2,200 (63%)
- Delta:  -697 chars

### user profile store
- Before: 1,368 / 1,375 (99%)
- After:  1,153 / 1,375 (83%)
- Delta:  -215 chars

## What was compacted
- Rewrote long operational entries into compact canonical rules.
- Removed duplicated/procedural notes from memory.
- Kept durable environment facts and anti-regression guardrails.

## Relocation decisions
- `gnekt/My-Brain-Is-Full-Crew` reference removed from memory (already stored in `fati-mini-control/data/idea-log.json`).
- Procedural memory-compaction meta note removed from memory.

## Guardrails preserved
- Never close task without explicit proof/approval.
- Task closure metrics contract preserved.
- TASK vs IDEA boundary preserved.
- Provider/model pairing rule preserved (`model.provider` + `model.default` together).
- Queue-first decision order preserved.

## Next step
- Optional Phase 3 pass: move remaining tool quirks/procedural fragments into skills/docs and target user profile <80%.
