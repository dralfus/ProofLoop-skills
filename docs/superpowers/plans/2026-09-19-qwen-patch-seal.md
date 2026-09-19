# QWEN_PATCH_SEAL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-use read-only Qwen seal stage that converts a bounded,
observed unsealed candidate into a Qwen-issued, exactly matched patch manifest.

**Architecture:** `scripts/qwen_assist.py` owns validation of the raw-free
`PATCH_SEAL_RECEIPT` and its exact comparison to Qwen's existing patch-schema
output. The PowerShell wrapper exposes `seal` as a local mode but maps it to
Qwen CLI `plan`, with read-only exclusions. Documentation makes seal terminal,
non-transferable by itself, and distinct from a yolo retry.

**Tech Stack:** Python standard library, Python `unittest`, PowerShell 7,
JSON Schema, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-19-qwen-patch-seal-design.md`

## Global Constraints

- Qwen remains an external bounded worker; it receives no acceptance authority.
- The ticket-wide cap remains seven Qwen calls; seal consumes one call.
- Seal is available once only after `STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT`.
- Seal always uses Qwen CLI `plan`, `--bare`, no `--safe-mode`, patch schema
  and read-only exclusions (`Agent,edit,notebook_edit,run_shell_command`).
- Controller may validate and compare receipts but may not synthesize a manifest.
- Seal cannot transfer, commit, merge, cherry-pick, push, use network/MCP,
  create subagents or run a full suite.
- Full receipts and terminal capture stay in local AppData; Git/docs/metrics are
  raw-free and contain neither token, prompt, source text nor transcript.

## Review Focus

- A forged receipt with a nonzero targeted exit code must be rejected before Qwen starts.
- A receipt with three files, 201 lines, nonempty Git operations or a full-suite flag must be rejected.
- A seal request after any yolo reason other than the missing-structured-output turn-limit reason must be rejected.
- A schema-valid Qwen manifest with a different file, line count or test command must not be sealed.
- `seal` must never reach Qwen CLI as an approval mode; the child command must contain `plan` and the read-only exclusions.

---

### Task 1: Python seal receipt and manifest gates

**Files:**

- Modify: `scripts/qwen_assist.py`
- Modify: `tests/test_qwen_assist.py`

**Interfaces:**

- Produces `validate_patch_seal_receipt(receipt: object) -> dict[str, object]`.
- Produces `validate_patch_seal_manifest(receipt: object, manifest: object) -> dict[str, object]`.
- `PATCH_SEAL_RECEIPT` has exactly: `baseline`, `files`, `changed_lines`,
  `targeted_tests`, `targeted_exit_code`, `git_operations`, `full_suite` and
  `yolo_reason`. The required yolo reason is
  `STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT`; targeted exit code is `0`.
- A successful exact comparison returns `{"status": "SEALED_CANDIDATE"}`;
  every rejection returns `{"status": "QWEN_UNUSABLE", "reason": "..."}`.

- [ ] **Step 1: Write failing unit tests for a valid receipt and exact manifest.**

  Add helpers in `QwenAssistTest`:

  ```python
  def patch_seal_receipt(self) -> dict[str, object]:
      return {
          "baseline": "abc123",
          "files": ["scripts/qwen_assist.py"],
          "changed_lines": 12,
          "targeted_tests": ["python -m unittest tests.test_qwen_assist.QwenAssistTest.test_patch_seal"],
          "targeted_exit_code": 0,
          "git_operations": [],
          "full_suite": False,
          "yolo_reason": "STRUCTURED_OUTPUT_MISSING_AT_TURN_LIMIT",
      }
  ```

  Assert that the valid receipt is accepted and that the matching existing
  patch candidate (with `successful_recon: True`) returns `SEALED_CANDIDATE`.

- [ ] **Step 2: Run the new unit test and verify RED.**

  Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest.test_patch_seal_accepts_exact_observed_manifest`

  Expected: FAIL because `validate_patch_seal_receipt` and
  `validate_patch_seal_manifest` do not yet exist.

- [ ] **Step 3: Add the minimal receipt validator and exact-match validator.**

  Add the two functions after `validate_patch_candidate`. Reuse
  `validate_patch_candidate` for manifest bounds, then compare `files`,
  `changed_lines`, `targeted_tests`, `git_operations` and `full_suite` with
  exact equality. Reject malformed fields as `MALFORMED_PATCH_SEAL_RECEIPT`,
  nonzero test exit as `TARGETED_TEST_NOT_GREEN`, a wrong yolo reason as
  `PATCH_SEAL_NOT_ELIGIBLE`, and mismatches as `PATCH_SEAL_MANIFEST_MISMATCH`.

- [ ] **Step 4: Run the focused test and verify GREEN.**

  Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest.test_patch_seal_accepts_exact_observed_manifest`

  Expected: PASS.

- [ ] **Step 5: Add RED tests for every Review Focus receipt/manifest failure.**

  Add one focused test each for nonzero exit, excessive scope/Git/full-suite,
  wrong yolo reason, and each exact-match mismatch (file, line count, test).

- [ ] **Step 6: Run the focused test class and verify GREEN.**

  Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest`

  Expected: all `QwenAssistTest` tests pass.

- [ ] **Step 7: Commit the Python gate.**

  ```powershell
  git add scripts/qwen_assist.py tests/test_qwen_assist.py
  git commit -m "Add Qwen patch seal receipt gate"
  ```

### Task 2: Explicit PowerShell seal mode

**Files:**

- Modify: `scripts/invoke_qwen_assist.ps1`
- Modify: `scripts/start_qwen_assist_capture.ps1`
- Modify: `tests/test_qwen_assist.py`
- Modify: `tests/test_qwen_credential.py`

**Interfaces:**

- Adds local `ApprovalMode = seal`; it is never sent as a Qwen CLI value.
- Adds mandatory `PatchSealReceiptPath` for seal.
- For seal, Qwen child argv contains `--approval-mode plan`, the patch schema,
  `--bare`, and `Agent,edit,notebook_edit,run_shell_command`.

- [ ] **Step 1: Write failing static tests for seal mode.**

  Assert in `test_qwen_assist.py` that the wrapper supports local `seal`, maps
  it to a distinct effective CLI approval variable with `plan`, validates a
  `PatchSealReceiptPath` through the Python receipt action, and uses the patch
  schema. Assert in `test_qwen_credential.py` that capture forwards the receipt
  path and supports `ValidateSet('plan', 'yolo', 'seal')`.

- [ ] **Step 2: Run the two new tests and verify RED.**

  Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest.test_powershell_wrapper_seal_is_read_only tests.test_qwen_credential.QwenCredentialTest.test_capture_runner_forwards_patch_seal_receipt`

  Expected: FAIL because `seal` and `PatchSealReceiptPath` are absent.

- [ ] **Step 3: Implement the minimal local seal mapping.**

  Expand local validation sets to include `seal`. Require an existing
  `PatchSealReceiptPath`, a patch-schema filename, `-SuccessfulRecon`, matching
  `-Baseline`, and a schema-valid recon. Invoke
  `python qwen_assist.py --validate-patch-seal-receipt <raw receipt>` before
  launching Qwen. Set `$effectiveApprovalMode = 'plan'` only for `seal`; keep
  current `plan` and `yolo` behavior unchanged. Extend the capture wrapper to
  pass `PatchSealReceiptPath` through its encoded child command without reading
  a credential itself.

- [ ] **Step 4: Run the new tests and verify GREEN.**

  Run: `python -m unittest tests.test_qwen_assist.QwenAssistTest.test_powershell_wrapper_seal_is_read_only tests.test_qwen_credential.QwenCredentialTest.test_capture_runner_forwards_patch_seal_receipt`

  Expected: PASS.

- [ ] **Step 5: Parse the two PowerShell scripts.**

  Run: `pwsh -NoProfile -Command "$null = [scriptblock]::Create((Get-Content scripts/invoke_qwen_assist.ps1 -Raw)); $null = [scriptblock]::Create((Get-Content scripts/start_qwen_assist_capture.ps1 -Raw))"`

  Expected: exit code 0.

- [ ] **Step 6: Commit the wrapper gate.**

  ```powershell
  git add scripts/invoke_qwen_assist.ps1 scripts/start_qwen_assist_capture.ps1 tests/test_qwen_assist.py tests/test_qwen_credential.py
  git commit -m "Add read-only Qwen patch seal mode"
  ```

### Task 3: Canonical protocol and delivery documentation

**Files:**

- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/references/task-lifecycle.md`
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/references/qwen-assist.md`
- Modify: `plugins/agentic-development-workflow/skills/finish-ticket/SKILL.md`
- Modify: `docs/codex-task-lifecycle.md`
- Modify: `docs/decisions.md`
- Modify: `tickets.md`

**Interfaces:**

- Adds decision D027, `PATCH_SEAL_RECEIPT`, `SEALED_CANDIDATE`, and terminal
  `QWEN_UNUSABLE` semantics.
- The canonical lifecycle remains the source of truth; plugin and human docs
  link to the same restrictions without granting acceptance authority.

- [ ] **Step 1: Add documentation-contract tests before documentation changes.**

  Add static assertions that canonical reference names `QWEN_PATCH_SEAL`,
  `PATCH_SEAL_RECEIPT`, `SEALED_CANDIDATE`, the one-call cap, and the explicit
  no-transfer/no-retry stop gate. Assert `qwen-assist.md` and the human lifecycle
  identify `plan` as the effective Qwen mode for seal.

- [ ] **Step 2: Run the documentation-contract tests and verify RED.**

  Run: `python -m unittest tests.test_qwen_credential.QwenCredentialTest.test_patch_seal_documentation_contract`

  Expected: FAIL because D027 and seal terminology do not yet exist.

- [ ] **Step 3: Update canonical and human documents consistently.**

  Add D027 with the observed failure, why the existing yolo-only contract did
  not handle it, the minimal seal decision, and the measurable criterion: one
  schema-valid Qwen seal exactly matching an observed receipt. In canonical
  lifecycle describe seal after a missing-manifest yolo result, before review;
  forbid transfer after a seal mismatch or absence. Mirror the same authority
  and stop-gate boundaries in qwen-assist reference, plugin entrypoint, human
  lifecycle and Ticket 5.

- [ ] **Step 4: Run the documentation-contract test and verify GREEN.**

  Run: `python -m unittest tests.test_qwen_credential.QwenCredentialTest.test_patch_seal_documentation_contract`

  Expected: PASS.

- [ ] **Step 5: Commit protocol and documentation.**

  ```powershell
  git add plugins/agentic-development-workflow/skills/finish-ticket docs/codex-task-lifecycle.md docs/decisions.md tickets.md tests/test_qwen_credential.py
  git commit -m "Document Qwen patch seal protocol"
  ```

### Task 4: Controlled end-to-end seal smoke

**Files:**

- Create: `docs/experiments/qwen-assist-patch-seal-smoke-<date>.md`
- Modify: `tickets.md`

**Interfaces:**

- Consumes a fresh schema-valid recon, an unsealed bounded yolo diff and a
  Controller-produced `PATCH_SEAL_RECEIPT` stored only in local capture.
- Produces raw-free experiment evidence; never a Ticket 314 acceptance verdict.

- [ ] **Step 1: Preflight one disposable worktree and local receipt path.**

  Verify `qwen --help` capabilities, current baseline, Generic Credential
  availability without printing it, and an initially clean worktree. Define
  one test-only candidate task with one file and one targeted command.

- [ ] **Step 2: Run a single bounded yolo candidate attempt.**

  Use the existing capture wrapper, patch schema, `--bare`, no `--safe-mode`,
  isolated `qwen-patch-*` worktree, and no Git/full-suite/acceptance prompt.
  If it returns a normal manifest, follow the existing candidate path and do
  not run seal. If it returns the exact missing-manifest turn-limit failure,
  continue only to Step 3.

- [ ] **Step 3: Independently create and validate the raw-free receipt.**

  Record only baseline, changed files/count, one targeted command/exit 0,
  empty Git operations, `full_suite: false` and the exact yolo reason in local
  AppData. Run `validate_patch_seal_receipt`; do not transfer the diff.

- [ ] **Step 4: Run exactly one Qwen seal attempt.**

  Invoke local `seal` mode with the existing patch schema and receipt. Parse
  only final `result.structured_result`; run
  `validate_patch_seal_manifest` against the observed receipt. Any missing or
  mismatched output is terminal `QWEN_UNUSABLE` with no retry.

- [ ] **Step 5: Verify and record the result.**

  For `SEALED_CANDIDATE`, independently recheck diff scope and targeted test,
  then record that only independent review could open transfer. For failure,
  record the terminal reason. In both outcomes remove disposable worktrees and
  branches, preserve capture only in AppData, write raw-free experiment evidence
  and update Ticket 5.

- [ ] **Step 6: Run the full repository test suite and final checks.**

  Run: `python -m unittest discover -s tests`

  Expected: all tests pass.

  Run: `git diff --check`

  Expected: no whitespace errors.

- [ ] **Step 7: Commit evidence only after all prior checks are observed.**

  ```powershell
  git add docs/experiments/qwen-assist-patch-seal-smoke-<date>.md tickets.md
  git commit -m "Record Qwen patch seal smoke"
  ```

## Plan self-review

- Spec coverage: Tasks 1–2 enforce receipt/mode boundaries; Task 3 keeps all
  protocol surfaces consistent; Task 4 supplies the required isolated proof.
- Placeholders: no implementation decision is deferred; each task defines its
  interfaces, exact tests, expected RED/GREEN result and commit boundary.
- Type consistency: both Python validators and PowerShell parameter use the
  exact names `PATCH_SEAL_RECEIPT`, `PatchSealReceiptPath`, `seal` and
  `SEALED_CANDIDATE` throughout.
- Review focus: all five listed failure classes are assigned to Tasks 1 or 2;
  Task 4 verifies runtime behavior separately from static tests.
