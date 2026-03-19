import inspect
from functools import wraps
from typing import Callable, Dict, List

from .toolfence_data import (
    BlockReason,
    BlockedToolCall,
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
from .toolfence import AgentManager



def _block(manager: AgentManager, tool_call: ToolCall, reason: BlockReason, message: str) -> None:
    record = _create_tool_call_record(tool_call, True, reason.value)
    manager.history.append(record)
    raise BlockedToolCall(tool_call.tool, reason, message, record)


def _pass(manager: AgentManager, tool_call: ToolCall) -> None:
    record = _create_tool_call_record(tool_call, False, "")
    manager.history.append(record)


def _build_tool_call(fn_name: str, signature, args, kwargs) -> ToolCall:
    bound = signature.bind_partial(*args, **kwargs)
    bound.apply_defaults()

    arguments = DynamicData()
    for key, value in bound.arguments.items():
        setattr(arguments, key, value)

    return ToolCall(tool=fn_name, arguments=arguments)


def _build_context(manager: AgentManager, tool_call: ToolCall) -> Context:
    return Context(
        tool_call=tool_call,
        evidence=manager.evidence,
        history=manager.history,
    )


def _build_tool(tool_name: str, parameters: Dict, is_async: bool) -> Tool:
    filtered_parameters = {}

    for parameter in parameters:
        parameter_data = {'type': 'no_type', 'hasDefault': False}

        annotation = parameters[parameter].annotation
        default = parameters[parameter].default

        if annotation != inspect._empty:
            parameter_data['type'] = annotation

        if default != inspect._empty:
            parameter_data['hasDefault'] = True

        filtered_parameters[parameter] = parameter_data

    return Tool(
        name=tool_name,
        parameters=filtered_parameters,
        is_async=is_async,
    )


def _validate_approval_handler(
    manager: AgentManager,
    tool_call: ToolCall,
    is_async_tool: bool,
) -> Callable:
    approval_handler = manager.tool_approval_handlers.get(tool_call.tool)

    if approval_handler == "default":
        if manager.default_approval_handler is None:
            _block(
                manager, tool_call,
                BlockReason.NO_APPROVAL_HANDLER,
                f'No default approval handler set. Provide one via set_default_approval_handler().',
            )
        approval_handler = manager.default_approval_handler

    if not is_async_tool and inspect.iscoroutinefunction(approval_handler):
        _block(
            manager, tool_call,
            BlockReason.ASYNC_HANDLER_MISMATCH,
            f'Approval handler for "{tool_call.tool}" is async but the tool is sync. '
            f'Use a sync handler or make the tool async.',
        )

    return approval_handler


def _execute_validation(manager: AgentManager, tool_call: ToolCall, context: Context) -> ValidationResult:
    block_result = run_block_rules(
        context,
        manager.block_rules.get(tool_call.tool, []),
    )

    if block_result.blocked:
        return block_result

    return run_escalation_rules(
        context,
        manager.escalation_rules.get(tool_call.tool, []),
    )


def _arg_checking(manager: AgentManager, tool_name: str, tool_call: ToolCall) -> None:
    if tool_name not in manager.arg_checking_tools:
        return

    arguments = dict(vars(tool_call.arguments).items())
    parameters = manager.tools[tool_name].parameters


    for parameter in parameters:
        if parameter not in arguments:
            _block(
                manager, tool_call,
                BlockReason.MISSING_ARGUMENT,
                f'"{tool_call.tool}" is missing required argument "{parameter}".',
            )
        else:
            expected_type = parameters[parameter]['type']
            if expected_type != 'no_type':
                if not isinstance(arguments[parameter], expected_type):
                    _block(
                        manager, tool_call,
                        BlockReason.INVALID_ARGUMENT_TYPE,
                        f'"{tool_call.tool}" received invalid type for argument "{parameter}". '
                        f'Expected {expected_type.__name__}, got {type(arguments[parameter]).__name__}.',
                    )



# @secure decorator
def secure(manager: AgentManager):
    def decorator(fn):
        signature = inspect.signature(fn)
        tool_name = fn.__name__
        parameters = dict(signature.parameters)
        is_async = inspect.iscoroutinefunction(fn)

        manager.tools[tool_name] = _build_tool(tool_name, parameters, is_async)

        # Build sync wrapper
        if not is_async:

            @wraps(fn)
            def wrapper(*args, **kwargs):
                tool_call = _build_tool_call(tool_name, signature, args, kwargs)
                _arg_checking(manager, tool_name, tool_call)

                context = _build_context(manager, tool_call)
                result = _execute_validation(manager, tool_call, context)

                if result.blocked:
                    _block(
                        manager, tool_call,
                        BlockReason.RULE_TRIGGERED,
                        f'Rule "{result.rule_id}" blocked this call: {result.message}',
                    )

                if result.requires_approval:
                    approval_handler = _validate_approval_handler(manager, tool_call, False)
                    if not approval_handler(context):
                        _block(
                            manager, tool_call,
                            BlockReason.APPROVAL_DENIED,
                            f'"{tool_call.tool}" was denied by the approval handler.',
                        )

                result = fn(*args, **kwargs)
                _pass(manager, tool_call)
                return result

            return wrapper

        # Build async wrapper
        else:

            @wraps(fn)
            async def wrapper(*args, **kwargs):
                tool_call = _build_tool_call(tool_name, signature, args, kwargs)
                _arg_checking(manager, tool_name, tool_call)

                context = _build_context(manager, tool_call)
                result = _execute_validation(manager, tool_call, context)

                if result.blocked:
                    _block(
                        manager, tool_call,
                        BlockReason.RULE_TRIGGERED,
                        f'Rule "{result.rule_id}" blocked this call: {result.message}',
                    )

                if result.requires_approval:
                    approval_handler = _validate_approval_handler(manager, tool_call, True)
                    is_async_handler = inspect.iscoroutinefunction(approval_handler)

                    approved = (
                        await approval_handler(context)
                        if is_async_handler
                        else approval_handler(context)
                    )

                    if not approved:
                        _block(
                            manager, tool_call,
                            BlockReason.APPROVAL_DENIED,
                            f'"{tool_call.tool}" was denied by the approval handler.',
                        )

                result = await fn(*args, **kwargs)
                _pass(manager, tool_call)
                return result

            return wrapper

    return decorator