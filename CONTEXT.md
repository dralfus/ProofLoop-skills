# ProofLoop Qwen Runtime Evidence

This context defines the terms used to reason about native Qwen session outcomes and guarded continuation in ProofLoop.

## Terminal Evidence

**Terminal receipt**:
A raw-free ProofLoop record binding one launch/session identity to its observed termination reason, process outcome, event coverage, counters, and loop assessment.
_Avoid_: Qwen final answer, session transcript

**Terminal reason**:
The evidenced cause by which a native Qwen process/session ended; it is distinct from whether continuation is safe.
_Avoid_: loop status, exit code (as a reason)

**Event coverage**:
The completeness classification for the event stream associated with one launch/session; `UNKNOWN` or `INCOMPLETE` cannot support a clear loop assessment.
_Avoid_: event count alone

**Native CLEAR**:
A documented positive loop-clear state emitted by the Qwen runtime itself.
_Avoid_: absence of a loop event, enabled loop-detection setting

**Host CLEAR**:
A separate, versioned ProofLoop detector result stating that its defined loop pattern was not found in a complete event stream.
_Avoid_: Native CLEAR, proof that no conceivable loop occurred

**Normal exit**:
A cleanly ended process/session that did not provide evidence of a budget stop; it is not a continuation-eligible budget terminal.
_Avoid_: budget stop
