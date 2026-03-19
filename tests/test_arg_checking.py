import pytest
from toolfence.toolfence import AgentManager
from toolfence.toolfence_secure import secure
from toolfence.toolfence_data import BlockedToolCall, BlockReason


# ---------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------

def make_manager(arg_checking=True):
    m = AgentManager()
    m.set_rules("action", rules=[], arg_checking=arg_checking)
    return m


# ---------------------------------------------------------------
# Missing arguments
# ---------------------------------------------------------------

def test_missing_required_argument():
    m = make_manager()

    @secure(m)
    def action(name: str, value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action("only_name")
    assert exc.value.reason == BlockReason.MISSING_ARGUMENT
    assert "value" in exc.value.message


def test_all_arguments_provided_passes():
    m = make_manager()

    @secure(m)
    def action(name: str, value: int) -> dict:
        return {"status": "ok"}

    result = action("hello", 42)
    assert result["status"] == "ok"


def test_missing_argument_tool_body_never_runs():
    m = make_manager()
    ran = []

    @secure(m)
    def action(name: str, value: int) -> dict:
        ran.append(True)
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall):
        action("only_name")

    assert ran == []


# ---------------------------------------------------------------
# Wrong types
# ---------------------------------------------------------------

def test_wrong_type_is_caught():
    m = make_manager()

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action("not_an_int")
    assert exc.value.reason == BlockReason.INVALID_ARGUMENT_TYPE
    assert "value" in exc.value.message


def test_wrong_type_message_shows_expected_and_got():
    m = make_manager()

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action("not_an_int")
    assert "int" in exc.value.message
    assert "str" in exc.value.message


def test_correct_type_passes():
    m = make_manager()

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    result = action(5)
    assert result["status"] == "ok"


def test_multiple_params_wrong_type_on_second():
    m = make_manager()

    @secure(m)
    def action(name: str, value: int) -> dict:
        return {"status": "ok"}

    with pytest.raises(BlockedToolCall) as exc:
        action("valid", "not_an_int")
    assert exc.value.reason == BlockReason.INVALID_ARGUMENT_TYPE
    assert "value" in exc.value.message


def test_unannotated_param_skips_type_check():
    m = make_manager()

    @secure(m)
    def action(value) -> dict:  # no annotation
        return {"status": "ok"}

    result = action("anything")
    assert result["status"] == "ok"


# ---------------------------------------------------------------
# Arg checking disabled
# ---------------------------------------------------------------


def test_arg_checking_disabled_wrong_type_passes():
    m = make_manager(arg_checking=False)

    @secure(m)
    def action(value: int) -> dict:
        return {"status": "ok"}

    result = action("not_an_int")
    assert result["status"] == "ok"


# ---------------------------------------------------------------
# Default arguments
# ---------------------------------------------------------------

def test_default_argument_not_required():
    m = make_manager()

    @secure(m)
    def action(name: str, value: int = 10) -> dict:
        return {"status": "ok", "value": value}

    result = action("hello")
    assert result["value"] == 10


def test_default_argument_overridden():
    m = make_manager()

    @secure(m)
    def action(name: str, value: int = 10) -> dict:
        return {"status": "ok", "value": value}

    result = action("hello", 99)
    assert result["value"] == 99
