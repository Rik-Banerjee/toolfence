import pytest
from toolfence.toolfence import AgentManager
from toolfence.toolfence_secure import secure
from toolfence.toolfence_data import Rule, BlockedToolCall, BlockReason


def make_manager():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    return m


# ---------------------------------------------------------------
# Basic recording
# ---------------------------------------------------------------

def test_passed_call_recorded_in_history():
    m = make_manager()
    m.set_rules("action", rules=[])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    action(1)
    assert len(m.history) == 1
    assert m.history[0].blocked is False
    assert m.history[0].tool == "action"


def test_blocked_call_recorded_in_history():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall):
        action(1)

    assert len(m.history) == 1
    assert m.history[0].blocked is True
    assert m.history[0].tool == "action"


def test_blocked_call_record_has_reason():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall):
        action(1)

    assert m.history[0].reason != ""


def test_multiple_calls_all_recorded():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="block-negative",
            description="Blocked.",
            condition=lambda ctx: ctx.tool_call.arguments.value < 0,
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    action(1)
    action(2)
    with pytest.raises(BlockedToolCall):
        action(-1)

    assert len(m.history) == 3
    assert m.history[0].blocked is False
    assert m.history[1].blocked is False
    assert m.history[2].blocked is True


def test_history_record_contains_arguments():
    m = make_manager()
    m.set_rules("action", rules=[])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    action(42)
    assert m.history[0].arguments.value == 42


def test_history_record_has_uuid_and_timestamp():
    m = make_manager()
    m.set_rules("action", rules=[])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    action(1)
    record = m.history[0]
    assert record.uuid != ""
    assert record.timestamp is not None


# ---------------------------------------------------------------
# History accessible in rule conditions
# ---------------------------------------------------------------

def test_rule_can_read_history():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="once-only",
            description="Only allowed once per session.",
            condition=lambda ctx: any(
                r.tool == "action" and not r.blocked for r in ctx.history
            ),
            action="block",
        )
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    result = action()
    assert result["status"] == "ok"

    with pytest.raises(BlockedToolCall):
        action()


def test_rule_counts_previous_calls():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="max-three",
            description="Maximum three calls per session.",
            condition=lambda ctx: sum(
                1 for r in ctx.history if r.tool == "action" and not r.blocked
            ) >= 3,
            action="block",
        )
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    action()
    action()
    action()

    with pytest.raises(BlockedToolCall):
        action()

    assert len([r for r in m.history if not r.blocked]) == 3


def test_blocked_calls_in_history_do_not_count_as_passed():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="block-negative",
            description="Blocked.",
            condition=lambda ctx: ctx.tool_call.arguments.value < 0,
            action="block",
        ),
        Rule(
            id="once-only",
            description="Only once.",
            condition=lambda ctx: any(
                r.tool == "action" and not r.blocked for r in ctx.history
            ),
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    # Blocked call — should not count toward the once-only limit
    with pytest.raises(BlockedToolCall):
        action(-1)

    # First successful call — should pass
    result = action(1)
    assert result["status"] == "ok"

    # Second successful call — now blocked by once-only
    with pytest.raises(BlockedToolCall):
        action(1)


# ---------------------------------------------------------------
# History across multiple tools
# ---------------------------------------------------------------

def test_history_shared_across_tools():
    m = make_manager()
    m.set_rules("tool_a", rules=[])
    m.set_rules("tool_b", rules=[])

    @secure(m)
    def tool_a() -> dict:
        return {"status": "ok"}

    @secure(m)
    def tool_b() -> dict:
        return {"status": "ok"}

    tool_a()
    tool_b()

    assert len(m.history) == 2
    assert m.history[0].tool == "tool_a"
    assert m.history[1].tool == "tool_b"


def test_blocked_call_record_attached_to_exception():
    m = make_manager()
    m.set_rules("action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action()

    # The exception carries the full record
    assert exc.value.record is not None
    assert exc.value.record.blocked is True
    assert exc.value.record.tool == "action"
