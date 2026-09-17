# Semantic diff gate

До дорогой verification Controller объявляет каждый production semantic delta как contract. Для такого contract обязательны owner, allowed и forbidden transitions, production consumer evidence и regression evidence.

`production_semantic_delta=true` нельзя пометить `test-only`. Отсутствие любого доказательства возвращает `SEMANTIC_DIFF_BLOCKED`; только полный набор даёт `SEMANTIC_DIFF_READY`. Gate валидирует декларацию, не читает Git diff, не запускает verification и не расширяет acceptance surface.