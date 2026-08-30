# Метрики здоровья цикла «реализация → проверка»

Дата исследования: 2026-08-27
Статус: исследование; этот файл не меняет принятый workflow.

## Вопрос и границы

Нужны измеримые признаки того, что задача проходит путь от реализации к
независимой проверке, а не получает ложный статус DONE. Исследованы только
официальная документация и API GitLab, официальный исходный файл установленного
Superpowers и первичный материал DORA/Google Cloud. Ниже **факты** описывают
существующие возможности источников; раздел «Предложение» — не документированная
возможность GitLab и не принятое решение проекта.

## Подтверждённые факты

### Готовые возможности GitLab

| Возможность | Что именно измеряет | Практическая польза для цикла | Ограничение |
| --- | --- | --- | --- |
| [Value Stream Analytics (VSA)](https://docs.gitlab.com/user/group/value_stream_analytics/) | Длительность стадии равна `end event - start event`; VSA показывает медианный lead time (issue created → closed), cycle time (первое упоминание issue в коммите MR → закрытие issue), новые issues и production deploys. | Базовая картина потока, долгие задачи и узкие места. | Cycle time появится только при `#<issue>` в commit message; это не доказательство независимой проверки. |
| [Настраиваемые стадии VSA](https://docs.gitlab.com/user/group/value_stream_analytics/#stage-measurement) | Стадии можно задать парой предопределённых событий, включая добавление/снятие label у issue или MR. Для label-based stages GitLab поддерживает cumulative duration повторяющихся пар add/remove. | Можно визуализировать время между статусами процесса, в том числе `workflow::blocked`. | VSA не даёт готовых agentic-метрик rework, числа fix-раундов, авторства тестов или причин блокировки; для них нужен собственный ledger и расчёт. |
| [Issue analytics](https://docs.gitlab.com/user/group/issues_analytics/) | Открытые/закрытые issues по месяцам; таблица содержит age, status, iteration, weight, assignee и другие поля; доступны фильтры по label и weight. | Быстрый обзор старых/незакрытых задач и срез по классу задачи. | Это не метрика rework или фактического времени блокировки. |
| [Merge request analytics](https://docs.gitlab.com/user/analytics/merge_request_analytics/) | Количество merged MR и среднее время от создания MR до merge; таблица включает commits, pipelines и line changes. | Диагностика очереди независимого review/merge. | Closed и ещё не merged MR не входят в mean time to merge. |
| [DORA metrics и API](https://docs.gitlab.com/api/dora/metrics/) | API возвращает deployment frequency, lead time for changes, time to restore service и change failure rate с daily/monthly/all интервалом. `lead_time_for_changes` — медиана от merge MR до deploy; CFR — incidents/deployments; TTRS — медиана времени открытого incident. | Результат цикла после поставки: скорость поставки надо смотреть вместе со стабильностью. | Это production-метрики, не счётчик агентских проверок или fix-раундов; API требует Ultimate. |

VSA специально предназначен для поиска bottlenecks и long-running issues/MRs,
а его lifecycle-метрики определены как медианы. [GitLab VSA](https://docs.gitlab.com/user/group/value_stream_analytics/#metrics)
также явно отмечает, что blocked issues по умолчанию в lifecycle overview не
включаются, но их можно отслеживать custom label.

Определения DORA различают «lead time» VSA (создание issue → закрытие) и
«lead time for changes» (merge MR → production); смешивать их нельзя.
[GitLab DORA docs](https://docs.gitlab.com/user/analytics/dora_metrics/#lead-time-for-changes)
Пять? Нет: DORA здесь даёт четыре delivery-сигнала, а не правило числа
попыток. Первичный материал DORA/Google Cloud группирует deployment frequency
и lead time for changes как скорость, а change failure rate и time to restore
service как стабильность. [Google Cloud: Four Keys](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance)

### Сырые события для недостающих метрик

[Resource label events API](https://docs.gitlab.com/api/resource_label_events/)
возвращает для каждого issue/MR добавления и удаления labels с `created_at`.
[Resource state events API](https://docs.gitlab.com/api/resource_state_events/)
возвращает close/reopen events; начальное opened/created состояние он не хранит,
поэтому длительность первоначального открытия надо брать из поля issue `created_at`.

Из этих фактов следует (это **вывод**, а не встроенная метрика GitLab), что
read-only экспорт событий позволяет вычислить без записи в GitLab:

| Производная метрика | Определение для одного issue | Что показывает |
| --- | --- | --- |
| Время блокировки | Сумма интервалов от `add workflow::blocked` до следующего `remove workflow::blocked`; для ещё заблокированной задачи — до момента выгрузки. | Внешние ожидания отдельно от общего lead time. |
| Возвраты/rework | Число пар `reopen` после close плюс число входов обратно в ранее пройденную процессную label-стадию. | Неудачные попытки завершения и нестабильную спецификацию/проверку. |
| Число итераций проверки | Число полных циклов «review verdict с существенным finding → fix → scoped re-review» из лога исполнения. | Насколько реализация сходится к acceptance. |
| Возраст незавершённой задачи | `exported_at - created_at`, с отдельным накопленным blocked time. | Кандидатов на triage, а не причину задержки сам по себе. |

Для корректности каждая смена label должна быть парной и упорядоченной по
`created_at`; непарное удаление или два add подряд — событие качества данных, а
не нулевой интервал. Для выгрузки доступны read-only `GET` endpoints для issues,
label events и state events; API issues также поддерживает выборки по состоянию,
labels и диапазонам обновления. [Issues API](https://docs.gitlab.com/api/issues/)

### Проверка лимита Superpowers: `subagent-driven-development`

Локально установленный файл
`C:\Users\alexey.andreev\.codex\plugins\cache\openai-curated-remote\superpowers\6.3.0\skills\subagent-driven-development\SKILL.md`
содержит лимит **пяти fix-раундов на задачу**. Один раунд — fix-dispatch и
scoped re-review. В rounds 1–3 возобновляется исходный implementer; в rounds
4–5 должен быть новый implementer на более сильной модели. После пятого
неразрешённого re-review новые dispatches прекращаются и findings
адъюдицируются с записью ruling в ledger. [Официальный исходник навыка](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md)

Этот же механизм задаёт критерии немедленной обработки BLOCKED: дополнить
контекст, повысить capability модели, декомпозировать задачу или исправить
план с записанным ruling; он запрещает повторять ту же попытку без изменения.
Реальный load-bearing дефект после breaker не должен молча парковаться: по
локально установленной версии нужно выбрать минимальное решение, а остановиться
только если все дальнейшие пути — догадки. Это является уже существующим
критерием эскалации Superpowers, а не статистическим порогом GitLab.

## Чего готовые средства не дают

В исследованных официальных источниках не найдено готовых GitLab-метрик
`rework`, числа agentic fix-раундов, авторства тестов или универсального
числового порога «остановить цикл». VSA умеет суммировать повторяющиеся
label-интервалы в label-based stage, но этого недостаточно для классификации
причин блокировки, подсчёта fix-раундов и связи findings с действиями агента.
Следовательно, эти показатели нельзя называть «встроенной аналитикой GitLab».

## Предложение для экспериментального workflow (не принято)

Проверить на нескольких реальных задачах минимальный **read-only pilot**, не
меняя GitLab projects, CI, integrations или существующие документы:

1. Вручную вести рядом с каждым task report небольшой ledger с моментами
   `implemented`, `review-start`, каждым `fix round R/5`, `blocked`,
   `unblocked`, `accepted` и ссылкой на evidence. Это дополняет, а не меняет
   требование независимого acceptance из `docs/target-workflow.md`.
2. После пилота выгрузить только GitLab issue/MR и event history, затем
   рассчитать по задачам: lead/cycle/stage time, blocked-time share
   (`blocked_time / age`), rework count, fix-round count, возраст и финальный
   статус. Показать медиану и распределение; не делать выводов по одному
   среднему значению.
3. Временно считать задачей для triage любую, которая: (a) находится в
   `workflow::blocked`, (b) имеет существенный finding после третьего
   fix-раунда, (c) превысила выбранный командой исторический p75 по age или
   blocked time, либо (d) дошла до breaker на round 5. Пункты (b) и (d)
   согласуются с существующей эскалацией Superpowers; p75 — лишь стартовая
   гипотеза, не внешний стандарт.
4. Считать пилот полезным только если он заранее обнаружит хотя бы один
   подтверждённый позже false-completion/blocker и даст объяснимую причину в
   event/ledger evidence. Если пороги дают шум без новых действий, не
   стандартизировать их.

Такой пилот решает конкретный observed failure mode — незаметный переход от
«реализовано» к «якобы завершено» — малым добавлением evidence и измерений, не
подменяя независимую acceptance-роль скоростными метриками.

## Источники

- [GitLab Value Stream Analytics](https://docs.gitlab.com/user/group/value_stream_analytics/)
- [GitLab Issue analytics](https://docs.gitlab.com/user/group/issues_analytics/)
- [GitLab Merge request analytics](https://docs.gitlab.com/user/analytics/merge_request_analytics/)
- [GitLab DORA metrics](https://docs.gitlab.com/user/analytics/dora_metrics/) и [DORA metrics API](https://docs.gitlab.com/api/dora/metrics/)
- [GitLab Resource label events API](https://docs.gitlab.com/api/resource_label_events/) и [Resource state events API](https://docs.gitlab.com/api/resource_state_events/)
- [Google Cloud / DORA Four Keys](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance)
- [Superpowers: subagent-driven-development source](https://github.com/obra/superpowers/blob/main/skills/subagent-driven-development/SKILL.md)
