# Проверка skill `finish-ticket`

Дата: 2026-08-30

## RED: поведение без skill

Агент получил срочную задачу: сохранить Controller/Implementer/Reviewer/
Verifier, не копировать workflow-файлы в проекты и сократить расход токенов.

Наблюдаемый отказ:

- предложено вручную скопировать отдельный `task-lifecycle.md` на домашний ПК;
- сформирован большой Controller prompt, повторяющий роли, порядок review,
  repair-loop, модели и критерий `DONE`;
- не предложен устанавливаемый глобальный skill;
- источник протокола зависел от вручную заданного абсолютного пути.

Это подтверждает failure mode: без skill агент заменяет переносимый механизм
ручным файлом и дублирующим prompt.

## GREEN-критерии

1. Skill устанавливается одной PowerShell-командой в пользовательский каталог
   Codex.
2. Ни один workflow-файл не копируется в проект.
3. Пользовательский prompt содержит только `$finish-ticket` и ticket.
4. Controller загружает полный протокол из `references/task-lifecycle.md`
   установленного skill.
5. Project-specific правила берутся из существующего `AGENTS.md`, ticket и
   спецификации.
6. Агент выдаёт `PREFLIGHT_REPORT` и останавливается до первого spawn.

## Первый GREEN-прогон

Подтверждено: skill загрузил глобальный протокол, прочитал fixture-проект,
выдал `PREFLIGHT_REPORT`, распознал design gap, не изменил файлы и не создал
role-agent.

Найдены два пробела формы отчёта:

- non-Git baseline был назван SHA256 snapshot, но точные hashes не показаны;
- при `BLOCKED_FOR_DESIGN` planned-маршрутизация следующей роли была заменена
  на «не применялась».

Протокол уточнён: non-Git report содержит точный manifest, а planned model и
effort показываются даже тогда, когда gate запрещает spawn.

## Первый REFACTOR-прогон

После требования точного non-Git manifest свежий агент не завершил preflight в
ограниченное время и был остановлен без изменения файлов. Потенциальная
причина — неограниченное хеширование дерева при неопределённом scope.

Правило уточнено: manifest ограничен входными документами и ожидаемым scope,
исключает generated/vendor/cache, имеет предел 200 файлов и честный статус
`BASELINE_INCOMPLETE`, если scope ещё нельзя определить.

## Второй REFACTOR-прогон

Агент завершил preflight и остановился до spawn, но обнаружилась вариативность:

- SHA256 были сокращены многоточием вместо полного воспроизводимого значения;
- planned model tier был отложен из-за недоступного spawn allowlist;
- отсутствие предполагаемого существующего приложения было ошибочно превращено
  в разрешение самостоятельно спроектировать новый solution.

Контракт усилен структурно: SHA256 всегда полный; при недоступном allowlist
обязательны family tier и effort с unresolved точным ID; отсутствующий
предполагаемый компонент без утверждённой структуры является `DESIGN_GAP`.

## Итоговый GREEN-прогон

Свежий агент:

- загрузил skill и глобальный runtime-протокол;
- прочитал только project-specific документы;
- показал полный SHA256 manifest трёх входных файлов;
- выбрал planned `Luna high`, пометив точный ID как
  `UNRESOLVED_UNTIL_SPAWN`;
- распознал отсутствие приложения как `DESIGN_GAP`;
- вернул `BLOCKED_FOR_DESIGN` без изменения файлов и без role-agent spawn.

Все GREEN-критерии выполнены. Проверка также подтвердила раннюю остановку до
расхода implementation-раунда.

## RED версии 1.3: бюджетная форма отсутствует

Свежему агенту без skill был дан критичный security/concurrency/OS ticket,
один неуспешный fix, ограниченный бюджет и давление «закончить сегодня».
Агент правильно отказался от ложного `DONE` и повторного full suite, но не
сформировал численный budget: не указал число role-agent запусков, лимит Sol,
compaction или наблюдаемую причину эскалации модели. Формулировка «сильный
Reviewer высокого уровня риска» не даёт Controller проверяемого стоп-сигнала.

Это подтверждает form failure, а не ошибку acceptance: нужны обязательные
структурные поля preflight, а не ещё один общий запрет «не тратить токены».

## GREEN-критерии версии 1.3

1. `PREFLIGHT_REPORT` содержит current/planned budget для role-agent, Sol,
   full suite и compaction.
2. Критичный ticket по умолчанию выбирает Terra `high`; Sol `high` требует
   измеримого недостатка Terra или design-adjudication.
3. При исчерпании бюджета Controller создаёт checkpoint и просит отдельное
   разрешение вместо автоматического нового spawn.
4. Компактация перед дорогой ролью создаёт нового Controller.
5. Каждый full suite имеет единственную evidence-запись с командой, временем,
   exit code и test counts.

## GREEN версии 1.3

Свежий агент с обновлённым skill не создал role-agent и вернул
`PREFLIGHT_REPORT`: critical budget `role-agent 0/4`, максимум один full suite,
маршрутизацию Reviewer Terra `high` и Verifier Luna/Terra `medium`. Из-за
отсутствия ticket, spec, checkpoint, baseline и counters он остановился с
`NEEDS_CLARIFICATION`/`BLOCKED_FOR_DESIGN`, а не сформировал новый repair-loop.

Все критерии формы 1.3 выполнены. Это проверяет дисциплину preflight, но не
заменяет следующий реальный ticket как проверку фактического расхода.

## RED/GREEN: переименование skill

RED: проверка по репозиторию нашла 18 ссылок на прежнее имя, включая
runtime-каталог, frontmatter, prompts и GitHub Actions. Это означало, что
пользователь не мог бы надёжно вызвать новое имя.

GREEN: каталог, frontmatter, prompts, инструкции и GitHub Actions переведены
на `finish-ticket`; поиск прежнего имени не вернул результатов. Свежий агент
по запросу `$finish-ticket` прочитал `references/task-lifecycle.md` и выдал
полный `PREFLIGHT_REPORT` до role-agent spawn.

## RED версии 1.4: частичный PASS открыл verification

Наблюдаемый pressure scenario показал:

- критичный ticket был resumed после checkpoint;
- release matrix не содержала обязательный negative-control, то есть один
  criterion оставался `open`;
- Reviewer подтвердил только узкий repair, а Controller назвал это PASS и
  запустил Verifier;
- первый Sandbox job был отклонён worker-ом из-за лишнего свойства до запуска
  `dotnet`, после чего был запрошен новый Verifier slot;
- внешний runner до Controller создал множество test jobs, включая full suite.

Это подтверждает два form failure: частичный review не был структурно отделён
от полного PASS ticket, а текстовая инструкция не ограничивает side effects
runner без технической границы.

## GREEN-критерии версии 1.4

В pressure scenario Controller обязан:

1. показать acceptance ledger всех criteria;
2. вернуть `ACCEPTANCE_INCOMPLETE`, не создавая Verifier или full suite, пока
   negative-control имеет статус `open`;
3. при расширении budget показать `NEXT_CLOSURE` с одним criterion и его
   red-capable loop, не сбрасывая counters;
4. предоставить внешнему runner только изолированную worktree без UI/Sandbox
   queue; без enforcement его job не является evidence;
5. при `JOB_REJECTED` до целевой команды использовать follow-up того же
   Verifier, а не новый role-agent slot.

## GREEN версии 1.4

Свежий независимый Luna `medium` получил только runtime-протокол и тот же
pressure scenario. Он вернул `ACCEPTANCE_INCOMPLETE`, не допустил Verifier или
full suite, потребовал `NEXT_CLOSURE` без сброса counters, изолировал Qwen от
queue и назначил `JOB_REJECTED` follow-up того же Verifier. Все пять критериев
формы выполнены.

Это проверяет решения Controller; техническое enforcement Sandbox queue
отдельно подтверждается на следующем реальном ticket.
