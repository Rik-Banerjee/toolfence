# API Reference

## AgentManager

The central object that holds all configuration, evidence, history, and registered tools.

```python
from toolfence.toolFence import AgentManager

manager = AgentManager(version="default")
```

### Constructor

| Parameter | Type | Default | Description |
|---|---|---|---|
| `version` | `str` | `"default"` | Optional label for the manager instance. |

### Attributes

| Attribute | Type | Description |
|---|---|---|
| `tools` | `Dict[str, Tool]` | All tools registered via `@secure`. |
| `history` | `List[ToolCallRecord]` | All tool calls made this session, passed and blocked. |
| `evidence` | `DynamicData` | Verified session data set via `set_evidence()`. |
| `block_rules` | `Dict[str, List[Rule]]` | Block rules per tool. |
| `escalation_rules` | `Dict[str, List[Rule]]` | Escalation rules per tool. |

### Methods

---

#### `set_evidence(key, value)`

Store a verified value in the evidence object. Accessible in rule conditions as `ctx.evidence.key`.

```python
manager.set_evidence("account_id", "ACC-001")
manager.set_evidence("tier", "premium")
```

| Parameter | Type | Description |
|---|---|---|
| `key` | `str` | Attribute name to set on the evidence object. |
| `value` | `Any` | The verified value to store. |

---

#### `set_rules(tool, rules, approval_handler, arg_checking)`

Register rules and an optional approval handler for a named tool. Runs structural checks immediately on registration.

```python
manager.set_rules(
    tool = "transfer_funds",
    rules=[
        Rule(id="hard-limit", ..., action="block"),
        Rule(id="soft-limit", ..., action="escalate"),
    ],
    approval_handler=my_handler,  # optional, defaults to "default"
    arg_checking=True,            # optional, defaults to True
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tool` | `str` | required | The exact name of the tool function. Must match the decorated function name. |
| `rules` | `List[Rule]` | `[]` | Rules to apply to this tool. Evaluated in order. |
| `approval_handler` | `Callable \| "default"` | `"default"` | Handler for escalation rules. `"default"` uses the manager's default handler. |
| `arg_checking` | `bool` | `True` | Whether to validate argument presence and types before rules run. |

Raises `ToolFenceSetupError` if any rule or handler fails structural validation.

---

#### `set_default_approval_handler(handler)`

Set the approval handler used by all tools that do not have a tool-specific handler.

```python
manager.set_default_approval_handler(lambda ctx: True)
```

| Parameter | Type | Description |
|---|---|---|
| `handler` | `Callable[[Context], bool]` | Must accept exactly one argument (Context) and return a bool. Can be sync or async. |

Raises `ToolFenceSetupError` if the handler fails structural validation.

---

#### `validate()`

Run completeness checks across the full configuration. Call after all tools, rules, and handlers are registered — before starting the agent loop.

```python
manager.validate()
```

Raises `ToolFenceSetupError` listing all errors found.

---

## secure

The decorator that registers a tool with the manager and wraps every call with the ToolFence interceptor.

```python
from toolfence.toolFence_secure import secure

@secure(manager)
def my_tool(arg: str) -> dict:
    return {"status": "ok"}
```

Works identically on async functions:

```python
@secure(manager)
async def my_async_tool(arg: str) -> dict:
    return {"status": "ok"}
```

The decorated function's name must match the tool name used in `set_rules()`. ToolFence uses `fn.__name__` as the tool name.

---

## Rule

```python
from toolfence.toolFenceData import Rule

Rule(
    id="my-rule",
    description="Human-readable explanation.",
    condition=lambda ctx: ctx.tool_call.arguments.amount > 100,
    action="block",  # or "escalate"
)
```

| Field | Type | Description |
|---|---|---|
| `id` | `str` | Unique identifier. Must be non-empty, non-whitespace, unique across all tools. |
| `description` | `str` | Human-readable explanation surfaced in `BlockedToolCall.message`. |
| `condition` | `Callable[[Context], bool]` | Takes a `Context`, returns a bool. Pure functions only — no side effects. |
| `action` | `str` | `"block"` or `"escalate"`. |

---

## BlockedToolCall

Raised when a tool call is blocked for any reason.

```python
from toolfence.toolFenceData import BlockedToolCall

try:
    my_tool("arg")
except BlockedToolCall as e:
    print(e.tool)     # name of the blocked tool
    print(e.reason)   # BlockReason enum value
    print(e.message)  # human-readable detail
    print(e.record)   # full ToolCallRecord
```

| Attribute | Type | Description |
|---|---|---|
| `tool` | `str` | Name of the tool that was blocked. |
| `reason` | `BlockReason` | Enum value identifying the cause. |
| `message` | `str` | Human-readable description of why the call was blocked. |
| `record` | `ToolCallRecord` | The full call record logged at the time of the block. |

The exception string is formatted as `[REASON] tool_name: message`.

---

## BlockReason

```python
from toolfence.toolFenceData import BlockReason
```

| Value | When raised |
|---|---|
| `RULE_TRIGGERED` | A block rule condition returned `True`. |
| `APPROVAL_DENIED` | An escalation rule fired and the approval handler returned `False`. |
| `NO_APPROVAL_HANDLER` | An escalation rule fired but no approval handler is configured. |
| `ASYNC_HANDLER_MISMATCH` | An async approval handler is assigned to a sync tool. |
| `MISSING_ARGUMENT` | A required argument was not provided. |
| `INVALID_ARGUMENT_TYPE` | An argument value does not match its declared type. |

---

## Context

Passed to every rule condition and approval handler.

```python
@dataclass(frozen=True)
class Context:
    tool_call: ToolCall
    evidence:  DynamicData
    history:   List[ToolCallRecord]
```

See [Core Concepts — The Context object](core-concepts.md#the-context-object) for full details on valid attribute access.

---

## ToolCallRecord

Stored in `manager.history` for every tool call, passed and blocked.

```python
@dataclass(frozen=True)
class ToolCallRecord:
    uuid:      str
    tool:      str
    arguments: DynamicData
    timestamp: datetime
    blocked:   bool
    reason:    str
```

| Field | Description |
|---|---|
| `uuid` | Unique ID for this call. |
| `tool` | Name of the tool. |
| `arguments` | The arguments passed to the tool. Access by attribute name. |
| `timestamp` | UTC datetime of the call. |
| `blocked` | `True` if the call was blocked, `False` if it passed. |
| `reason` | The `BlockReason` value as a string if blocked, empty string if passed. |

---

## ToolFenceSetupError

Raised when ToolFence detects a configuration error — either at `set_rules()` / `set_default_approval_handler()` time (structural errors) or at `manager.validate()` time (completeness errors).

```python
from toolfence.toolFenceConfig import ToolFenceSetupError

try:
    manager.set_rules("tool", rules=[Rule(id="", ...)])
except ToolFenceSetupError as e:
    print(e.message)
```

| Attribute | Type | Description |
|---|---|---|
| `message` | `str` | Full description of all errors found. |
