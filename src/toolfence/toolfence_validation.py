from typing import List

from .toolfence_data import Context, Rule, ValidationResult


def _evaluate_rule(rule: Rule, context: Context) -> bool:
    return rule.condition(context)


def run_block_rules(context: Context, rules: List[Rule]) -> ValidationResult:
    for rule in rules:
        try:
            triggered = _evaluate_rule(rule, context)
        except Exception as e:
            return ValidationResult(
                blocked=True,
                requires_approval=False,
                message=f'Rule "{rule.id}" raised an exception: {e}',
                rule_id=rule.id,
            )

        if triggered:
            return ValidationResult(
                blocked=True,
                requires_approval=False,
                message=rule.description,
                rule_id=rule.id,
            )

    return ValidationResult(blocked=False, requires_approval=False, message="")


def run_escalation_rules(context: Context, rules: List[Rule]) -> ValidationResult:
    for rule in rules:
        try:
            triggered = _evaluate_rule(rule, context)
        except Exception as e:
            return ValidationResult(
                blocked=True,
                requires_approval=False,
                message=f'Rule "{rule.id}" raised an exception: {e}',
                rule_id=rule.id,
            )

        if triggered:
            return ValidationResult(
                blocked=False,
                requires_approval=True,
                message=rule.description,
                rule_id=rule.id,
            )

    return ValidationResult(blocked=False, requires_approval=False, message="")