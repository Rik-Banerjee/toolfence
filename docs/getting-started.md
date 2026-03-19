# Getting Started

## Installation

```bash
pip install toolfence
```

For async support, no additional dependencies are needed — ToolFence uses Python's built-in `asyncio`.

---

## Your first secured agent

This guide walks through a minimal ToolFence setup from scratch.

### 1. Create an AgentManager

The `AgentManager` is the central object that holds your rules, evidence, approval handlers, and call history. Every secured tool is registered with it.

```python
from toolfence import AgentManager

manager = AgentManager()
```

### 2. Set an approval handler

An approval handler is a callable that receives a `Context` argument and returns `True` (approve) or `False` (deny) to signal whether user approval is given. It is called whenever an escalation rule fires. You need at least a default handler if any of your tools have escalation rules.

```python
def my_approval_handler(ctx) -> bool:
    tool = ctx.tool_call.tool
    args = vars(ctx.tool_call.arguments)
    answer = input(f"Approve {tool}({args})? (yes/no): ")
    return answer.strip().lower() == "yes"

manager.set_default_approval_handler(my_approval_handler)
```

### 3. Define rules

Rules are attached to specific tool names using `set_rules()`. Each `Rule` has an ID, a description, a condition (a callable that takes a `Context` and returns a bool), and an action (`"block"` or `"escalate"`).

```python
from toolfence import Rule

manager.set_rules(
    tool = "delete_record",
    rules=[
        Rule(
            id="block-system-records",
            description="System records cannot be deleted.",
            condition=lambda ctx: ctx.tool_call.arguments.record_id.startswith("SYS-"),
            action="block",
        ),
        Rule(
            id="escalate-all-deletions",
            description="All deletions require approval.",
            condition=lambda ctx: True,
            action="escalate",
        ),
    ],
)
```

### 4. Decorate your tools with @secure

Wrap your tool functions with `@secure(manager)`. This registers the tool with the manager and wraps every call with the ToolFence interceptor.

```python
from toolfence import secure

@secure(manager)
def delete_record(record_id: str) -> dict:
    return {"status": "deleted", "record_id": record_id}
```

### 5. Validate your configuration

Call `manager.validate()` after all tools, rules, and handlers are registered — before starting your agent loop. This runs completeness checks and raises a `ToolFenceSetupError` with a full list of any problems found.

```python
manager.validate()
```

*Thats it, ToolFence is set up for your agent!*

### 6. Handle BlockedToolCall during runtime

When a rule blocks a call or an approval handler denies it, ToolFence raises `BlockedToolCall`. Catch it in your agent loop and decide how to handle it — typically by returning the error message to the LLM so it can inform the user and take the next steps.

```python
from toolfence import BlockedToolCall

try:
    result = delete_record("SYS-001")
except BlockedToolCall as e:
    print(f"Blocked [{e.reason}]: {e.message}")
```

### Complete example

```python
from toolfence import AgentManager, secure, Rule, BlockedToolCall

manager = AgentManager()
manager.set_default_approval_handler(lambda ctx: input(f'Do you approve {ctx.tool_call.tool} to execute? ') == 'yes')

manager.set_rules(
    tool = "delete_record",
    rules=[
        Rule(
            id="block-system-records",
            description="System records cannot be deleted.",
            condition=lambda ctx: ctx.tool_call.arguments.record_id.startswith("SYS-"),
            action="block",
        ),
        Rule(
            id="escalate-all-deletions",
            description="All deletions require approval.",
            condition=lambda ctx: True,
            action="escalate",
        ),
    ],
)

@secure(manager)
def delete_record(record_id: str) -> dict:
    return {"status": "deleted", "record_id": record_id}

manager.validate()

try:
    delete_record("SYS-001")
except BlockedToolCall as e:
    print(f"Blocked: {e.message}")
# Output: Blocked: System records cannot be deleted.

try:
    delete_record("REC-042")
except BlockedToolCall as e:
    print(f"Blocked: {e.message}")
# Output: (approval prompt shown, approved, tool runs)
```

---

## Next steps

- [Core Concepts](core-concepts.md) — understand the mental model behind ToolFence
- [Rules](rules.md) — full rule API and patterns
- [Evidence](evidence.md) — verify LLM arguments against trusted data
- [Approval Handlers](approval-handlers.md) — sync, async, and callable class handlers
