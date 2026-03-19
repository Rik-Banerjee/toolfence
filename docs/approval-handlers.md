# Approval Handlers

## What an approval handler is

An approval handler is a callable that is invoked when an escalation rule fires. It receives the current `Context` and returns `True` to allow the tool call to proceed or `False` to deny it.

```python
def my_handler(ctx) -> bool:
    # inspect ctx, make a decision
    return True  # or False
```

Approval handlers are where human-in-the-loop control lives. They are the mechanism by which ToolFence asks a person (or another system) whether a particular action should be allowed.

---

## Default vs tool-specific handlers

### Default handler

A default handler is used for any tool that does not have its own specific handler registered. Set it once and it applies everywhere escalation rules exist.

```python
manager.set_default_approval_handler(Callable)
```

### Tool-specific handler

A tool-specific handler overrides the default for that particular tool only. Other tools continue to use the default.

```python
manager.set_rules(
    tool = "delete_record",
    rules=[...],
    approval_handler=my_specific_handler,  # only used for delete_record
)
```

If a tool has escalation rules and no tool-specific handler is registered, it falls back to the default handler. If no default handler has been set either, ToolFence will raise a the call is blocked with `BlockReason.NO_APPROVAL_HANDLER`. Catch setup issues like this before runtime by executing `manager.validate()`.

---

## Handler forms

### Lambda

```python
manager.set_default_approval_handler(lambda ctx: True)
```

### Named function

```python
def cli_handler(ctx) -> bool:
    tool = ctx.tool_call.tool
    args = vars(ctx.tool_call.arguments)
    answer = input(f"Approve {tool}({args})? (yes/no): ")
    return answer.strip().lower() == "yes"

manager.set_default_approval_handler(cli_handler)
```

---

## Async handlers

If your approval handler needs to call an external service (e.g., a Slack webhook, a PagerDuty endpoint, an internal approval API), you can make it async. ToolFence awaits it automatically when it is attached to an async tool.

```python
import asyncio

async def webhook_handler(ctx) -> bool:
    tool = ctx.tool_call.tool
    args = vars(ctx.tool_call.arguments)
    # Simulate sending approval request and waiting for response
    await asyncio.sleep(0.1)
    print(f"Approval received for {tool}")
    return True

manager.set_default_approval_handler(webhook_handler)
```

### Async handler rules

| Tool type | Handler type | Behaviour |
|---|---|---|
| Sync | Sync | Works correctly |
| Sync | Async | Blocked with `ASYNC_HANDLER_MISMATCH` |
| Async | Sync | Works correctly — handler is called directly |
| Async | Async | Works correctly — handler is awaited |

An async handler on a sync tool is caught at runtime with `BlockReason.ASYNC_HANDLER_MISMATCH`. It is also caught earlier by `manager.validate()`. Use a sync handler on sync tools, or convert the tool to async.

---

## The Context object in handlers

The handler receives the full `Context` for the call being approved. Use it to make informed decisions.

```python
def smart_handler(ctx) -> bool:
    amount = ctx.tool_call.arguments.amount
    tier   = ctx.evidence.tier

    # Premium users have a higher auto-approval threshold
    if tier == "premium" and amount < 5000:
        return True

    # All others require explicit confirmation
    answer = input(f"Approve transfer of ${amount}? (yes/no): ")
    return answer.strip().lower() == "yes"
```

See [Core Concepts — The Context object](core-concepts.md#the-context-object) for the full structure.

---

## Handler signature requirements

Every approval handler must accept exactly one argument — the `Context`. Handlers with zero or more than one parameter are caught immediately when registered and raise `ToolFenceSetupError`.

```python
# Correct
manager.set_default_approval_handler(lambda ctx: True)

# Wrong — zero args, raises ToolFenceSetupError immediately
manager.set_default_approval_handler(lambda: True)

# Wrong — two args, raises ToolFenceSetupError immediately
manager.set_default_approval_handler(lambda ctx, extra: True)
```

---

## Handler is only called when a rule fires

The approval handler is not called on every tool invocation — only when an escalation rule condition returns `True`. If no escalation rule fires (either because there are none, or because none matched), the handler is never called.

```python
manager.set_rules(
    tool = "transfer_funds",
    rules=[
        Rule(
            id="large-transfer",
            description="Large transfers require approval.",
            condition=lambda ctx: ctx.tool_call.arguments.amount > 1000,
            action="escalate",
        ),
    ],
)

# amount=50 — escalation rule does not fire, handler never called
transfer_funds("ACC-001", "ACC-002", 50.0)

# amount=5000 — escalation rule fires, handler is called
transfer_funds("ACC-001", "ACC-002", 5000.0)
```
