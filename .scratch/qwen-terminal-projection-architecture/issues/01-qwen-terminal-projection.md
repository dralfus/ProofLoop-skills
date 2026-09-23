# 01 — QwenTerminalProjection: единая terminal JSON projection

**What to build:** Все bounded Qwen terminal-producing paths одинаково классифицируют terminal JSON, structured-output failure и error envelope в raw-free decision, не раскрывая transcript или secrets.

**Blocked by:** None — can start immediately

**Status:** complete; committed in `4751c04` (`feat(qwen): unify bounded runtime contracts`)

- [x] Единственный pure-интерфейс принимает наблюдённые stdout/stderr и возвращает raw-free failure projection или terminal structured result.
- [x] Recon, capture и assist adapters используют одну семантику для success, structured-output missing и auth/forbidden failures; protocol сохраняет намеренно silent output contract.
- [x] Fixture matrix доказывает fail-closed поведение и отсутствие raw message в projection.
