# Перенос репозитория на GitHub

## Что уже подготовлено

- plugin находится в `plugins/agentic-development-workflow/`;
- marketplace описан в `.agents/plugins/marketplace.json`;
- executable protocol имеет версию `1.7.0`;
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
git commit -m "feat: publish agentic development workflow 1.7"
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

## Граница ответственности

Этот репозиторий хранит protocol и plugin. Он не создаёт GitHub repository,
не добавляет remote и не выполняет push автоматически.
