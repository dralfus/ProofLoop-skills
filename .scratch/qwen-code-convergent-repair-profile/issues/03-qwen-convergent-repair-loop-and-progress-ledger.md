# 03 — Сходящийся Qwen repair-loop и progress ledger

**What to build:** Qwen Implementer может продолжать локальную работу без числового лимита попыток, но ticket движется дальше только при независимом доказательстве монотонного прогресса и отсутствии регрессии.

**Blocked by:** 01 — Runtime adapter contract и совместимость Codex-профиля; 02 — Qwen Code capability preflight и независимые роли.

**Status:** implemented locally; full live Qwen repair convergence pending.

- [x] Workflow различает local attempt и repair-candidate: локальная RED → fix → GREEN работа не меняет acceptance status, а candidate передаётся на независимый review.
- [x] Append-only progress ledger связывает finding fingerprint, normalized root cause, RED/GREEN evidence, hypothesis, diff/scope delta и reviewer verdict каждого candidate.
- [x] Automatic continuation разрешена только после закрытия открытого finding без регрессии принятого criterion и без неутверждённого scope expansion.
- [x] Повтор root cause без нового воспроизводимого RED evidence, regression, `NEW_REQUIREMENT`, `DESIGN_GAP` или scope expansion создаёт terminal stop gate.
- [x] После static PASS общий Verifier подтверждает acceptance и evidence; `DONE` сохраняет независимые `SPEC: PASS`, `CODE_QUALITY: PASS` и `ACCEPTED`.

Evidence: Qwen repair-ledger policy, adversarial fixtures, terminal sequence
validation and composed lifecycle scenarios pass locally. A real Qwen repair
sequence with multiple candidates and independent role verdicts has not run.
