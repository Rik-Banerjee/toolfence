import pytest
from toolfence.toolfence import AgentManager
from toolfence.toolfence_secure import secure
from toolfence.toolfence_data import Rule, BlockedToolCall, BlockReason


# ---------------------------------------------------------------
# set_evidence / get in rules
# ---------------------------------------------------------------

def test_evidence_accessible_in_rule_condition():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("account_id", "ACC-001")

    received = []
    m.set_rules("action", rules=[
        Rule(
            id="capture-evidence",
            description="Capture.",
            condition=lambda ctx: received.append(ctx.evidence.account_id) or False,
            action="block",
        )
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    action()
    assert received == ["ACC-001"]


def test_evidence_updated_mid_session():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("limit", 100)

    m.set_rules("action", rules=[
        Rule(
            id="over-limit",
            description="Over limit.",
            condition=lambda ctx: ctx.tool_call.arguments.value > ctx.evidence.limit,
            action="block",
        )
    ])

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    # Under original limit
    result = action(50)
    assert result["status"] == "ok"

    # Raise the limit mid-session
    m.set_evidence("limit", 200)
    result = action(150)
    assert result["status"] == "ok"

    # Over new limit
    with pytest.raises(BlockedToolCall):
        action(250)


def test_multiple_evidence_fields():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("account_id", "ACC-001")
    m.set_evidence("email", "alice@example.com")
    m.set_evidence("tier", "premium")

    received = {}
    m.set_rules("action", rules=[
        Rule(
            id="capture-multi-evidence",
            description="Capture.",
            condition=lambda ctx: received.update({
                "account_id": ctx.evidence.account_id,
                "email": ctx.evidence.email,
                "tier": ctx.evidence.tier,
            }) or False,
            action="block",
        )
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    action()
    assert received["account_id"] == "ACC-001"
    assert received["email"] == "alice@example.com"
    assert received["tier"] == "premium"


# ---------------------------------------------------------------
# Evidence verification — argument vs evidence
# ---------------------------------------------------------------

def test_matching_argument_passes_evidence_check():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("account_id", "ACC-001")

    m.set_rules("action", rules=[
        Rule(
            id="account-mismatch",
            description="Account mismatch.",
            condition=lambda ctx: ctx.tool_call.arguments.account_id != ctx.evidence.account_id,
            action="block",
        )
    ])

    @secure(m)
    def action(account_id: str) -> dict:
        return {"status": "ok"}

    result = action("ACC-001")
    assert result["status"] == "ok"


def test_mismatched_argument_blocked_by_evidence_check():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("account_id", "ACC-001")

    m.set_rules("action", rules=[
        Rule(
            id="account-mismatch",
            description="Account mismatch.",
            condition=lambda ctx: ctx.tool_call.arguments.account_id != ctx.evidence.account_id,
            action="block",
        )
    ])

    @secure(m)
    def action(account_id: str) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action("ACC-999")
    assert exc.value.reason == BlockReason.RULE_TRIGGERED


def test_prompt_injection_caught_by_evidence():
    """
    Simulates an LLM being tricked into using a different account.
    The argument value comes from an untrusted source (prompt injection),
    but evidence was loaded from a verified source at session start.
    The mismatch rule catches it regardless of what the LLM passed.
    """
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_evidence("user_id", "USER-42")

    m.set_rules("transfer_funds", rules=[
        Rule(
            id="user-mismatch",
            description="Transfer source does not match verified session user.",
            condition=lambda ctx: ctx.tool_call.arguments.user_id != ctx.evidence.user_id,
            action="block",
        )
    ])

    @secure(m)
    def transfer_funds(user_id: str, amount: float) -> dict:
        return {"status": "transferred"}

    # Injected user_id — should be caught
    with pytest.raises(BlockedToolCall) as exc:
        transfer_funds("USER-99", 5000.0)
    assert exc.value.reason == BlockReason.RULE_TRIGGERED

    # Correct user_id — should pass
    result = transfer_funds("USER-42", 100.0)
    assert result["status"] == "transferred"


def test_evidence_not_set_returns_none_not_error():
    """
    Accessing an evidence field that was never set returns None
    (default Python attribute access) rather than raising an exception.
    Rules must handle this gracefully.
    """
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)

    m.set_rules("action", rules=[
        Rule(
            id="safe-evidence-check",
            description="Safe check.",
            condition=lambda ctx: getattr(ctx.evidence, "missing_field", None) is not None,
            action="block",
        )
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    # Should pass since missing_field was never set
    result = action()
    assert result["status"] == "ok"
