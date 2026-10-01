# Оценка MindiveLabs skill-doctor

Дата проверки: 2026-09-09.

## Что это делает

`skill-doctor` — plugin/skill для **Claude Code**, а не для Codex. Он
инвентаризирует Claude-skills из `~/.claude/skills`, `.claude/skills` и
additional directories из Claude settings, затем выдаёт Markdown-отчёт о
конфликтах инструкций.

Статический scanner детерминированно ищет только три класса: одинаковое имя
skill (name shadow), совпадение извлечённых путей состояния и пару skills с
`disable-model-invocation: true`. Остальные четыре заявленных класса
(коллизия triggers, semantic overlap, proactive race, subsumption) выполняются
семантическим анализом моделью по summary/trigger metadata. Его результат
эвристический, а не воспроизводимый тест.

## Применимость к ProofLoop

Инструмент не измеряет качество реализации ticket: он не читает diff, не
запускает тесты, не проверяет acceptance criteria, не сравнивает evidence и
не считает токены. Поэтому его нельзя использовать как acceptance authority
или как доказательство `DONE`.

Он полезен только как preflight-аудит набора skills. Для этого проекта он мог
бы обнаружить риск, когда несколько skills одновременно претендуют на
оркестрацию, TDD, debugging или review. Наблюдаемый пример риска: параллельные
инструкции о создании subagents и о собственном repair-loop порождают лишние
роли и расход бюджета.

## Почему не устанавливать напрямую

Текущая реализация жёстко привязана к Claude Code: Bash, пути `~/.claude/*`,
Claude plugin hooks и Claude settings schema. Установка в Codex не даст
достоверного inventory и добавит внешние hooks. Также первый запуск/режим
plugin регистрирует advisory hooks, а `--fix` может перемещать skills в trash;
это не требуется для read-only оценки.

## Рекомендуемый безопасный эксперимент

Не устанавливать `skill-doctor`. Перенести в ProofLoop только его
детерминированную идею как новый **read-only** validator, но после отдельного
согласования:

1. Сканировать только явный inventory Codex skills/plugin skills, без hooks и
   без model-based semantic verdict.
2. Проверять exact duplicate name, пересечение declared triggers и правила,
   способные создать role-agent или запись в один state/evidence path.
3. Выдавать JSON/Markdown как advisory `SKILL_CONFLICT_REPORT`; ничего не
   удалять и не изменять автоматически.
4. Добавить отдельные измеримые критерии качества ticket в ProofLoop:
   время до первого focused RED/GREEN, число role-agent, число test jobs,
   повторные primary causes, terminal reason и независимый acceptance verdict.

Следующее решение: сначала провести ручной inventory текущего набора skills и
проверить, есть ли реальные trigger/role collisions. Только если найдутся
измеримые конфликты, проектировать минимальный Codex-native validator.

## Первичные источники

- [README проекта](https://github.com/MindiveLabs/skill-doctor/blob/main/README.md)
- [SKILL.md: discovery, semantic analysis, отчёт и hooks](https://github.com/MindiveLabs/skill-doctor/blob/main/skills/skill-doctor/SKILL.md)
- [Статический scanner](https://github.com/MindiveLabs/skill-doctor/blob/main/skills/skill-doctor/bin/skill-doctor-scan)
- [Setup script](https://github.com/MindiveLabs/skill-doctor/blob/main/setup)
