from toolfence import secure, AgentManager, Rule, BlockedToolCall

# --- ToolFence setup ---
manager = AgentManager()
manager.set_default_approval_handler(lambda ctx: True)

# Load verified data from your database and set as evidence
manager.set_evidence("account_id", "ACC-001")
manager.set_evidence("email",      "alice@example.com")

# --- Rules ---
manager.set_rules(
    tool = "transfer_funds",
    rules=[
        Rule(
            id="transfer-account-mismatch",
            description="Transfer source does not match the verified session account.",
            condition=lambda ctx: ctx.tool_call.arguments.from_account != ctx.evidence.account_id,
            action="block",
        ),
    ],
)

manager.set_rules(
    tool = "update_email",
    rules=[
        Rule(
            id="email-account-mismatch",
            description="Cannot update email on an account that does not belong to this session.",
            condition=lambda ctx: ctx.tool_call.arguments.account_id != ctx.evidence.account_id,
            action="block",
        ),
    ],
)

# --- Tools ---
@secure(manager)
def transfer_funds(from_account: str, to_account: str, amount: float) -> dict:
    return {"status": "transferred"}

@secure(manager)
def update_email(account_id: str, new_email: str) -> dict:
    return {"status": "updated"}

manager.validate()

# Passes — from_account matches evidence
transfer_funds("ACC-001", "ACC-002", 100.0)

# Blocked — injected account does not match evidence
try:
    transfer_funds("ACC-ATTACKER", "ACC-002", 5000.0)
except BlockedToolCall as e:
    print(e.message)
# Output: Transfer source does not match the verified session account.