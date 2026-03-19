import pytest
from toolfence.toolfence import AgentManager
from toolfence.toolfence_secure import secure
from toolfence.toolfence_data import Rule
from toolfence.toolfence_config import ToolFenceSetupError


# ---------------------------------------------------------------
# Structural checks — rule ID
# ---------------------------------------------------------------

def test_empty_rule_id_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="", description="bad", condition=lambda ctx: True, action="block")
        ])


def test_whitespace_rule_id_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="   ", description="bad", condition=lambda ctx: True, action="block")
        ])


def test_duplicate_rule_id_same_tool_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="dup-id", description="first", condition=lambda ctx: True, action="block"),
            Rule(id="dup-id", description="second", condition=lambda ctx: True, action="block"),
        ])


def test_duplicate_rule_id_across_tools_raises():
    m = AgentManager()
    m.set_rules("tool_a", rules=[
        Rule(id="shared-id", description="first", condition=lambda ctx: True, action="block")
    ])
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("tool_b", rules=[
            Rule(id="shared-id", description="second", condition=lambda ctx: True, action="block")
        ])


def test_unique_rule_ids_pass():
    m = AgentManager()
    m.set_rules("action", rules=[
        Rule(id="rule-one", description="first", condition=lambda ctx: True, action="block"),
        Rule(id="rule-two", description="second", condition=lambda ctx: False, action="block"),
    ])


# ---------------------------------------------------------------
# Structural checks — rule condition
# ---------------------------------------------------------------

def test_non_callable_condition_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="bad-cond", description="bad", condition="not callable", action="block")
        ])


def test_condition_zero_args_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="bad-arity", description="bad", condition=lambda: True, action="block")
        ])


def test_condition_two_args_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="bad-arity-2", description="bad", condition=lambda a, b: True, action="block")
        ])


def test_condition_one_arg_passes():
    m = AgentManager()
    m.set_rules("action", rules=[
        Rule(id="good-cond", description="good", condition=lambda ctx: True, action="block")
    ])


# ---------------------------------------------------------------
# Structural checks — rule action
# ---------------------------------------------------------------

def test_invalid_action_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[
            Rule(id="bad-action", description="bad", condition=lambda ctx: True, action="prevent")
        ])


def test_block_action_passes():
    m = AgentManager()
    m.set_rules("action", rules=[
        Rule(id="valid-block", description="ok", condition=lambda ctx: True, action="block")
    ])


def test_escalate_action_passes():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_rules("action", rules=[
        Rule(id="valid-escalate", description="ok", condition=lambda ctx: True, action="escalate")
    ])


# ---------------------------------------------------------------
# Structural checks — approval handler
# ---------------------------------------------------------------

def test_non_callable_default_handler_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_default_approval_handler("not a function")


def test_handler_zero_args_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_default_approval_handler(lambda: True)


def test_handler_two_args_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_default_approval_handler(lambda a, b: True)


def test_handler_one_arg_passes():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)


def test_non_callable_tool_specific_handler_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[], approval_handler="not a function")


def test_tool_specific_handler_wrong_arity_raises():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_rules("action", rules=[], approval_handler=lambda: True)


def test_callable_class_handler_passes():
    class MyHandler:
        def __call__(self, ctx):
            return True

    m = AgentManager()
    m.set_default_approval_handler(MyHandler())


def test_callable_class_handler_wrong_arity_raises():
    class BadHandler:
        def __call__(self):
            return True

    m = AgentManager()
    with pytest.raises(ToolFenceSetupError):
        m.set_default_approval_handler(BadHandler())


# ---------------------------------------------------------------
# Completeness checks — manager.validate()
# ---------------------------------------------------------------

def test_validate_escalation_rule_no_handler_raises():
    m = AgentManager()
    # No default handler, no tool-specific handler
    m.set_rules("action", rules=[
        Rule(id="escalate", description="escalate", condition=lambda ctx: True, action="escalate")
    ], approval_handler="default")

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    with pytest.raises(ToolFenceSetupError):
        m.validate()


def test_validate_escalation_with_default_handler_passes():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_rules("action", rules=[
        Rule(id="escalate", description="escalate", condition=lambda ctx: True, action="escalate")
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    m.validate()  # should not raise


def test_validate_escalation_with_specific_handler_passes():
    m = AgentManager()
    # No default handler, but tool-specific one provided
    m.set_rules("action", rules=[
        Rule(id="escalate", description="escalate", condition=lambda ctx: True, action="escalate")
    ], approval_handler=lambda ctx: True)

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    m.validate()  # should not raise


def test_validate_async_handler_on_sync_tool_raises():
    m = AgentManager()

    async def async_handler(ctx):
        return True

    m.set_default_approval_handler(async_handler)
    m.set_rules("action", rules=[])

    @secure(m)
    def action() -> dict:  # sync tool
        return {"status": "ok"}

    with pytest.raises(ToolFenceSetupError):
        m.validate()


def test_validate_clean_config_passes():
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    m.set_rules("action", rules=[
        Rule(id="block-rule", description="block", condition=lambda ctx: False, action="block")
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    m.validate()  # should not raise


# ---------------------------------------------------------------
# Completeness checks — warnings (validate does not raise)
# ---------------------------------------------------------------

def test_validate_set_rules_without_secure_warns(capsys):
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    # set_rules for a tool that has no @secure decorator
    m.set_rules("ghost_tool", rules=[])

    m.validate()
    output = capsys.readouterr().out
    assert "ghost_tool" in output


def test_validate_secure_without_set_rules_warns(capsys):
    m = AgentManager()

    @secure(m)
    def orphan_tool() -> dict:
        return {"status": "ok"}

    m.validate()
    output = capsys.readouterr().out
    assert "orphan_tool" in output


def test_validate_dead_default_handler_warns(capsys):
    m = AgentManager()
    m.set_default_approval_handler(lambda ctx: True)
    # No escalation rules anywhere
    m.set_rules("action", rules=[
        Rule(id="block-only", description="block", condition=lambda ctx: False, action="block")
    ])

    @secure(m)
    def action() -> dict:
        return {"status": "ok"}

    m.validate()
    output = capsys.readouterr().out
    assert "never be called" in output


# ---------------------------------------------------------------
# Error messages contain useful context
# ---------------------------------------------------------------

def test_error_message_contains_tool_name():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError) as exc:
        m.set_rules("my_tool", rules=[
            Rule(id="bad", description="bad", condition=lambda: True, action="block")
        ])
    assert "my_tool" in exc.value.message


def test_error_message_contains_rule_id():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError) as exc:
        m.set_rules("action", rules=[
            Rule(id="my-rule-id", description="bad", condition=lambda: True, action="block")
        ])
    assert "my-rule-id" in exc.value.message


def test_multiple_errors_reported_at_once():
    m = AgentManager()
    with pytest.raises(ToolFenceSetupError) as exc:
        m.set_rules("action", rules=[
            Rule(id="bad-one", description="bad", condition=lambda: True, action="block"),
            Rule(id="bad-two", description="bad", condition=lambda: True, action="block"),
        ])
    # Both rule IDs should appear in the single error message
    assert "bad-one" in exc.value.message
    assert "bad-two" in exc.value.message