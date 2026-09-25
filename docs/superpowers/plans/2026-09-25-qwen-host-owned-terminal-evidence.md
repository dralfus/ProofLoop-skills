# Qwen Host-Owned Terminal Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Добавить settings-neutral host receipt для budget-stop/loop evidence native Qwen и разрешать continuation только при доказанном terminal source, полном event stream и checkpoint policy `READY`.

**Architecture:** Новый pure Python projector классифицирует raw Qwen JSONL и host process observation в один raw-free receipt. Отдельный PowerShell supervisor владеет child process, наблюдает JSONL во время работы и фиксирует собственный stop; существующие runtime adapter и lifecycle policy остаются единственной authority для continuation. Host stop и `HOST_CLEAR` не выдаются за native Qwen signals.

**Tech Stack:** PowerShell/.NET process control, Python standard library, `unittest`, existing Qwen JSONL `--json-file` path, existing plugin validator.

**Spec:** `docs/superpowers/specs/2026-09-25-qwen-host-owned-terminal-evidence-design.md` (одобрено владельцем 2026-09-25); принятое решение — D051 в `docs/decisions.md`.

## Global Constraints

- Сохраняются текущие Qwen protocol argv ceilings: `20 turns / 20 tool calls / 30m / depth 1`.
- Не меняются Qwen settings, provider, credentials, sampling, reasoning, role profile или loop-detection configuration.
- `HOST_CLEAR` — только отсутствие заданного versioned host pattern на полном потоке; это не `NATIVE_CLEAR` и не утверждение об отсутствии любых возможных циклов.
- `NORMAL_EXIT`, `PROCESS_FAILURE`, `USER_INTERRUPT`, `UNKNOWN`, `INCOMPLETE` и `DETECTED` никогда не открывают budget continuation.
- `session_end`, exit code, counters и финальный текст сами по себе не являются budget-stop reason.
- Raw event JSONL, tool payloads, stdout/stderr, prompt, absolute paths, credentials и exceptions не попадают в постоянный receipt или обычный output.
- При гонке host stop с native completion, неизвестной схеме, потере события, неполном файле или неполном receipt результат fail-closed; повторный запуск не делается.
- `recon`, `QWEN_ASSIST`, seal, Codex routing и acceptance authority остаются без изменений.
- Реализация выполняется в существующем рабочем дереве по прямой инструкции владельца: необходимые adapter/checkpoint-файлы отсутствуют в `HEAD` и уже изменены/созданы в незакоммиченном состоянии. Существующие изменения не переносятся, не очищаются и не staged; каждое изменение ограничивается файлами этого плана. Commit/push не входят в scope.
- Ни одна задача этого implementation plan не запускает Qwen-модель. Ticket 24 live pilot остаётся отдельным gate после локальной реализации и проверки.

## Review Focus

1. Qwen штатно завершился в тот же момент, когда host увидел ceiling: только наблюдённая host stop action до process exit может дать `HOST_*_LIMIT`; иначе требуется `UNKNOWN`/`NORMAL_EXIT` и ноль continuation. Проверить Task 2.
2. Усечение sidecar, незакрытая запись, неизвестная schema либо несовпадение session ID не дают `event_coverage=COMPLETE` или `HOST_CLEAR`. Проверить Tasks 1–3.
3. Три вызова с одинаковыми `{name,input}` сами по себе не доказывают loop: это обычный повторный `read_file`, `git status` или другой read-only check. Проверить Task 1 на одинаковых actions с изменившимся результатом и с одинаковым результатом, но изменившимся текстом assistant. Detector анализирует только полные tool-interaction cycles; не останавливает процесс и не изменяет сообщения.
4. Изменение способа запуска `.cmd` может менять quoting, stdin/stdout/stderr redirection, console/TTY, credential inheritance или tree termination. Supervisor читает только JSONL sidecar; если нельзя доказать сохранение текущей stream/console семантики, source unsupported. Проверить Task 2 и Task 4 fake-child tests; несовместимость не обходить переходом в headless mode.
5. Секреты/raw output могут попасть в PowerShell error stream либо дочерний Python projection при аварийном завершении. Проверить Task 4 leak assertions и `finally` cleanup.

---

### Task 1: Pure host terminal receipt projector and loop detector

**Files:**
- Create: `scripts/qwen_terminal_evidence.py`
- Create: `tests/test_qwen_terminal_evidence.py`
- Modify: `scripts/qwen_runtime_adapter.py:project_qwen_events`
- Test: `tests/test_qwen_runtime_adapter.py`

**Interfaces:**
- `project_terminal_receipt(event_jsonl: str, process_observation: object, *, expected_launch_id: str) -> dict[str, object]`
- `process_observation` is an exact-key object: `launch_id`, `child_started`, `process_exited`, `process_exit_code`, `host_stop_reason`, `host_stop_requested`, `stop_observed_while_running`, `session_end_seen_before_stop`, `event_file_bytes_at_stop`, `event_file_closed`, `elapsed_ms`. `event_file_bytes_at_stop` is `null` unless the supervisor recorded a host-stop intent; otherwise it is the byte size sampled after the final live-process check and immediately before sending the graceful interrupt. It must be a complete JSONL-line boundary.
- `host_stop_reason` is `HOST_WALL_LIMIT`, `HOST_TOOL_LIMIT`, or `None`. Loop detection is projection-only and cannot issue a process stop. Booleans must be literal JSON booleans; exit code and elapsed time must be bounded integers.
- Receipt fields: `schema_version`, `status`, fixed `reason`, `launch_id`, hashed `session_id_hash`, `terminal_reason`, `terminal_source`, `process_exit_code`, `event_coverage`, `turns`, `tool_calls`, `wall_time_seconds`, `loop_status`, `loop_detector_version`, and `budget_stop`.
- `loop_detector_version` for this plan is `exact_tool_interaction_cycle_v1`. A cycle is one completed assistant message with one or more ordered `tool_use` blocks followed by matching `user` `tool_result` blocks. Its in-memory fingerprint includes normalized assistant content, each tool name/input, and each matched result content/`is_error`, with unique message/tool IDs excluded. Three adjacent identical completed cycle fingerprints mean `DETECTED`; repeated `{name,input}` alone never does. Different result, assistant content, action order, or input resets the run. Malformed, missing, duplicate, unknown, or possibly truncated cycle data yields `UNKNOWN`. This is a narrow host heuristic, not an intent oracle.
- The loop detector never stops the child. Only a typed host wall/tool ceiling can request process termination; loop status is evaluated from the complete terminal event stream and any `DETECTED` status blocks continuation.
- A host budget terminal is eligible only when the supervisor proves the same launch was started, the stop intent and interrupt were issued while the process was observed running, no `session_end` preceded the intent, a matching `session_end` starts at or after `event_file_bytes_at_stop`, the process tree exited after it, and the event file was closed and fully parsed. The cutoff is sampled before interrupt because a fast graceful response can append `session_end` while a post-interrupt size sample is being taken; using the post-interrupt size would turn that valid response into a partial-line race. A process exit detected on the final pre-signal liveness check clears host-stop attribution. Missing post-stop `session_end`, a child requiring force kill, a partial pre-intent line, or any ordering race yields `INCOMPLETE`/`UNKNOWN` and no continuation.

- [x] **Step 1: Write failing projector tests**

Add tests for `HOST_CLEAR` only on a complete stream; three same `{name,input}` calls with different results → not `DETECTED`; three same calls and same results but different assistant text → not `DETECTED`; three identical complete assistant/tool-result cycles → `DETECTED`; a different input/result/content or a user prompt breaks the sequence; missing tool name/input/result, duplicate IDs, malformed result, unknown block, or possibly truncated result → `UNKNOWN`; normal exit → not a budget stop; host stop with `session_end` before `event_file_bytes_at_stop` → not attributed to host; raw-free output. Use fixture events with a private session id, command, prompt marker, tool output, and secret token.

Example assertion:

```python
receipt = project_terminal_receipt(event_jsonl, process_observation, expected_launch_id="a" * 32)
assert receipt["loop_status"] == "DETECTED"
assert receipt["loop_detector_version"] == "exact_tool_interaction_cycle_v1"
assert "private command" not in json.dumps(receipt)
```

- [x] **Step 2: Run the focused tests and observe the missing-module failure**

Run: `python -m unittest discover -s tests -p test_qwen_terminal_evidence.py -v`
Expected: FAIL because `qwen_terminal_evidence.py` and `project_terminal_receipt` do not exist.

- [x] **Step 3: Implement the minimum pure projection**

Implement strict key/type/identity checks, canonical in-memory completed interaction fingerprints, three-consecutive-cycle detection, event coverage classification, terminal reason/source classification, and the fixed raw-free receipt. Never include event values or exception text in the return object. If a tool-result content value reaches the documented 65,536-byte per-field limit, mark loop status `UNKNOWN` rather than risk comparing equal head/tail previews as full results.

Fingerprint construction hashes the normalized complete interaction, not an isolated action:

```python
canonical = json.dumps(
    {
        "assistant_content": normalized_assistant_blocks,
        "results": [
            {"content": matched_result_content, "is_error": matched_is_error}
            for matched_result_content, matched_is_error in tool_results_in_use_order
        ],
    },
    ensure_ascii=True,
    sort_keys=True,
    separators=(",", ":"),
)
fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Repeated actions with changed assistant text or matched results are ordinary repeated work, not a loop. Two equal completed cycles remain below threshold. Even a three-cycle match is only a terminal `DETECTED` classification: it never signals the live supervisor to interrupt the child; it can only make later continuation ineligible. An intentionally identical three-cycle workflow remains a documented residual false-positive risk.

- [x] **Step 4: Run the focused tests and then the adapter tests**

Run: `python -m unittest discover -s tests -p test_qwen_terminal_evidence.py -v`
Expected: PASS for all terminal/coverage/detector/raw-free cases.

Run: `python -m unittest discover -s tests -p test_qwen_runtime_adapter.py -v`
Expected: PASS; legacy projection remains fail-closed and only the new explicit host observation can create host terminal evidence.

### Task 2: Supervise the protocol child and prove host stop ownership with fake processes

**Files:**
- Create: `scripts/qwen_protocol_supervisor.ps1`
- Create: `tests/test_qwen_protocol_supervisor.py`
- Test: `scripts/invoke_qwen_finish_ticket_cli.ps1`

**Interface:**

```powershell
function Invoke-QwenProtocolChild {
    param(
        [string]$QwenCommand,
        [string[]]$QwenArguments,
        [string]$EventFilePath,
        [string]$LaunchId,
        [int]$MaxToolCalls,
        [int]$MaxWallTimeSeconds
    )
    # Returns only: qwen_exit_code, process_observation
}
```

`process_observation` uses exactly the keys in Task 1. The supervisor polls complete JSONL lines while the child is alive; `MaxToolCalls` and `MaxWallTimeSeconds` initially mirror the existing protocol contract (`20` and `1800`) without changing Qwen argv. Tool ceiling counts completed `tool_use`/matching `tool_result` pairs; stop is requested only after that completed-pair threshold while the process is still running. The loop detector never stops a process. If the child exited before a budget stop, a stop is never attributed to the host.

- [x] **Step 1: Add fake-child integration tests**

Add fake direct-child cases to `tests/test_qwen_protocol_supervisor.py`: a child that writes session-start/tool-use/tool-result JSONL then waits and emits matching session-end on graceful process-group interrupt; a child that exits normally before a threshold; a child that exits exactly at a threshold; a child that ignores graceful interrupt; and a child that leaves a partial final JSONL line. Add a recognized `qwen.cmd` Node-shim fixture whose fake JS entrypoint records argv, plus an unknown `.cmd` fixture with a marker side effect. Assert tool stop occurs after the matching result, loop classification alone never stops the child, session-end ordering, process-tree exit, `event_file_closed`, exact prompt argument preservation (including newlines and shell metacharacters), no execution of unknown wrappers, and no raw text in parent stdout/stderr.

- [x] **Step 2: Run fake-child tests before adding the supervisor**

Run: `python -m unittest discover -s tests -p test_qwen_runtime_guard.py -v`
Expected: FAIL because protocol still invokes Qwen synchronously and has no host stop observation.

- [x] **Step 3: Implement a single-process monitor with exact process ownership**

Use the existing native CreateProcess/Job Object child handle, a monotonic Stopwatch, and a tail parser that consumes only complete JSONL lines. The supervisor may observe the event sidecar only: it must not capture or asynchronously drain stdout/stderr, and must preserve the current launcher's stdin/stdout/stderr redirection and console/TTY behavior exactly. Fake-child tests cover inherited handles and process-tree ownership. `.ps1` and `.exe` launch directly. For `.cmd`, recognize only the observed fixed Qwen npm-style Node shim shape and fixed `node_modules\\@qwen-code\\qwen-code\\cli-entry.js` entrypoint; run `node.exe` directly with that entrypoint followed by original argv. Accept the shim only if its complete structure matches, the entrypoint exists, and its bundled Node or PATH-resolved `node.exe` exists. Unknown/future `.cmd` wrappers fail closed before child creation; never fall back to `cmd.exe`, PowerShell shell invocation, or environment-based argument transport. Poll at `100 ms`; on `MaxToolCalls` completed tool pairs or wall threshold, require `HasExited -eq $false`, record stop intent, send a graceful interrupt to an isolated child process group, and wait for a matching `session_end`, all descendants' exits, and event-writer closure. If graceful shutdown is not acknowledged within `5 s`, force tree termination and set event coverage `INCOMPLETE` so no host receipt can be `READY`.

The direct Node adapter must prove prompt/argv preservation with quotes, `%PATH%`, `^`, `|`, `!`, and newline; the protocol capability `--help` preflight and child launch must both use the adapter, and an unknown `.cmd` must not execute at either stage. Keep the existing protocol argv and do not switch to `-p`/headless.

- [x] **Step 4: Run fake-child cases including the completion race**

Run: `python -m unittest discover -s tests -p test_qwen_runtime_guard.py -v`
Expected: PASS; only a stop request observed before child exit may produce a `HOST_*_LIMIT`. Normal exit and race outcomes must not be budget continuation evidence.

### Task 3: Bind terminal receipt to checkpoint continuation policy

**Files:**
- Modify: `scripts/qwen_runtime_adapter.py:prepare_continuation`
- Modify: `scripts/validate_plugin.py:qwen_runtime_guard_decision` and runtime observation validation
- Modify: `tests/test_qwen_runtime_adapter.py`
- Modify: `tests/test_qwen_runtime_lifecycle.py`
- Test: `tests/test_qwen_guard_policy.py`

**Interfaces:**
- `prepare_continuation` accepts the Task 1 receipt as `prior_projection` and requires exact receipt schema/version.
- Runtime ledger terminal reasons `HOST_WALL_LIMIT` and `HOST_TOOL_LIMIT` are resumable only with `terminal_source=HOST`, `event_coverage=COMPLETE`, `loop_status=HOST_CLEAR`, `budget_stop=true`, matching `launch_id/session_id`, and a valid checkpoint.
- `DETECTED`, `NORMAL_EXIT`, `PROCESS_FAILURE`, `USER_INTERRUPT`, `UNKNOWN`, and `INCOMPLETE` always append a terminal stop or return blocked; none can reach `QWEN_RUNTIME_GUARD_READY`. A loop detector finding is not a process-stop reason.
- Existing loop detection and repeated-fingerprint stops remain terminal. Recon policy remains unchanged.

- [x] **Step 1: Add policy tests for allowed and blocked receipts**

Add tests where a valid `HOST_WALL_LIMIT` + complete `HOST_CLEAR` receipt reaches `READY`; each changed identity/source/version/counter/coverage blocks; `NORMAL_EXIT` cannot resume; any detector `DETECTED` result blocks; loop evidence is never a host process-stop action; and all events/counters remain append-only.

- [x] **Step 2: Run adapter and lifecycle tests before policy edits**

Run: `python -m unittest discover -s tests -p test_qwen_runtime_adapter.py -v`
Expected: FAIL because continuation currently requires legacy `CLEAR` plus native `MAX_*_EXHAUSTED` terminal reasons.

- [x] **Step 3: Extend runtime receipt/ledger validation**

Validate the exact receipt keys and accepted enum pairs before `qwen_runtime_guard_decision`. Bind the host evidence to the preceding runtime observation; do not infer `budget_stop` from counts. Retain checkpoint/worktree/progress/test/review checks unchanged.

- [x] **Step 4: Run focused runtime, lifecycle, and guard tests**

Run: `python -m unittest discover -s tests -p test_qwen_runtime_adapter.py -v`
Expected: PASS.

Run: `python -m unittest discover -s tests -p test_qwen_runtime_lifecycle.py -v`
Expected: PASS, including zero continuation for every non-eligible terminal class.

Run: `python -m unittest discover -s tests -p test_qwen_guard_policy.py -v`
Expected: PASS; pre-dispatch settings/capability policy is unchanged.

### Task 4: Wire the supervisor into protocol mode without changing other modes

**Files:**
- Modify: `scripts/invoke_qwen_finish_ticket_cli.ps1:protocol branch`
- Modify: `scripts/invoke_qwen_finish_ticket.ps1`
- Modify: `tests/test_qwen_runtime_guard.py`
- Preserve unchanged: `scripts/qwen_invocation_contract.py` protocol argv values

- [x] **Step 1: Add parent-launcher tests for host projection and cleanup**

Assert protocol calls the supervisor exactly once, passes the exact current argv limits, provides a matching launch identity, restores process-scoped credential/output-limit environment before Python projection, and deletes both JSONL and process-observation temporary files in `finally` on success, error, timeout, and malformed JSON.

- [x] **Step 2: Run the launcher tests before integration**

Run: `python -m unittest discover -s tests -p test_qwen_runtime_guard.py -v`
Expected: FAIL because the parent still runs `& $QwenCommand` and does not pass process observation to the projector.

- [x] **Step 3: Wire the protocol branch only**

Dot-source `qwen_protocol_supervisor.ps1` and call `Invoke-QwenProtocolChild` only when `$Mode -eq 'protocol'`. Keep recon invocation, Credential Manager target propagation, and env restoration code intact. Write the raw-free process observation to an ephemeral JSON file; call the Python adapter with `--project-events`, `--process-observation-file`, and the same `--launch-id`; remove both temporary files in `finally`.

- [x] **Step 4: Run runtime-guard tests and verify the compatibility command contract**

Run: `python -m unittest discover -s tests -p test_qwen_runtime_guard.py -v`
Expected: PASS; fake Qwen child only, no model request.

Run: `python -m unittest discover -s tests -p test_qwen_invocation_contract.py -v`
Expected: PASS; protocol argv remains exact and recon remains distinct.

### Task 5: Synchronize the accepted target semantics and current blocked status

**Files:**
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`
- Modify: `README.md`
- Modify: `docs/codex-task-lifecycle.md`
- Modify: `docs/current-state.md`
- Modify: `tickets.md`
- Modify: `docs/decisions.md` only if implementation findings require a D051 addendum
- Preserve: `CONTEXT.md` terminology and D051 accepted semantics

- [x] **Step 1: Add documentation assertions before edits**

Extend existing validator/tests so the canonical protocol and user docs agree on these exact invariants: `HOST_CLEAR` is versioned and complete-stream-only; `NORMAL_EXIT` is not a budget terminal; `UNKNOWN` is fail-closed; Ticket 24 remains `BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN` until a separate bounded live pilot succeeds.

- [x] **Step 2: Run documentation/validator tests before edits**

Run: `python -m unittest discover -s tests -p test_validate_plugin.py -v`
Expected: FAIL on the missing D051 synchronization assertions.

- [x] **Step 3: Update canonical protocol first, then human-facing summaries**

Document the host receipt source, the accepted eligible reasons, exact meaning/version of `HOST_CLEAR`, fail-closed cases, unchanged Qwen settings/argv, and the separate live Ticket 24 gate. Do not mark Ticket 24 complete or claim live evidence.

- [x] **Step 4: Run documentation validators**

Run: `python -m unittest discover -s tests -p test_validate_plugin.py -v`
Expected: PASS.

Run: `python scripts/validate_plugin.py`
Expected: exit `0` with no schema or lifecycle errors.

### Task 6: Final local verification and readiness handoff

**Files:** all files listed above.

- [x] **Step 1: Run focused suites**

Run: `python -m unittest discover -s tests -p test_qwen_terminal_evidence.py -v`
Expected: PASS.

Run: `python -m unittest discover -s tests -p test_qwen_runtime_guard.py -v`
Expected: PASS.

Run: `python -m unittest discover -s tests -p test_qwen_runtime_lifecycle.py -v`
Expected: PASS.

- [x] **Step 2: Run the complete local suite and validators**

Run: `python -m unittest discover -s tests`
Expected: exit `0`, zero failures/errors, full discovery count reported.

Run: `python scripts/validate_plugin.py`
Expected: exit `0`.

Run: `git diff --check`
Expected: no whitespace errors in tracked plan implementation changes.

- [x] **Step 3: Confirm the live gate remains separate**

Verify by code and docs that no test invoked Qwen, no external settings changed, and Ticket 24 remains `BLOCKED_EVIDENCE_SOURCE` / `NOT_RUN` until its separately bounded live run has an eligible host receipt. Report exact counters, test totals, terminal taxonomy, and remaining live-gate requirements. Do not commit or push.

---

## Implementation Review Decisions Still Visible to the Owner

- The host detector's narrow rule is three consecutive identical completed interaction-cycle fingerprints, including normalized assistant content and matched tool results. Identical actions alone do not stop the child. Exact repeated successful cycles can still be legitimate in unusual workflows, so the detector is not an intent oracle; it never interrupts a live process, and its residual pattern limitation stays visible in receipt/version/docs. Loops that vary their interaction content may not be detected. `HOST_CLEAR` means only that this versioned pattern was not found in a complete stream.
- Current Qwen CLI limits stay exactly `20/20/30m/depth1`; host stop is accepted only if observed before child exit. Any race is non-resumable, so the effective number of successful continuations can be lower than the numeric ceilings.
- Host process control must keep protocol argv/mode unchanged. If fake-process or later live compatibility evidence shows otherwise, stop and report unsupported; do not fall back to headless mode or alter Qwen settings.

## Execution status (2026-09-25)

Tasks 1–6 are complete for the local, settings-neutral implementation. This
execution-status entry describes the implementation-plan stage, before the
separately authorized bounded Ticket 314 pilot recorded in `docs/current-state.md`.
An outer-launcher regression found that the protocol `--help` capability probe
could still execute an unknown `.cmd` before the supervisor's fail-closed gate.
The preflight now shares the recognized direct-Node adapter; a full-launcher
test asserts rejection before the wrapper marker can be created. Final local
verification totals are recorded in `docs/current-state.md`. At that stage
neither Qwen CLI nor model had been invoked. Ticket 24 remains a separate
native-compatibility gate. No commit or push had been authorized at that stage.
