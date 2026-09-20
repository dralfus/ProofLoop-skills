# MINIMAL_SOLUTION_CHECK

Эта reference применяется только тогда, когда обычный preflight уже показал
вероятный выбор между новым кодом, абстракцией или зависимостью и существующим
решением. Это не самостоятельная команда, agent, repository audit или новый
acceptance gate.

## Applicability

Controller может добавить check только для ordinary non-Qwen Codex ticket, который:

- не использует Qwen и не внешний worker;
- не critical, resumed или partial;
- не затрагивает security, concurrency, native или UI boundary;
- не имеет `DESIGN_GAP` и доказуемый production/test seam для всех criteria.

Если хотя бы одно условие не выполнено, Controller записывает
`MINIMAL_SOLUTION_CHECK: NOT_APPLICABLE` с короткой причиной и не делает
дополнительного исследования. Check также опускается, когда preflight не
показал правдоподобной альтернативы в уже объявленном scope.

## Формат packet

Когда check применим, Controller добавляет в существующий
`IMPLEMENTATION_PACKET` ровно пять строк. Он использует только уже прочитанные
preflight-файлы, manifest зависимостей и прямые dependencies объявленного entry
point; отдельный tool-call, agent или полный поиск repository запрещены.

```text
Reuse: <existing component | none found in declared scope>
Platform/dependency: <stdlib/platform/already installed dependency | none applicable>
Minimal scope: <expected files or component boundary>
Alternative rejected: <specific preflight fact>
Invariant: <acceptance/security/validation/evidence that remains required>
```

`Reuse` и `Platform/dependency` фиксируют наблюдаемое состояние, а не задают
новое исследование. `Alternative rejected` не может быть общей фразой вроде
«сложнее»; это факт из объявленного scope. При отсутствии такого факта block
не добавляется.

## Реализация и review

Implementer рассматривает block только как ограничение scope. Он не может
сократить criteria, тесты, validation, security controls, evidence или
необходимую compatibility-проверку.

После обычных `SPEC` и `CODE_QUALITY` existing independent Reviewer задаёт
ровно один дополнительный вопрос:

> Появился ли новый код, dependency или abstraction при доказанной доступной
> более простой альтернативе из `MINIMAL_SOLUTION_CHECK`?

Reviewer возвращает `MINIMAL_SOLUTION: PASS | FINDING | NOT_APPLICABLE`.
`FINDING` допустим только при конкретной доказанной альтернативе в declared
scope; он классифицируется как обычный `QUALITY_BLOCKER` и следует текущему
repair-loop. Этот verdict не заменяет и не понижает `SPEC`, `CODE_QUALITY`,
acceptance ledger, Verifier, full suite или acceptance authority.

## Измерительный pilot

До отдельного решения Controller сохраняет для каждого применимого ticket:

- `MINIMAL_SOLUTION_CHECK: applied | omitted | NOT_APPLICABLE` и причину;
- production diff и test diff отдельно;
- role-agent launches, классы tool calls, fix rounds и context reuse;
- model/tier/effort, observed usage или `NOT_AVAILABLE`;
- review/verification outcome, scope drift и stop reason.

После не менее десяти применимых ordinary ticket сравнивают этот набор с
сопоставимым baseline. Адаптация остаётся только если уменьшился хотя бы один
наблюдаемый дорогой показатель без роста repair rounds, scope drift или
acceptance failures. Сокращение LOC не является доказательством экономии
токенов. При отсутствии выигрыша либо росте input/reasoning usage block
удаляется отдельным решением.
