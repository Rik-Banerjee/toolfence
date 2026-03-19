# Core Concepts

## The problem ToolFence solves

When an LLM agent calls a tool, it decides what arguments to pass based on the conversation — the user's message, the system prompt, and its own reasoning. All of that is text. Text can be manipulated. A user can craft a message that convinces the LLM to call a tool it shouldn't, pass an argument it shouldn't, or bypass a safety instruction it was given.

ToolFence moves enforcement out of the prompt and into Python code. Rules are evaluated at the call layer — after the LLM has decided what to do but before the tool function runs. No prompt, no user input, and no LLM reasoning can change what your rules do.

---

## The three pillars

### 1. Block rules

A block rule unconditionally prevents a tool call from executing when its condition is met. The tool function body never runs. No approval is requested. The call is logged to history as blocked and a `BlockedToolCall` exception is raised immediately.

Use block rules for things that are **never** allowed — hard limits, forbidden operations, invariants that must always hold.

```python
Rule(
    id="no-system-deletion",
    description="System records cannot be deleted.",
    condition=lambda ctx: ctx.tool_call.arguments.record_id.startswith("SYS-"),
    action="block",
)
```

### 2. Escalation rules

An escalation rule pauses execution and hands control to an approval handler. If the handler returns `True`, the tool runs normally. If it returns `False`, the call is blocked and `BlockedToolCall` is raised.

Use escalation rules for things that are **sometimes** allowed but require user approval (e.g., large transactions, deleting files, allowing permissions).

```python
Rule(
    id="large-transfer",
    description="Transfers over $1,000 require approval.",
    condition=lambda ctx: ctx.tool_call.arguments.amount > 1000,
    action="escalate",
)
```

### 3. Evidence verification

Evidence is verified data loaded from a trusted source (e.g., a database, an auth service, a session token) at the start of a session. It lives in `manager.evidence`, which the LLM cannot read or modify.

When the LLM fills in tool arguments, ToolFence can check those arguments against the evidence. If they contradict each other, a block rule fires. This catches two classes of failure:

- **Hallucination** — the LLM made up a value that looks plausible but is wrong
- **Prompt injection** — a malicious user convinced the LLM to use a different account, user ID, or other sensitive value

```python
manager.set_evidence("account_id", "ACC-001")  # loaded from DB

Rule(
    id="account-mismatch",
    description="Transfer source does not match the verified session account.",
    condition=lambda ctx: ctx.tool_call.arguments.from_account != ctx.evidence.account_id,
    action="block",
)
```

---

## The execution order

Every secured tool call goes through these steps in order:

```
tool called
    │
    ▼
1. Argument checking
   Are all required arguments present?
   Are all typed arguments the correct type?
   → if not: raise BlockedToolCall(MISSING_ARGUMENT or INVALID_ARGUMENT_TYPE)
    │
    ▼
2. Block rules (evaluated in registration order)
   Does any block rule condition return True?
   → if yes: raise BlockedToolCall(RULE_TRIGGERED)
    │
    ▼
3. Escalation rules (evaluated in registration order)
   Does any escalation rule condition return True?
   → if yes: call approval handler
       → if denied: raise BlockedToolCall(APPROVAL_DENIED)
       → if approved: continue
    │
    ▼
4. Execute tool function
    │
    ▼
5. Record to history (blocked=False)
```

Block rules are always evaluated before escalation rules. Within each group, the first matching rule wins and evaluation stops.

---

## The Context object

Every rule condition and every approval handler receives a single `Context` argument. It carries everything ToolFence knows about the current call.

```python
@dataclass(frozen=True)
class Context:
    tool_call: ToolCall
    evidence:  DynamicData
    history:   List[ToolCallRecord]
```

### `ctx.tool_call`

Information about the current call being evaluated.

```python
@dataclass(frozen=True)
class ToolCall:
    tool:      str         # name of the tool being called
    arguments: DynamicData # the arguments passed by the LLM
```

Access arguments by name:

```python
ctx.tool_call.tool               # "transfer_funds"
ctx.tool_call.arguments.amount   # 5000.0
ctx.tool_call.arguments.from_account  # "ACC-001"
```

### `ctx.evidence`

The verified data loaded into the manager via `set_evidence()`. Access any key by attribute name:

```python
ctx.evidence.account_id   # "ACC-001"
ctx.evidence.user_id      # "USER-42"
ctx.evidence.tier         # "premium"
```

Evidence is set by your code from a trusted source. The LLM cannot influence it.

### `ctx.history`

A list of `ToolCallRecord` objects — one for every tool call made in this session so far, including blocked ones. Use it to write stateful rules that depend on what has already happened.

```python
@dataclass(frozen=True)
class ToolCallRecord:
    uuid:      str         # unique ID for this call
    tool:      str         # tool name
    arguments: DynamicData # arguments passed
    timestamp: datetime    # when the call was made
    blocked:   bool        # whether the call was blocked
    reason:    str         # block reason if blocked, empty string if passed
```

Access history in a condition:

```python
# Block if this tool has already been called successfully this session
condition=lambda ctx: any(
    r.tool == "send_email" and not r.blocked
    for r in ctx.history
)
```

### Using Context correctly

Conditions and handlers must only access the three top-level fields: `tool_call`, `evidence`, and `history`. Accessing any other attribute on `ctx` — or accessing `tool_call.args` instead of `tool_call.arguments`, for example — will result in errors during runtime. It is recomennded to run tests after all tools have been configured with ToolFence.

```python
# Correct
lambda ctx: ctx.tool_call.arguments.amount > 100
lambda ctx: ctx.evidence.account_id == "ACC-001"
lambda ctx: len(ctx.history) > 0

# Wrong — caught at setup time
lambda ctx: ctx.tool.arguments.amount > 100      # ctx.tool does not exist
lambda ctx: ctx.tool_call.args.amount > 100      # .args is not a valid attribute
lambda ctx: ctx.ev.account_id == "ACC-001"       # ctx.ev does not exist
```

---

## Where ToolFence fits in your stack

ToolFence is not an agent framework. It does not manage conversations, call the LLM, or parse tool schemas. It is a determinsitic security layer that wraps your existing tool functions.

```
┌─────────────────────────────────────┐
│  Agent framework (LangChain, etc.)  │
│  or custom agent loop               │
├─────────────────────────────────────┤
│  LLM (decides what to call)         │
├─────────────────────────────────────┤
│  ToolFence (enforces what's allowed)│  ← you are here
├─────────────────────────────────────┤
│  Tool functions (do the actual work)│
└─────────────────────────────────────┘
```

Use the LLM to decide what actions to take. Use ToolFence to enforce what actions are permitted.

---

## Next steps

- [Rules](rules.md) — full rule API and patterns
- [Evidence](evidence.md) — verify LLM arguments against trusted data
- [Approval Handlers](approval-handlers.md) — sync, async, and callable class handlers