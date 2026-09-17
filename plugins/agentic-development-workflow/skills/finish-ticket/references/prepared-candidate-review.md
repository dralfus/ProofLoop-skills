# Prepared candidate и evidence receipt

Controller формирует **prepared candidate** после локального диагностического RED/GREEN. Это не приёмка и не разрешение на выпуск: цель — передать Reviewer точный candidate delta и не смешивать его с неизменившейся системой.

## Состав candidate

`candidate` обязан содержать opaque `identity`, непустые `scope_delta`, `criteria`, `invariants`, а также `diagnostic_evidence` с одним воспроизводимым `RED` и хотя бы одним `GREEN`. Диагностический evidence **не требует** предварительного static PASS.

`evidence_context` фиксирует `build_configuration`, `execution_configuration` и `required_environment`. Это поля идентичности evidence, а не классификация execution channel и не инструкция его запускать.

## Review и повторное использование evidence

Reviewer должен быть fresh, named, read-only (`read` и `verify`), без fork/write; его verdict обязан быть привязан к `candidate_identity` и содержать `SPEC=PASS`, `CODE_QUALITY=PASS`.

Каждый receipt содержит candidate identity, test id, context, command, executed set и `GREEN` result. Его можно только сравнить с текущим candidate — автоматически повторно использовать или запускать нельзя.

При различии candidate identity, build/execution configuration либо required environment Controller возвращает `EVIDENCE_STALE`; после этого требуется новый review либо новое evidence. При отсутствии корректного свежего review — `REVIEW_REQUIRED`. Лишь точное совпадение даёт `PREPARED_CANDIDATE_READY` с действием `REQUEST_VERIFIER`.