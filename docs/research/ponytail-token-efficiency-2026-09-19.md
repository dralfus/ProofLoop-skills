# Ponytail: применимость для снижения расхода токенов в ProofLoop

Дата исследования: 2026-09-19.
Исследованный commit Ponytail: `e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156`.

## Краткий вывод

Ponytail не следует устанавливать в ProofLoop как глобальный always-on plugin
или делать обязательным правилом каждого role-agent. Его наиболее полезная
идея — короткая проверка, что решение действительно нуждается в новом коде,
абстракции или зависимости. Она может снижать объём diff и число последующих
исправлений у ordinary ticket с очевидной ловушкой over-engineering.

Она не является решением основных дорогих отказов ProofLoop: отсутствующего
seam, неясного acceptance contract, повторяющейся root cause, opaque reject
или недоказуемого поведения внешнего worker. Эти отказы требуют уже имеющихся
preflight, independent review, diagnostic cycle и stop gates.

Особенно важное ограничение: собственное повторное измерение Ponytail показало
на OpenAI reasoning-моделях рост стоимости на `26.2%` для `gpt-5.4-mini` и на
`38.7%` для `gpt-5.5`. Причина, названная авторами, — постоянный объём правил
во входе и дополнительное рассуждение перевешивают сокращение кода. Поэтому
сокращение строк кода нельзя считать сокращением токенов или стоимости сессии.

## Что именно делает Ponytail

Основной skill постоянно подсказывает ladder выбора решения: не делать
ненужную работу; переиспользовать существующий код; предпочитать stdlib,
нативную возможность платформы и уже установленную зависимость; затем писать
минимальную реализацию. Он также запрещает спекулятивные абстракции и требует
устранять root cause, а не симптом.

Plugin поставляет hooks `SessionStart` и `SubagentStart`. По умолчанию правило
внедряется в каждый subagent. Это удобно для одиночной coding-сессии, но в
ProofLoop добавляет один и тот же контекст Implementer, Reviewer и Verifier
без доказательства, что он нужен каждой роли.

Отдельный `ponytail-review` сознательно смотрит только на сложность:
удаление, stdlib, native platform, YAGNI и сокращение. Он явно не оценивает
корректность, безопасность и производительность.

## Доказательства и их границы

Авторы исправили ранний single-shot benchmark и добавили agentic benchmark с
изолированными Claude Code-сессиями. В одном запуске на 12 feature-задачах
получено в среднем на 54% меньше production LOC, на 22% меньше токенов и на
20% меньше стоимости. Большой выигрыш был только там, где baseline строил
лишний UI вместо native form input; на неустранимом backend CRUD варианты
сходились. Safety-проверки прошли, но это небольшой авторский эксперимент
(`Haiku 4.5`, `n=4`) и детерминированный safety floor, а не независимое
доказательство production-готовности.

Более широкий cost-verification авторов прямо ограничивает применимость:
выигрыш 42--75% на Claude не переносится на OpenAI reasoning-модели. Кроме
того, ранний agentic результат был признан недействительным из-за утечки
SessionStart hook в baseline; это хороший пример того, почему ProofLoop должен
мерить изменения workflow только в изолированных arms и с честным baseline.

У Ponytail есть также first-party предупреждение о слабой переносимости
многошагового ladder на малые локальные модели. Это не тест именно Qwen, но
достаточная причина не переносить в QWEN_ASSIST постоянную многошаговую
инструкцию без собственного controlled experiment.

## Рекомендация для ProofLoop

Не добавлять Ponytail plugin, hooks или его полный текст в global skill.
Вместо этого проверить одну минимальную ProofLoop-адаптацию только на ordinary
ticket:

1. В уже существующий compact `IMPLEMENTATION_PACKET` добавить необязательный
   блок `MINIMAL_SOLUTION_CHECK` максимум из пяти строк: существующий reuse,
   stdlib/platform/dependency choice, минимальный ожидаемый scope, причина
   отклонения альтернативы и safety/acceptance constraint.
2. Controller формирует блок сам по результату обычного preflight; отдельный
   агент, новый tool-call и полный аудит репозитория для него запрещены.
3. Implementer использует блок как ограничение реализации, но не получает
   права уменьшать acceptance criteria, тесты, validation, security controls
   или required evidence.
4. Existing independent Reviewer после обычных `SPEC` и `CODE_QUALITY`
   проверяет также один вопрос: «появился ли новый код, dependency или
   abstraction при доказанной доступной более простой альтернативе?» Это не
   новый role-agent и не замена correctness/security review.
5. Блок не применяется к critical, resumed, security, concurrency, native/UI
   или design-gap ticket, а также когда preflight уже не доказал production
   seam. Там экономия строк повышает риск false simplification.

Для QWEN_ASSIST нельзя передавать ladder целиком. В schema-first recon можно
добавить одно узкое поле: `existing_or_platform_alternative`, требующее факт
`file:line` либо значение `none-found`. Qwen не выбирает вариант сам и не
получает новое полномочие на patch или acceptance. Это соответствует текущему
read-only, bounded назначению QWEN_ASSIST и не создаёт новый бесконтрольный
reasoning loop.

## Что нельзя заимствовать

- Режимы `full`/`ultra`, постоянные hooks и требование «code first; max 3
  short lines»: они конфликтуют с compact packet, доказуемым preflight и могут
  увеличить входной контекст reasoning-моделей.
- «Одна runnable проверка» как замену независимому Reviewer, Verifier,
  acceptance ledger или full suite. Это допустимая дисциплина Implementer, но
  не acceptance authority.
- `ponytail-review` как единственный review: он намеренно не ищет security и
  correctness failures.
- Подсчёт только LOC как метрику экономии: маленький diff может быть stub,
  потерей guard или переносом сложности в неучтённый код.

## Предлагаемый измерительный эксперимент

До изменения канонического lifecycle провести один controlled pilot без
глобальной установки Ponytail. Выбрать ordinary, не security ticket, где
реально вероятна альтернатива «новый dependency/custom abstraction против
stdlib/platform/existing code». Использовать текущие budget и acceptance gates.

В ticket metrics записать: наличие `MINIMAL_SOLUTION_CHECK`, размер production
diff и tests отдельно, число role-agent launches, tool calls, fix rounds,
полный/частичный повтор контекста, модель/effort, observed usage при наличии,
итог независимых review/verification и причину каждого stop gate. Сравнивать
не только LOC, но и долю `DONE` с полным evidence, число regressions,
`BLOCKED_FOR_DESIGN` и repair rounds.

Изменение можно считать полезным лишь если при неизменной независимой приёмке
оно уменьшает хотя бы один фактически дорогой показатель без роста repair,
scope drift или acceptance failures. Если измеримый выигрыш отсутствует или
растёт input/reasoning usage, блок удаляется: он не должен становиться ещё
одним постоянным процессом ради принципа минимализма.

## Источники

- [Основной skill Ponytail](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/skills/ponytail/SKILL.md)
- [Hooks plugin](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/hooks/claude-codex-hooks.json)
- [Границы ponytail-review](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/skills/ponytail-review/SKILL.md)
- [Agentic benchmark и методика](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/benchmarks/agentic/README.md)
- [Результаты agentic benchmark](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/benchmarks/results/2026-06-18-agentic.md)
- [Повторная проверка стоимости по провайдерам](https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/benchmarks/results/2026-06-17-cost-verification.md)
