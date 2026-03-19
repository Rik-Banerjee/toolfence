from toolfence import secure, AgentManager, Rule, BlockedToolCall

# --- ToolFence setup ---
manager = AgentManager()
manager.set_default_approval_handler(lambda ctx: input(f'Do you approve {ctx.tool_call.tool} to execute? ') == 'yes')

# --- Rules ---
manager.set_rules(
    tool = "delete_record",
    rules=[
        Rule(
            id="block-system-records",
            description="System records cannot be deleted.",
            condition=lambda ctx: ctx.tool_call.arguments.record_id.startswith("SYS-"),
            action="block",
        ),
        Rule(
            id="escalate-all-deletions",
            description="All deletions require approval.",
            condition=lambda ctx: True,
            action="escalate",
        ),
    ],
)

# --- Tool ---
@secure(manager)
def delete_record(record_id: str) -> dict:
    return {"status": "deleted", "record_id": record_id}

manager.validate()

try:
    delete_record("SYS-001")
except BlockedToolCall as e:
    print(f"Blocked: {e.message}")
# Output: Blocked: System records cannot be deleted.

try:
    delete_record("REC-042")
except BlockedToolCall as e:
    print(f"Blocked: {e.message}")
# Output: (approval prompt shown, approved, tool runs)