# Qwen-first Implementation Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Qwen the bounded patch Implementer and prove one disposable end-to-end candidate-to-review path with a manifest-only completion call that permits exactly one structured-output tool call.

**Architecture:** Local `seal` remains the public wrapper mode, but its effective Qwen behavior becomes `QWEN_MANIFEST_ONLY`: it receives only a raw-free receipt, uses `plan` with the single structured-output tool, and returns the existing patch schema. Controller observes diff/test facts independently; the capture reader alone issues `SEALED_CANDIDATE` after exact validation.

**Tech Stack:** Python 3 standard library and `unittest`; PowerShell 7; Qwen CLI; JSON Schema; Markdown.

**Spec:** `docs/superpowers/specs/2026-09-19-qwen-first-implementation-design.md`

## Global Constraints

- Qwen is the bounded Implementer only in an isolated candidate worktree; it has no acceptance, transfer, Git, full-suite, network/MCP or subagent authority.
- `seal` maps to Qwen `plan`, uses `--bare`, never `--safe-mode`, and has `--max-tool-calls 1` for structured output only.
- Receipt baseline equals confirmed recon and current baseline; ticket reservation allows exactly one seal attempt.
- Missing, malformed or mismatching terminal output is `QWEN_UNUSABLE`, with no automatic retry or fallback.
- Live proof is one disposable test-only patch, never Ticket 314 implementation or acceptance.
- Tokens, prompts, source text and raw terminal transcripts remain outside Git and metrics.

## Review Focus

- Seal retaining the write candidate tool budget: Task 2 pins the effective limit to `0`.
- Packet omits receipt or permits code inspection: Task 1 pins exact prompt text.
- Non-final JSON event reaches `SEALED_CANDIDATE`: Task 3 tests capture reader rejection.
- Existing `plan`/`yolo` behavior regresses: Task 2 tests their retained limits.
- Pilot claims success without independent diff, test, exact manifest and review: Task 4 requires all gates.

---

### Task 1: Deterministic manifest-only packet contract

**Files:**
- Modify: `scripts/qwen_assist.py`
- Modify: `tests/test_qwen_assist.py`

**Interfaces:**
- Produces `manifest_only_limits() -> dict[str, object]` with approval `plan`, tool limit `0`, and existing read-only exclusions.
- Produces `build_manifest_only_prompt(prompt: str, receipt: object) -> str`.

- [ ] **Step 1: Write failing tests.**

```python
def test_manifest_only_packet_contains_receipt_and_forbids_code_inspection(self) -> None:
    prompt = QWEN_ASSIST.build_manifest_only_prompt("Return manifest now.", self.patch_seal_receipt())
    self.assertIn("PATCH_SEAL_RECEIPT", prompt)
    self.assertIn('"baseline": "abc123"', prompt)
    self.assertIn("Do not inspect, edit, or run tools", prompt)
    self.assertEqual(QWEN_ASSIST.manifest_only_limits()["max_tool_calls"], 0)

def test_manifest_only_packet_rejects_invalid_receipt(self) -> None:
    with self.assertRaises(ValueError):
        QWEN_ASSIST.build_manifest_only_prompt("Return manifest", {"baseline": "abc123"})
```

- [ ] **Step 2: Verify RED.**

Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest.test_manifest_only_packet_contains_receipt_and_forbids_code_inspection tests.test_qwen_assist.QwenAssistTest.test_manifest_only_packet_rejects_invalid_receipt`

Expected: FAIL because both helpers are absent.

- [ ] **Step 3: Implement the minimal helpers.**

```python
def manifest_only_limits() -> dict[str, object]:
    return {"approval_mode": "plan", "max_tool_calls": 0,
            "excluded_tools": "Agent,edit,notebook_edit,run_shell_command"}

def build_manifest_only_prompt(prompt: str, receipt: object) -> str:
    if validate_patch_seal_receipt(receipt)["status"] != "PATCH_SEAL_RECEIPT_READY":
        raise ValueError("manifest-only requires a ready patch seal receipt")
    return f"{prompt}\nPATCH_SEAL_RECEIPT:\n{json.dumps(receipt, sort_keys=True)}\nDo not inspect, edit, or run tools. Return only the patch manifest."
```

- [ ] **Step 4: Verify GREEN and commit.**

Run the Step 2 command; expected PASS.

```powershell
git add scripts/qwen_assist.py tests/test_qwen_assist.py
git commit -m "Define Qwen manifest-only packet"
```

### Task 2: Enforce zero-tool seal launch without changing recon/yolo

**Files:**
- Modify: `scripts/invoke_qwen_assist.ps1`
- Modify: `scripts/start_qwen_assist_capture.ps1`
- Modify: `scripts/qwen_assist.py`
- Modify: `tests/test_qwen_assist.py`
- Modify: `tests/test_qwen_credential.py`

**Interfaces:**
- Consumes local `ApprovalMode = seal`, receipt, ticket, recon report and baseline.
- Produces `plan`, patch schema, `--max-tool-calls 1`, `--bare` and read-only exclusions; `plan` and `yolo` retain `20`.
- Adds CLI action `--build-manifest-only-prompt` requiring `--prompt` and `--patch-seal-receipt`.

- [ ] **Step 1: Write failing static tests.**

```python
def test_seal_uses_manifest_only_zero_tool_packet(self) -> None:
    wrapper = POWERSHELL_WRAPPER.read_text(encoding="utf-8")
    self.assertIn("$maxToolCalls = if ($ApprovalMode -eq 'seal') { '0' } else { '20' }", wrapper)
    self.assertIn("--build-manifest-only-prompt", wrapper)
    self.assertIn("'--max-tool-calls' $maxToolCalls", wrapper)

def test_capture_runner_keeps_ticket_and_receipt_arguments_quoted(self) -> None:
    runner = CAPTURE_RUNNER.read_text(encoding="utf-8")
    self.assertIn("Quote-PowerShellLiteral", runner)
    self.assertIn("-TicketId $(Quote-PowerShellLiteral $TicketId)", runner)
```

- [ ] **Step 2: Verify RED.**

Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest.test_seal_uses_manifest_only_zero_tool_packet tests.test_qwen_credential.QwenCredentialTest.test_capture_runner_keeps_ticket_and_receipt_arguments_quoted`

Expected: FAIL because seal has tool limit `20`.

- [ ] **Step 3: Implement the smallest wrapper change.**

```powershell
$maxToolCalls = if ($ApprovalMode -eq 'seal') { '0' } else { '20' }
if ($ApprovalMode -eq 'seal') {
    $effectivePrompt = python "$PSScriptRoot\qwen_assist.py" --build-manifest-only-prompt $Prompt --patch-seal-receipt $patchSealReceipt
}
# Qwen argv:
'--max-tool-calls' $maxToolCalls `
'--prompt' $effectivePrompt
```

Keep `Quote-PowerShellLiteral` in the capture runner and do not change plan/yolo limits.

- [ ] **Step 4: Verify GREEN and parse wrappers.**

Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest tests.test_qwen_credential.QwenCredentialTest`

Expected: PASS.

Run: `pwsh -NoProfile -Command "$null = [scriptblock]::Create((Get-Content scripts/invoke_qwen_assist.ps1 -Raw)); $null = [scriptblock]::Create((Get-Content scripts/start_qwen_assist_capture.ps1 -Raw)); $null = [scriptblock]::Create((Get-Content scripts/get_qwen_assist_capture.ps1 -Raw))"`

Expected: exit code `0`.

- [ ] **Step 5: Commit.**

```powershell
git add scripts/invoke_qwen_assist.ps1 scripts/start_qwen_assist_capture.ps1 scripts/qwen_assist.py tests/test_qwen_assist.py tests/test_qwen_credential.py
git commit -m "Run Qwen seal as tool-free manifest lane"
```

### Task 3: Capture-reader terminal-event proof

**Files:**
- Modify: `scripts/get_qwen_assist_capture.ps1`
- Modify: `tests/test_qwen_credential.py`

**Interfaces:**
- Consumes capture stdout and receipt path.
- Produces `SEALED_CANDIDATE` only for final `result.structured_result` exactly matching the receipt; otherwise raw-free `QWEN_UNUSABLE`.

- [ ] **Step 1: Write failing fixture tests.**

```python
def test_capture_reader_rejects_non_final_manifest_event(self) -> None:
    # Temporary stdout.json: [{"type": "message", "structured_result": valid_manifest}].
    # Finished PID plus receipt path must return QWEN_UNUSABLE/MISSING_TERMINAL_PATCH_MANIFEST.

def test_capture_reader_seals_exact_final_manifest(self) -> None:
    # Temporary stdout.json: [{"type": "result", "structured_result": valid_manifest}].
    # Finished PID plus receipt path must return SEALED_CANDIDATE without terminal_output or stderr.
```

- [ ] **Step 2: Verify RED.**

Run: `python -m unittest tests.test_qwen_credential.QwenCredentialTest.test_capture_reader_rejects_non_final_manifest_event tests.test_qwen_credential.QwenCredentialTest.test_capture_reader_seals_exact_final_manifest`

Expected: FAIL until fixture-driven reader behavior exists.

- [ ] **Step 3: Implement tested behavior.**

Require `@($terminalOutput)[-1].type -eq 'result'`; serialize only its
`structured_result` to `qwen_assist.py --validate-patch-seal-manifest`. Return
`SEALED_CANDIDATE` only on validator success; otherwise return raw-free
`QWEN_UNUSABLE` with its reason.

- [ ] **Step 4: Verify GREEN and commit.**

Run the Step 2 command; expected PASS.

```powershell
git add scripts/get_qwen_assist_capture.ps1 tests/test_qwen_credential.py
git commit -m "Verify Qwen manifest-only terminal event"
```

### Task 4: Protocol and one disposable end-to-end proof

**Files:**
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/references/qwen-assist.md`
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/SKILL.md`
- Modify: `docs/codex-task-lifecycle.md`
- Modify: `docs/decisions.md`
- Create: `docs/experiments/qwen-first-manifest-only-smoke-2026-09-19.md`
- Modify: `tickets.md`
- Modify: `tests/test_qwen_credential.py`

**Interfaces:** Documents `QWEN_MANIFEST_ONLY` as effective seal behavior, still without acceptance authority. Records either complete raw-free proof or terminal `QWEN_UNUSABLE`.

- [ ] **Step 1: Write a failing documentation-contract test.**

```python
def test_manifest_only_documentation_contract(self) -> None:
    for document in (CANONICAL_LIFECYCLE, QWEN_REFERENCE, HUMAN_LIFECYCLE):
        content = document.read_text(encoding="utf-8")
        self.assertIn("QWEN_MANIFEST_ONLY", content)
        self.assertIn("--max-tool-calls 1", content)
        self.assertIn("no retry", content.lower())
```

- [ ] **Step 2: Verify RED.**

Run: `python -m unittest tests.test_qwen_credential.QwenCredentialTest.test_manifest_only_documentation_contract`

Expected: FAIL because protocol names only `QWEN_PATCH_SEAL`.

- [ ] **Step 3: Update protocol and D028.**

Document observed seal agent-turn waste, single-structured-output manifest-only decision,
exact terminal-match/no-retry/no-transfer rule, and the disposable evidence
criterion. Do not alter acceptance authority.

- [ ] **Step 4: Verify GREEN.**

Run the Step 2 command; expected PASS.

- [ ] **Step 5: Run one bounded live proof.**

1. Create a clean `qwen-patch-manifest-only-<date>` disposable worktree; verify baseline and Credential Manager availability without printing its secret.
2. Run one schema-valid recon and one Qwen yolo test-only patch attempt.
3. Independently observe scope and run one targeted command.
4. If yolo has no manifest, create a local receipt only for an allowlisted
   reason: `STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT` or the explicitly
   diagnosed host-side `COLLECTOR_PROJECTION_FAILED`. Run exactly one
   single-structured-output seal. Do not retry within one seal identity.
5. Poll capture reader. Only `SEALED_CANDIDATE` opens one fresh read-only review of fixture scope; otherwise record terminal `QWEN_UNUSABLE`.
6. Delete only the named disposable worktree/branch; retain captures only in AppData.

- [ ] **Step 6: Full verification.**

Run: `python -m unittest discover -s tests`

Expected: all tests pass.

Run: `git diff --check`

Expected: no whitespace errors.

- [ ] **Step 7: Commit.**

```powershell
git add plugins/agentic-development-workflow/skills/finish-ticket docs/codex-task-lifecycle.md docs/decisions.md docs/experiments/qwen-first-manifest-only-smoke-2026-09-19.md tickets.md tests/test_qwen_credential.py
git commit -m "Prove Qwen-first manifest-only lane"
```

## Plan self-review

- Spec coverage: Tasks 1–3 implement isolated packet, zero-tool launch and terminal exact-match; Task 4 aligns protocol and executes the single proof.
- Placeholder scan: all functions, inputs, terminal outcomes and commands are named; no deferred behavior remains.
- Type consistency: receipt is `PATCH_SEAL_RECEIPT`; local mode is `seal`; Qwen mode is `plan`; only capture reader returns `SEALED_CANDIDATE`.
- Review focus coverage: zero tools and non-regression (Task 2), prompt contract (Task 1), final event (Task 3), proof completeness (Task 4).
