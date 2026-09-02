# 03 — Сходящийся Qwen repair-loop и progress ledger

**What to build:** Qwen Implementer может продолжать локальную работу без числового лимита попыток, но ticket движется дальше только при независимом доказательстве монотонного прогресса и отсутствии регрессии.

**Blocked by:** 01 — Runtime adapter contract и совместимость Codex-профиля; 02 — Qwen Code capability preflight и независимые роли.

**Status:** ready-for-agent

- [ ] Workflow различает local attempt и repair-candidate: локальная RED → fix → GREEN работа не меняет acceptance status, а candidate передаётся fresh Reviewer.
- [ ] Append-only progress ledger связывает finding fingerprint, normalized root cause, RED/GREEN evidence, hypothesis, diff/scope delta и reviewer verdict каждого candidate.
- [ ] Automatic continuation разрешена только после закрытия открытого finding без регрессии принятого criterion и без неутверждённого scope expansion.
- [ ] Повтор root cause без нового воспроизводимого RED evidence, regression, `NEW_REQUIREMENT`, `DESIGN_GAP` или scope expansion создаёт terminal stop gate, а не новую бесконечную попытку.
- [ ] После static PASS общий Verifier подтверждает acceptance и evidence; `DONE` сохраняет независимые `SPEC: PASS`, `CODE_QUALITY: PASS` и `ACCEPTED`.
