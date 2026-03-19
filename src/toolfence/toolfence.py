import inspect
from typing import Callable, Dict, List, Set

from .toolfence_data import (
    Context,
    DynamicData,
    Rule,
    Tool,
    ToolCall,
    ToolCallRecord,
    ValidationResult,
    _create_tool_call_record,
)
from .toolfence_validation import run_block_rules, run_escalation_rules
from .toolfence_config import (
    ConfigIssue,
    ToolFenceSetupError,
    check_approval_handler,
    check_default_approval_handler,
    check_rule,
    validate_manager,
)


class AgentManager:
    def __init__(self, version: str = "default"):
        self.version = version

        self.tools: Dict[str, Tool] = {}
        self.history: List[ToolCallRecord] = []
        self.evidence: DynamicData = DynamicData()

        self.block_rules: Dict[str, List[Rule]] = {}
        self.escalation_rules: Dict[str, List[Rule]] = {}
        self.arg_checking_tools: Set[str] = set()

        self.default_approval_handler: Callable[[Context], bool] | None = None
        self.tool_approval_handlers: Dict[str, Callable[[Context], bool] | str] = {}

        self.rule_ids: Dict[str, str] = {}

    def set_evidence(self, key: str, value) -> None:
        setattr(self.evidence, key, value)


    def set_rules(
        self,
        tool: str,
        rules: List[Rule] = [],
        approval_handler: Callable[[Context], bool] | str = "default",
        arg_checking: bool = True,
    ) -> None:

        # Structural check
        issues: List[ConfigIssue] = []
        duplicates = set()

        for rule in rules:
            # Duplicate ID check
            if isinstance(rule.id, str) and rule.id.strip():
                if rule.id in self.rule_ids or rule.id in duplicates:
                    issues.append(ConfigIssue(
                        level="error",
                        location=f"rule:{rule.id} (tool:{tool})",
                        message=(
                            f'Rule ID "{rule.id}" is already used by tool '
                            f'"{tool if rule.id in duplicates else self.rule_ids[rule.id]}". Rule IDs must be unique.'
                        ),
                    ))
                    continue
                else:
                    duplicates.add(rule.id)

            issues.extend(check_rule(rule, tool))

        if approval_handler != "default":
            issues.extend(check_approval_handler(approval_handler, tool))

        errors = [i for i in issues if i.level == "error"]
        warnings = [i for i in issues if i.level == "warning"]

        if warnings:
            print(f'ToolFence configuration warnings for "{tool}":')
            for w in warnings:
                print(w)

        if errors:

            error_lines = "\n".join(str(e) for e in errors)
            raise ToolFenceSetupError(
                f'ToolFence configuration errors in set_rules("{tool}") — '
                f'fix these before running the agent:\n{error_lines}'
            )

        self.tool_approval_handlers[tool] = approval_handler

        if arg_checking:
            self.arg_checking_tools.add(tool)

        block_rules = []
        escalation_rules = []

        for rule in rules:
            self.rule_ids[rule.id] = tool
            if rule.action == "block":
                block_rules.append(rule)
            else:
                escalation_rules.append(rule)

        self.block_rules[tool] = block_rules
        self.escalation_rules[tool] = escalation_rules

    def set_default_approval_handler(self, handler: Callable[[Context], bool]) -> None:
        # Structural check
        issues = check_default_approval_handler(handler)

        errors = [i for i in issues if i.level == "error"]
        warnings = [i for i in issues if i.level == "warning"]

        if warnings:
            print("ToolFence configuration warnings for default approval handler:")
            for w in warnings:
                print(w)

        if errors:
            error_lines = "\n".join(str(e) for e in errors)
            raise ToolFenceSetupError(
                f"ToolFence configuration errors in set_default_approval_handler() — "
                f"fix these before running the agent:\n{error_lines}"
            )

        self.default_approval_handler = handler

    # Full ToolFence configuration check
    def validate(self) -> None:
        validate_manager(self)
