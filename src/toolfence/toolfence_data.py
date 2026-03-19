from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Callable, List
import uuid


class DynamicData:
    pass

@dataclass(frozen=True)
class ToolCall:
    tool: str
    arguments: DynamicData


@dataclass(frozen=True)
class Tool:
    name: str
    parameters: Dict[str, Dict]
    is_async: bool


@dataclass(frozen=True)
class ToolCallRecord:
    uuid: str
    tool: str
    arguments: DynamicData
    timestamp: datetime
    blocked: bool
    reason: str


@dataclass(frozen=True)
class Context:
    tool_call: ToolCall
    evidence: DynamicData
    history: List[ToolCallRecord]


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    condition: Callable[[Context], bool]
    action: str  # "block" | "escalate"

@dataclass(frozen=True)
class ValidationResult:
    blocked: bool
    requires_approval: bool
    message: str
    rule_id: str | None = None


class BlockReason(str, Enum):
    RULE_TRIGGERED         = "RULE_TRIGGERED"
    APPROVAL_DENIED        = "APPROVAL_DENIED"
    NO_APPROVAL_HANDLER    = "NO_APPROVAL_HANDLER"
    ASYNC_HANDLER_MISMATCH = "ASYNC_HANDLER_MISMATCH"
    MISSING_ARGUMENT       = "MISSING_ARGUMENT"
    INVALID_ARGUMENT_TYPE  = "INVALID_ARGUMENT_TYPE"



class BlockedToolCall(Exception):
    def __init__(self, tool: str, reason: BlockReason, message: str, record: ToolCallRecord):
        self.tool = tool
        self.reason = reason
        self.message = message
        self.record = record
        super().__init__(f"[{reason}] {tool}: {message}")



def _create_tool_call_record(
    tool_call: ToolCall,
    blocked: bool,
    reason: str,
) -> ToolCallRecord:
    return ToolCallRecord(
        uuid=str(uuid.uuid4()),
        tool=tool_call.tool,
        arguments=tool_call.arguments,
        timestamp=datetime.utcnow(),
        blocked=blocked,
        reason=reason,
    )

