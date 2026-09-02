# Перенос репозитория на GitHub

## Что уже подготовлено

- plugin находится в `plugins/agentic-development-workflow/`;
- marketplace описан в `.agents/plugins/marketplace.json`;
- plugin `agentic-development-workflow` имеет версию `1.11.0`;
- локальное состояние, временные файлы и старые ZIP исключены из Git;
- GitHub Actions валидирует manifest и обязательные файлы plugin.

## Перед первой публикацией

1. Проверьте, что в документах нет внутренних путей, секретов, токенов,
   customer data или логов с чувствительным содержимым.
2. Лицензия `Unlicense` уже добавлена в `LICENSE`: использовать, изменять,
   распространять и продавать материалы можно без условий и гарантий.
3. GitHub repository уже создан: `https://github.com/dralfus/ProofLoop-skills`.
4. В корне этого проекта выполните команды:

```powershell
git branch -M main
git add .
git commit -m "feat: publish agentic development workflow 1.11"
git remote add origin https://github.com/dralfus/ProofLoop-skills.git
git push -u origin main
```

## Установка на другом ПК

```powershell
git clone https://github.com/dralfus/ProofLoop-skills.git
Set-Location <CLONE_DIRECTORY>
codex plugin marketplace add .
codex plugin add agentic-development-workflow@personal
```

После обновления репозитория повторите последнюю команду и начните новый Codex
task. Для plugin из этого репозитория не требуется ZIP, PowerShell installer
или копирование workflow-файлов в проект разработки.

Для Qwen Code v0.22.2 из того же clone выполните:

```powershell
qwen extensions install .
```

Extension делает `finish-ticket` и `finish-ticket-controller` discoverable,
используя единственный lifecycle из Codex plugin. Запуск: `/finish-ticket
ticket <ID или путь>`. Перед публикацией сверяйте real-pilot evidence с
`docs/experiments/qwen-code-v0222-pilot.md`; `NOT_RUN` не является live run.

## Граница ответственности

Этот репозиторий хранит protocol и plugin. Он не создаёт GitHub repository,
не добавляет remote и не выполняет push автоматически.
