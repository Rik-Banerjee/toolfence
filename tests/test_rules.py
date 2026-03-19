import pytest
from toolfence.toolfence import AgentManager
from toolfence.toolfence_secure import secure
from toolfence.toolfence_data import Rule, BlockedToolCall, BlockReason


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

def make_manager():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    return m


def make_tool(manager, rules):
    manager.set_rules("action", rules=rules)

    @secure(manager)
    def action(value: int) -> dict:
        return {"status": "ok", "value": value}

    return action


# ---------------------------------------------------------------
# Block rules
# ---------------------------------------------------------------

def test_block_rule_triggers():
    m = make_manager()
    tool = make_tool(m, rules=[
        Rule(
            id="block-if-negative",
            description="Negative values are not allowed.",
            condition=lambda ctx: ctx.tool_call.arguments.value < 0,
            action="block",
        )
    ])
    with pytest.raises(BlockedToolCall) as exc:
        tool(-1)
    assert exc.value.reason == BlockReason.RULE_TRIGGERED


def test_block_rule_does_not_trigger():
    m = make_manager()
    tool = make_tool(m, rules=[
        Rule(
            id="block-if-negative",
            description="Negative values are not allowed.",
            condition=lambda ctx: ctx.tool_call.arguments.value < 0,
            action="block",
        )
    ])
    result = tool(5)
    assert result["status"] == "ok"


def test_block_rule_body_never_runs():
    m = make_manager()
    ran = []

    m.set_rules("tracked_action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    def tracked_action(value: int) -> dict:
        ran.append(value)
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall):
        tracked_action(1)

    assert ran == []


def test_block_rule_message_contains_rule_id():
    m = make_manager()
    tool = make_tool(m, rules=[
        Rule(
            id="my-rule-id",
            description="Blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])
    with pytest.raises(BlockedToolCall) as exc:
        tool(1)
    assert "my-rule-id" in exc.value.message


# ---------------------------------------------------------------
# Escalation rules
# ---------------------------------------------------------------

def test_escalation_rule_triggers_and_approves():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    tool = make_tool(m, rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])
    result = tool(1)
    assert result["status"] == "ok"


def test_escalation_rule_triggers_and_denies():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: False)
    tool = make_tool(m, rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])
    with pytest.raises(BlockedToolCall) as exc:
        tool(1)
    assert exc.value.reason == BlockReason.APPROVAL_DENIED


def test_escalation_rule_does_not_trigger():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: False)  # would deny if it fired
    tool = make_tool(m, rules=[
        Rule(
            id="never-escalate",
            description="Never escalated.",
            condition=lambda ctx: False,
            action="escalate",
        )
    ])
    result = tool(1)
    assert result["status"] == "ok"


# ---------------------------------------------------------------
# Rule priority and ordering
# ---------------------------------------------------------------

def test_block_takes_priority_over_escalate():
    m = AgentManager()
    approval_called = []
    m.set_default_approval_handler(lambda ctx: approval_called.append(True) or True)

    m.set_rules("action", rules=[
        Rule(
            id="block-rule",
            description="Blocked.",
            condition=lambda ctx: True,
            action="block",
        ),
        Rule(
            id="escalate-rule",
            description="Escalated.",
            condition=lambda ctx: True,
            action="escalate",
        ),
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action(1)

    assert exc.value.reason == BlockReason.RULE_TRIGGERED
    assert approval_called == []  # escalation handler never reached


def test_first_matching_block_rule_stops_evaluation():
    m = make_manager()
    second_rule_checked = []

    m.set_rules("action", rules=[
        Rule(
            id="first-block",
            description="First block.",
            condition=lambda ctx: True,
            action="block",
        ),
        Rule(
            id="second-block",
            description="Second block.",
            condition=lambda ctx: second_rule_checked.append(True) or True,
            action="block",
        ),
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action(1)

    assert exc.value.reason == BlockReason.RULE_TRIGGERED
    assert second_rule_checked == []


def test_no_rules_passes_clean():
    m = make_manager()
    tool = make_tool(m, rules=[])
    result = tool(42)
    assert result["status"] == "ok"
    assert result["value"] == 42


# ---------------------------------------------------------------
# Rule condition receives correct context
# ---------------------------------------------------------------

def test_rule_receives_tool_call_arguments():
    m = make_manager()
    received = []

    m.set_rules("action", rules=[
        Rule(
            id="capture-args",
            description="Capture.",
            condition=lambda ctx: received.append(ctx.tool_call.arguments.value) or False,
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    action(99)
    assert received == [99]


def test_rule_receives_evidence():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("limit", 100)

    m.set_rules("action", rules=[
        Rule(
            id="evidence-check",
            description="Over limit.",
            condition=lambda ctx: ctx.tool_call.arguments.value > ctx.evidence.limit,
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    result = action(50)
    assert result["status"] == "ok"

    with pytest.raises(BlockedToolCall):
        action(150)


def test_rule_receives_history():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)

    m.set_rules("action", rules=[
        Rule(
            id="once-only",
            description="Only allowed once.",
            condition=lambda ctx: any(
                r.tool == "action" and not r.blocked for r in ctx.history
            ),
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    action(1)
    with pytest.raises(BlockedToolCall):
        action(2)