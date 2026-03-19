import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, List

from .toolfence_data import Rule

if TYPE_CHECKING:
    from .toolfence import AgentManager




class ToolFenceSetupError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class ConfigIssue:
    level: str       # "error" or "warning"
    location: str    # e.g. "tool:transfer_funds", "rule:transfer-limit", "handler:default"
    message: str

    def __str__(self) -> str:
        return f"  [{self.level.upper()}] {self.location}: {self.message}"

# Checks for number of params the handler accepts
def _handler_param_count(handler) -> int:
    if inspect.isfunction(handler) or inspect.isbuiltin(handler):
        return len(inspect.signature(handler).parameters)

    if inspect.ismethod(handler):
        return len(inspect.signature(handler).parameters)

    if hasattr(handler, '__call__'):
        params = list(inspect.signature(handler.__call__).parameters.values())
        return len([p for p in params if p.name != 'self'])

    return -1


# Validate a rule
def check_rule(rule: Rule, tool: str) -> List[ConfigIssue]:
    issues = []
    location = f"rule:{rule.id} (tool:{tool})"

    # Rule ID must be non-empty, non-whitespace
    if not isinstance(rule.id, str) or not rule.id.strip():
        issues.append(ConfigIssue(
            level="error",
            location=f"rule (tool:{tool})",
            message="Rule ID must be a non-empty, non-whitespace string.",
        ))
        return issues

    # Condition must be callable
    if not callable(rule.condition):
        issues.append(ConfigIssue(
            level="error",
            location=location,
            message=f"Condition is not callable. Got {type(rule.condition).__name__}.",
        ))
        return issues

    # Condition must accept exactly one argument (context)
    param_count = _handler_param_count(rule.condition)
    if param_count != 1:
        issues.append(ConfigIssue(
            level="error",
            location=location,
            message=(
                f"Condition must accept exactly one argument (context). "
                f"Got {param_count} parameter(s)."
            ),
        ))

    # Action must be "block" or "escalate"
    if rule.action not in ("block", "escalate"):
        issues.append(ConfigIssue(
            level="error",
            location=location,
            message=(
                f'Invalid action "{rule.action}". '
                f'Valid actions are "block" or "escalate".'
            ),
        ))

    return issues

# Validate approval handler
def check_approval_handler(handler, tool: str) -> List[ConfigIssue]:
    issues = []
    location = f"handler (tool:{tool})"

    if not callable(handler):
        issues.append(ConfigIssue(
            level="error",
            location=location,
            message=f"Approval handler is not callable. Got {type(handler).__name__}.",
        ))
        return issues

    # Handler must accept exactly one argument (context)
    param_count = _handler_param_count(handler)
    if param_count != 1:
        issues.append(ConfigIssue(
            level="error",
            location=location,
            message=(
                f"Approval handler must accept exactly one argument (context). "
                f"Got {param_count} parameter(s)."
            ),
        ))

    return issues

# Validate default handler
def check_default_approval_handler(handler) -> List[ConfigIssue]:
    return check_approval_handler(handler, tool="default")



# Run full AgentManager configuration checks
def validate_manager(manager: "AgentManager") -> None:
    issues: List[ConfigIssue] = []

    registered_tools = set(manager.tools.keys())
    configured_tools = set(manager.block_rules.keys()) | set(manager.escalation_rules.keys())

    # Escalation rules must have approval handler
    for tool, rules in manager.escalation_rules.items():
        if not rules:
            continue

        handler = manager.tool_approval_handlers.get(tool)

        if handler is None:
            issues.append(ConfigIssue(
                level="error",
                location=f"tool:{tool}",
                message=(
                    'Tool has escalation rule(s) but no approval handler configured. '
                    'Pass approval_handler= to set_rules() or call set_default_approval_handler().'
                ),
            ))
        elif handler == "default" and manager.default_approval_handler is None:
            issues.append(ConfigIssue(
                level="error",
                location=f"tool:{tool}",
                message=(
                    'Tool has escalation rule(s) that rely on the default approval handler, '
                    'but no default handler has been set. '
                    'Call set_default_approval_handler() before running the agent.'
                ),
            ))

    # Check for async handlers assigned to sync tools
    for tool, handler in manager.tool_approval_handlers.items():
        if handler == "default":
            handler = manager.default_approval_handler
        if handler is None or not inspect.iscoroutinefunction(handler):
            continue

        tool_obj = manager.tools.get(tool)
        if tool_obj is not None and not tool_obj.is_async:
            issues.append(ConfigIssue(
                level="error",
                location=f"tool:{tool}",
                message=(
                    f'Approval handler is async but "{tool}" is a sync tool. '
                    f'Use a sync handler or convert the tool to async.'
                ),
            ))

    # set_rules called for a tool not decorated with @secure
    for tool in configured_tools:
        if tool not in registered_tools:
            issues.append(ConfigIssue(
                level="warning",
                location=f"tool:{tool}",
                message=(
                    f'set_rules() was called for "{tool}" but no @secure-decorated function '
                    f'with that name has been registered. '
                    f'Check for a name mismatch or missing @secure decorator.'
                ),
            ))

    # @secure tools with no set_rules call
    for tool in registered_tools:
        if tool not in configured_tools:
            issues.append(ConfigIssue(
                level="warning",
                location=f"tool:{tool}",
                message=(
                    f'"{tool}" is decorated with @secure but set_rules() was never called for it. '
                    f'It will run with no rules and no arg checking.'
                ),
            ))

    # Default handler set but no escalation rules anywhere
    has_any_escalation = any(bool(rules) for rules in manager.escalation_rules.values())
    if manager.default_approval_handler is not None and not has_any_escalation:
        issues.append(ConfigIssue(
            level="warning",
            location="handler:default",
            message=(
                "A default approval handler is set but no escalation rules exist anywhere. "
                "The handler will never be called."
            ),
        ))

    errors   = [i for i in issues if i.level == "error"]
    warnings = [i for i in issues if i.level == "warning"]

    if warnings:
        print("ToolFence configuration warnings:")
        for w in warnings:
            print(w)

    if errors:
        error_lines = "\n".join(str(e) for e in errors)
        raise ToolFenceSetupError(
            f"ToolFence configuration errors found — fix these before running the agent:\n"
            f"{error_lines}"
        )