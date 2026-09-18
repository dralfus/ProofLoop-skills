# Luna-first escalation policy

Этот reference применяется, когда Controller выбирает модель Codex для
ordinary ticket. `Luna-first` означает запрос tier `efficient`, а не
предположение по имени модели: exact model ID и поддерживаемый effort берутся
из verified runtime inventory.

## Назначение

Сначала получить дешёвый, воспроизводимый feedback на узком scope; повышать
tier только когда evidence показывает, что следующий полезный шаг требует
более глубокого рассуждения. Policy не ослабляет acceptance authority,
SEAM_FEASIBILITY, review, verification или общие stop gates.

## Разрешённый путь

1. Ordinary локальная реализация: `efficient/high` Implementer.
2. После локального finding — один scoped repair тем же Implementer.
3. Только для mechanical low-risk ticket разрешён второй scoped repair тем же
   tier. До него Controller подтверждает, что первый repair дал новую
   локализацию либо закрыл другой finding.
4. Затем Controller либо фиксирует `EFFICIENT_TIER_DEFICIENCY` и выбирает
   `standard/high`, либо останавливается с текущим budget/design gate.

Critical, resumed, security/privacy, concurrency, OS/native, irreversible
side-effect и new-owner tickets не получают этот дополнительный Luna repair.
Для них Controller выбирает `standard` по основной risk policy; Luna может
выполнить только read-only или детерминированный scoped preflight.

## EFFICIENT_TIER_DEFICIENCY

Перед первым `standard/high` spawn Controller записывает:

```text
EFFICIENT_TIER_DEFICIENCY
Предыдущая роль и model ID: <значения inventory>
Последний RED: <одна команда, exit code, first failed operation>
Fingerprint: <нормализованное значение>
Scope: <не расширен | разрешённое изменение>
Причина эскалации: <межкомпонентный контракт | неразрешённая семантика |
подтверждённая недостаточность локального repair>
Следующий closure: <один criterion -> red-capable loop>
```

Допустимые причины: после разрешённого Luna repair сохранён независимым review
локализованный finding; новый RED требует согласовать несколько существующих
owners; либо preflight установил критичный риск. Не допускаются: повтор
прежнего fingerprint, общий failed boolean без projection, отсутствие нового
RED, повышенный effort «на всякий случай» или превышение времени.

## Измерение rollout

Первые десять ordinary ticket без critical факторов образуют pilot. Для каждого
сохранить tier/model/effort, число Luna-pass, repair count, trigger escalation,
`DONE|REJECTED|BLOCKED` и observed `TOKEN_USAGE`. Успех — меньше запусков
`standard`/`frontier` без роста `REJECTED`, reopen или времени до первого
подтверждённого GREEN. Ticket с critical факторами в эту выборку не входит.