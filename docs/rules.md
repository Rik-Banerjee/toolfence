# Rules

## The Rule dataclass

```python
@dataclass(frozen=True)
class Rule:
    id:          str
    description: str
    condition:   Callable[[Context], bool]
    action:      str  # "block" | "escalate"
```

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier across all rules in the manager. Used in error messages and history. |
| `description` | `str` | Human-readable explanation of why the rule exists. Surfaced in `BlockedToolCall.message`. |
| `condition` | `Callable[[Context], bool]` | A callable that takes a `Context` and returns a bool. Evaluated at call time. |
| `action` | `str` | `"block"` to hard block, `"escalate"` to request approval. |

---

## Actions

### `"block"`

The tool call is prevented immediately. The tool function never runs. `BlockedToolCall` is raised with `reason=BlockReason.RULE_TRIGGERED`.

```python
Rule(
    id="no-large-deletes",
    description="Deleting more than 100 records at once is not permitted.",
    condition=lambda ctx: ctx.tool_call.arguments.count > 100,
    action="block",
)
```

### `"escalate"`

Execution is paused and the approval handler is called with the current `Context`. If the handler returns `True`, the tool runs. If it returns `False`, `BlockedToolCall` is raised with `reason=BlockReason.APPROVAL_DENIED`.

```python
Rule(
    id="large-export",
    description="Exporting more than 1,000 records requires approval.",
    condition=lambda ctx: ctx.tool_call.arguments.count > 1000,
    action="escalate",
)
```

---

## Conditions

A condition is any callable that accepts one argument (a `Context`) and returns a bool. Lambdas are the most common form, but named functions work too.

```python
# Lambda
condition=lambda ctx: ctx.tool_call.arguments.amount > 10000

# Named function
def is_large_transfer(ctx):
    return ctx.tool_call.arguments.amount > 10000

condition=is_large_transfer
```

### Accessing context in conditions

See [Core Concepts — The Context object](core-concepts.md#the-context-object) for the full structure.

---

## Rule IDs

Rule IDs must be:

- Non-empty strings
- Non-whitespace
- Unique across **all tools** in the manager — not just within a single tool

Duplicate IDs raise a `ToolFenceSetupError` immediately at `set_rules()` time.

```python
# This raises ToolFenceSetupError — "my-rule" is already registered
manager.set_rules("tool_a", rules=[Rule(id="my-rule", ...)])
manager.set_rules("tool_b", rules=[Rule(id="my-rule", ...)])
```

---

## Tools with no rules

Calling `set_rules()` with an empty list is valid. The tool will still benefit from argument checking but no rules will be evaluated.

```python
manager.set_rules(tool = "get_balance", rules=[])
```

---

## Accessing history in conditions

The `ctx.history` list contains every tool call made in the session so far — including blocked ones. This allows stateful rules that depend on what has already happened.

```python
# Allow a tool to be called only once per session
Rule(
    id="once-only",
    description="This action can only be performed once per session.",
    condition=lambda ctx: any(
        r.tool == "send_report" and not r.blocked
        for r in ctx.history
    ),
    action="block",
)
```

```python
# Block if the same argument value has been used before
Rule(
    id="no-repeat-transfers",
    description="Cannot transfer to the same account twice in one session.",
    condition=lambda ctx: any(
        r.tool == "transfer_funds"
        and not r.blocked
        and r.arguments.to_account == ctx.tool_call.arguments.to_account
        for r in ctx.history
    ),
    action="block",
)
```

---

## Arg checking

By default, `set_rules()` enables argument checking for the tool. Before any rules run, ToolFence verifies:

- All parameters declared in the function signature are present in the call
- All typed parameters match their declared types

```python
@secure(manager)
def transfer_funds(from_account: str, to_account: str, amount: float) -> dict: ...

# Missing 'amount' → BlockedToolCall(reason=MISSING_ARGUMENT)
transfer_funds("ACC-001", "ACC-002")

# amount is a string instead of float → BlockedToolCall(reason=INVALID_ARGUMENT_TYPE)
transfer_funds("ACC-001", "ACC-002", "five hundred")
```

To disable argument checking for a tool:

```python
manager.set_rules(tool = "my_tool", rules=[], arg_checking=False)
```

---

## Next steps

- [Evidence](evidence.md) — verify LLM arguments against trusted data
- [Approval Handlers](approval-handlers.md) — sync, async, and callable class handlers