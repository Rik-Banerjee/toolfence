import pytest
import asyncio
from toolfence.toolfence import AgentManager
from toolfence.toolfence_secure import secure
from toolfence.toolfence_data import Rule, BlockedToolCall, BlockReason


# ---------------------------------------------------------------
# Basic async tool behaviour
# ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_tool_passes():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_rules("action", rules=[])

    @secure(m)
    async def action(value: int) -> dict:
        return {"status": "ok", "value": value}

    result = await action(42)
    assert result["status"] == "ok"
    assert result["value"] == 42


@pytest.mark.asyncio
async def test_async_tool_blocked_by_rule():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_rules("action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    async def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        await action(1)
    assert exc.value.reason == BlockReason.RULE_TRIGGERED


@pytest.mark.asyncio
async def test_async_tool_body_never_runs_when_blocked():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    ran = []

    m.set_rules("action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    async def action() -> dict:
        ran.append(True)
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall):
        await action()

    assert ran == []


# ---------------------------------------------------------------
# Async tool + async approval handler
# ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_tool_with_async_handler_approves():
    m = AgentManager()

    async def async_handler(ctx):
        return True

    m.set_default_approval_handler(async_handler)
    m.set_rules("action", rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])

    @secure(m)
    async def action() -> dict:
        return {"status": "ok"}

    result = await action()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_async_tool_with_async_handler_denies():
    m = AgentManager()

    async def async_handler(ctx):
        return False

    m.set_default_approval_handler(async_handler)
    m.set_rules("action", rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])

    @secure(m)
    async def action() -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        await action()
    assert exc.value.reason == BlockReason.APPROVAL_DENIED


# ---------------------------------------------------------------
# Async tool + sync approval handler
# ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_tool_with_sync_handler_approves():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)  # sync handler on async tool
    m.set_rules("action", rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])

    @secure(m)
    async def action() -> dict:
        return {"status": "ok"}

    result = await action()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_async_tool_with_sync_handler_denies():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: False)
    m.set_rules("action", rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])

    @secure(m)
    async def action() -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        await action()
    assert exc.value.reason == BlockReason.APPROVAL_DENIED


# ---------------------------------------------------------------
# Async tool arg checking
# ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_tool_missing_argument_blocked():
    m = AgentManager()
    m.set_rules("action", rules=[])

    @secure(m)
    async def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        await action()
    assert exc.value.reason == BlockReason.MISSING_ARGUMENT


@pytest.mark.asyncio
async def test_async_tool_wrong_type_blocked():
    m = AgentManager()
    m.set_rules("action", rules=[])

    @secure(m)
    async def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        await action("not_an_int")
    assert exc.value.reason == BlockReason.INVALID_ARGUMENT_TYPE


# ---------------------------------------------------------------
# Async tool history
# ---------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_tool_passed_call_recorded():
    m = AgentManager()
    m.set_rules("action", rules=[])

    @secure(m)
    async def action() -> dict:
        return {"status": "ok"}

    await action()
    assert len(m.history) == 1
    assert m.history[0].blocked is False


@pytest.mark.asyncio
async def test_async_tool_blocked_call_recorded():
    m = AgentManager()
    m.set_rules("action", rules=[
        Rule(
            id="always-block",
            description="Always blocked.",
            condition=lambda ctx: True,
            action="block",
        )
    ])

    @secure(m)
    async def action() -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall):
        await action()

    assert len(m.history) == 1
    assert m.history[0].blocked is True


# ---------------------------------------------------------------
# Async handler on sync tool blocked at runtime
# ---------------------------------------------------------------

def test_async_handler_on_sync_tool_raises_at_runtime():
    """
    If validate() was not called, async handler mismatch is still
    caught the first time the tool is called.
    """
    m = AgentManager()

    async def async_handler(ctx):
        return True

    m.set_default_approval_handler(async_handler)
    m.set_rules("action", rules=[
        Rule(
            id="always-escalate",
            description="Always escalated.",
            condition=lambda ctx: True,
            action="escalate",
        )
    ])

    @secure(m)
    def action() -> dict:  # sync
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action()
    assert exc.value.reason == BlockReason.ASYNC_HANDLER_MISMATCH
