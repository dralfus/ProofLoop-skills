# Дизайн: evidence-gated continuation для сложных Qwen-задач

## Цель

Максимизировать полезное завершение сложных задач Qwen, не путая продуктивную,
но длинную работу с зацикливанием. Пер-session ceilings остаются watchdog, а
не целевым расходом модели. Пользовательские настройки, reasoning, provider,
sampling и глубина subagent не меняются.

## Наблюдаемый failure mode

Один и тот же фиксированный protocol budget применяется к простым и сложным
задачам. Qwen может достичь потолка при доказуемом прогрессе и оставить
реализацию незавершённой. Снижение общего лимита усиливает этот риск. Обратный
вариант — просто сбросить счётчики и повторить неизменный ввод — не различает
трудную задачу и цикл и может повторно запустить ту же бесполезную
последовательность.

## Почему текущий workflow не закрывает failure mode полностью

Protocol задаёт фиксированные session limits `20 turns / 20 tool calls / 30m /
depth 1`. Runtime guard уже завершает исчерпанную сессию и запрещает инерционный
retry; новая сессия требует нового launch identity и воспроизводимого evidence.
Однако нет единого проверяемого checkpoint-контракта, который разрешает
продолжение именно после проверки актуального состояния worktree и ledger, при
неизменных требованиях ticket, но с новым continuation packet.

## Решение

Оставить `20/20/30m/depth1` верхним budget одной protocol-сессии. Не подбирать
меньшие стартовые числа только по субъективной оценке сложности. Ввести
checkpoint и progress gate для дополнительной свежей сессии:

1. После каждого завершённого local attempt, repair candidate, review verdict
   и targeted verification Controller сохраняет append-only evidence.
2. При budget stop Controller фиксирует checkpoint текущего task: неизменный
   ticket/scope и baseline, состояние worktree/diff, закрытые и открытые
   findings, последний RED/GREEN и один доказуемый следующий шаг. В отчёте
   counters предыдущего запуска не обнуляются и остаются видны.
3. Новая сессия разрешена только при валидном checkpoint, наблюдаемом
   прогрессе относительно предыдущего запуска, неизменном scope и конкретном
   следующем red-capable closure. Она получает новый receipt/launch identity
   и continuation packet с этим checkpoint; per-session counters начинаются
   заново, task history — нет.
4. Продолжение не меняет пользовательские требования задачи, но не повторяет
   дословно исходный prompt без состояния. Идентичная попытка без нового
   evidence, повтор root cause/tool fingerprint, regression, scope expansion,
   design gap или невалидный checkpoint остаются terminal stop.
5. Для native Qwen не вводится общий числовой предел repair rounds: общую
   сходимость обеспечивают ledger, verified progress и terminal stop gates.
   Каждый отдельный запуск остаётся ограниченным текущими session ceilings.
6. Глубина `1`, loop detection, независимые Reviewer/Verifier, acceptance
   authority и configured Qwen reasoning сохраняются. Персональные настройки,
   provider, sampling и внешние Qwen/Stepler-файлы не меняются.

Итоговая адаптация сначала касается совокупного продвижения через
evidence-gated fresh sessions, а не автоматического увеличения чисел в одном
запуске. Изменять per-session ceilings можно позднее только по runtime evidence
о productive session, которая систематически достигает потолка.

## Альтернативы

1. Снизить все protocol limits: отклонено, потому что это остановит и
   продуктивную сложную работу раньше, не обнаруживая цикл.
2. Сбрасывать budgets и повторять прежний ввод: отклонено, потому что это
   может воспроизвести тот же loop без нового состояния или доказательства.
3. Сохранить per-session watchdog и продолжать только по проверенному
   checkpoint: выбрано, поскольку различает продуктивное продолжение и
   повторение неудачи, не ослабляя authority gates.

## Измеримые критерии

- Простая задача может завершиться до достижения лимита; лимит не является
  целевым расходом.
- Исчерпание session budget всегда терминально для данного запуска.
- Продолжение создаёт новый launch/receipt и сохраняет всю предыдущую историю
  и counters; старый budget не стирается из evidence.
- Прогрессирующий валидный checkpoint может открыть следующую сессию без
  изменения ticket requirements, с актуальным diff/findings/test evidence.
- Повтор того же prompt без нового checkpoint/evidence не открывает сессию.
- Loop, повтор fingerprint/root cause, regression, scope expansion, design gap
  и повреждённая/несогласованная цепочка ledger блокируют continuation.
- Fixtures покрывают productive budget exhaustion → continuation и
  non-progress/repeated-tool exhaustion → terminal stop.
- Recon, QWEN_ASSIST, seal, Codex routing, role independence, configured
  reasoning, user settings, provider и sampling не меняются.

## Граница scope

Этот дизайн не увеличивает текущие protocol численные ceilings, не запускает
Qwen, не переносит disposable pilot patch в основную ветку и не даёт Qwen
acceptance authority. Его первый implementation slice — локальный pure policy
contract и Controller procedure: он принимает только Controller-attested
fingerprints, сам не читает worktree/progress ledger/test receipts и пока не
подключён к native launcher. Поэтому успешные fixtures доказывают локальное
policy поведение, а не работающий native continuation path. Отдельная задача
подключения launcher, а затем live multi-repair pilot обязательны; pilot
выполняется только после них и не переносит disposable patch без отдельного
разрешения.
