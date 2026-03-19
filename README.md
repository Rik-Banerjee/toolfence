# ToolFence

**Deterministic runtime security for AI agent tools.**

LLMs can hallucinate and be prompt-engineered, allowing faulty agent actions to slip through. ToolFence helps solve this by enforcing strict and deterministic rules.

ToolFence is a lightweight Python framework that sits between your LLM and your tool functions. When an agent calls a tool, ToolFence intercepts the call, evaluates your rules, and either passes it through, blocks it, or escalates it for user approval — all before your tool function runs. Rules are Python code, not LLM instructions, so they cannot be overridden by a clever prompt.

---

## Why ToolFence

LLMs are good at deciding *what* to do. They are not reliable enforcers of *what is allowed*. A well-crafted prompt can convince an LLM to ignore its own safety instructions. ToolFence allows a quick and simple way to enforce policy at the code layer — outside the prompt, outside the model, and outside the reach of any user input.

```
User prompt → LLM → tool call → [ToolFence] → tool execution
                                      ↑
                          deterministic rules run here
```

---

## Installation

```bash
pip install toolfence
```

---

## Quick example

```python
from toolfence import secure, AgentManager, Rule, BlockedToolCall

manager = AgentManager()
manager.set_default_approval_handler(lambda ctx: input(f'Do you approve {ctx.tool_call.tool} to execute? ') == 'yes')

manager.set_rules(
    tool = "transfer_funds",
    rules=[
        # Hard block — never transfer over $10,000
        Rule(
            id="transfer-hard-limit",
            description="Transfers over $10,000 are never permitted.",
            condition=lambda ctx: ctx.tool_call.arguments.amount > 10000,
            action="block"
        ),
        # Escalate — transfers over $1,000 need user approval
        Rule(
            id="transfer-large-escalate",
            description="Transfers over $1,000 require approval.",
            condition=lambda ctx: ctx.tool_call.arguments.amount > 1000,
            action="escalate"
        ),
    ],
)

@secure(manager)
def transfer_funds(from_account: str, to_account: str, amount: float) -> dict:
    return {"status": "transferred", "amount": amount}

manager.validate()

try:
    transfer_funds("ACC-001", "ACC-002", 15000.0)
except BlockedToolCall as e:
    print(e.message)  # "Transfers over $10,000 are never permitted."
```

---

## Features

- **Hard block rules** — write Python conditions that unconditionally prevent a tool call from executing
- **Escalation rules** — pause execution and require user approval before proceeding
- **Evidence verification** — load trusted data (e.g., database, API) and verify LLM-supplied arguments against it, catching hallucinations and prompt injection
- **Argument checking** — validate argument presence and types before rules even run
- **Async support** — works with async tools and async approval handlers
- **Config validation** — catch misconfigured rules, missing handlers, and configuration mistakes before your agent runs
- **Structured errors** — every blocked tool call raises `BlockedToolCall` with a message for your agent's LLM
- **Full history** — every tool call (passed or blocked) is recorded in `AgentManager.history`
- **Easy Integration** — easily integrates with other frameworks and workflows such as LangChain

---

## How it works

```
@secure(manager)
def my_tool(arg: str) -> dict: ...
```

Decorating a function with `@secure` registers it with the `AgentManager` and wraps it with the ToolFence interceptor. Every call to `my_tool` now runs through:

1. **Argument checking** — are all required arguments present and correctly typed?
2. **Block rules** — does any block rule condition return `True`? If so, raise `BlockedToolCall`.
3. **Escalation rules** — does any escalation rule condition return `True`? If so, call the approval handler. If denied, raise `BlockedToolCall`.
4. **Execute** — all checks passed, run the real tool function.
5. **Record** — log the call to `AgentManager.history`.

---

## Documentation

- [Getting Started](docs/getting-started.md)
- [Core Concepts](docs/core-concepts.md)
- [Rules](docs/rules.md)
- [Evidence](docs/evidence.md)
- [Approval Handlers](docs/approval-handlers.md)
- [API Reference](docs/api-reference.md)

---

## Examples

- [`examples/example_basic.py`](examples/example_basic.py) — minimal setup with block and escalation rules
- [`examples/example_evidence.py`](examples/example_evidence.py) — evidence verification and prompt injection prevention
