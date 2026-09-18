# Raw-free PASS projection

PASS projection связывает candidate identity, execution channel и artifact reference с criterion counts, required controls и evidence status. Она не содержит prompt, secret, path, raw command output, exception text или customer data.

Только полная projection с `passed == total` возвращает `PASS_PROJECTION_READY`; иначе `PASS_PROJECTION_BLOCKED`. Verifier может опираться на projection без ручного чтения assertion source.
Запрещённые raw fields проверяются рекурсивно во всех вложенных objects и lists.
