# Discovery и execution receipts

`DISCOVERY_RECEIPT` и `EXECUTION_RECEIPT` — разные доказательства. Первый хранит selector и уникальный discovered set; второй — команду, фактически executed set, `passed/failed/skipped` counts и result.

Controller не делает product verdict из одного exit code. Он сначала сравнивает discovery и execution sets, а также сумму counts с executed set. Расхождение даёт `EVIDENCE_INCOMPLETE/DISCOVERY_EXECUTION_MISMATCH`: нужно выбрать другой evidence seam либо заблокировать ticket, без автоматического retry.

Environment failure до запуска целевой команды даёт `INFRASTRUCTURE_BLOCKER/PRE_COMMAND_ENVIRONMENT_FAILURE`. Валидатор только проверяет receipts: он не запускает команду и не повторяет её.