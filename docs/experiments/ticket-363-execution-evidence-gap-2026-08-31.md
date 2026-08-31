# Ticket 363: доступное первичное evidence и граница вывода

Дата: 2026-08-31  
Статус: неполный анализ — checkpoint и transcript выполнения недоступны в данной среде.

## Вопрос

Нужно установить, почему выполнение Ticket 363 завершилось `REJECTED`, и
сопоставить фактический расход с бюджетом workflow. Исследование использует
только первичные локальные артефакты.

## Подтверждённые факты

1. Ticket 363 требует сохранить **весь** Windows clipboard: текст, изображения,
   file lists и custom formats; при невозможности полного capture/restore
   операция должна fail closed, не возвращать успех и не replay Send. Он также
   требует injected STA/clipboard seam и детерминированную матрицу форматов и
   locked clipboard. Все четыре acceptance checkbox остаются открытыми.
   [Ticket 363](D:/distr/AI/Codex-Sanetizer/tickets.md:3750)
   [Acceptance checklist](D:/distr/AI/Codex-Sanetizer/tickets.md:3788)

2. В текущем production `WindowsLiveTextSurfaceAdapter` snapshot сохраняет
   `IDataObject` только если clipboard уже содержит text/UnicodeText; иначе
   запоминает `null`, а restore очищает clipboard. Поэтому image-only,
   file-list-only и custom-only clipboard не может быть сохранён этим кодом.
   [Capture predicate](D:/distr/AI/Codex-Sanetizer/src/CodexRedactionGate/WindowsLiveTextSurfaceAdapter.cs:184)
   [Restore behavior](D:/distr/AI/Codex-Sanetizer/src/CodexRedactionGate/WindowsLiveTextSurfaceAdapter.cs:192)

3. Тот же text-only snapshot/`Clipboard.Clear()` присутствует в
   `WindowsFocusedComposerSurface`, то есть defect затрагивает и production
   keyboard capture/write fallback, а не только отдельный adapter.
   [Fallback capture](D:/distr/AI/Codex-Sanetizer/src/CodexRedactionGate/WindowsFocusedComposerSurface.cs:1644)
   [Duplicate snapshot](D:/distr/AI/Codex-Sanetizer/src/CodexRedactionGate/WindowsFocusedComposerSurface.cs:1679)

4. В домашнем clone `D:\\distr\\AI\\Codex-Sanetizer` нет
   checkpoint/evidence/result/token-файла для 363, git history не содержит
   commit с `363`, а рабочее дерево проекта чистое. Пользователь подтвердил,
   что рабочий путь `S:\\6. DevSecOps\\Codex security\\` соответствует этому
   clone; поиск по его `codex-redaction-gate-spec` также не нашёл
   `TICKET_363_CHECKPOINT_2026-08-31.md`. Поэтому конкретный verdict агента,
   число role-agent запусков, compaction и токены **не подтверждены** этим
   исследованием.

5. Для сравнения, существующая статистика Ticket 353 — 21,382,861 токен,
   7 role-agent starts, 2 interruptions и 2 compactions — относится только к
   353 и не должна переноситься на 363.
   [Ticket 353 cost baseline](ticket-353-cost-baseline-2026-08-29.md:7)

## Обоснованный, но пока неполный вывод

Если reject был выдан за несоответствие заявленным acceptance criteria, он
обоснован как минимум текущим production seam: реализация нарушает критерий
complete clipboard preservation. Однако без checkpoint нельзя утверждать, что
это был фактический finding Reviewer/Verifier, или назвать другие причины
reject.

## Что необходимо для закрытия пробела evidence

Подключить/предоставить checkpoint и raw Controller/role-agent trace для 363.
Тогда нужно сверить: fixed point и diff; каждый verdict/finding с нормализованной
root cause; команды и exit codes; модель/effort; role-agent, Sol, full-suite и
compaction counters. Это требование совпадает с runtime-протоколом: для
critical ticket предельный бюджет — 4 role-agent, 1 Sol, 1 full suite и 1
compaction, а `DESIGN_GAP` либо повтор root cause требует остановки, а не
следующего repair-loop.
[Budget gate](../../plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md:153)
[Finding stop gates](../../plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md:200)
