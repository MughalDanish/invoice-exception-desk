"""Supervisor plans may reorder work, but cannot omit or change mandatory checks."""

from app.modules.investigation.schemas import InvestigationPlan, InvoiceSnapshot, PlanTask

ROUTES = {
    "TOTAL_MISMATCH": ("financial", "arithmetic", ("get_rule_results", "get_invoice_snapshot")),
    "DUPLICATE_INVOICE": (
        "financial",
        "duplicate",
        ("get_rule_results", "find_duplicate_candidates"),
    ),
    "UNAPPROVED_VENDOR": ("supplier", "supplier", ("get_rule_results", "get_supplier_policy")),
    "AMOUNT_OUTLIER": (
        "supplier",
        "outlier",
        ("get_rule_results", "get_supplier_policy", "get_supplier_history"),
    ),
}


def mandatory_plan(snapshot: InvoiceSnapshot) -> InvestigationPlan:
    tasks = []
    for rule in snapshot.blockers:
        role, kind, tools = ROUTES.get(
            rule.code, ("financial", "unsupported", ("get_rule_results",))
        )
        tasks.append(
            PlanTask(task_id=str(rule.id), rule_id=rule.id, role=role, kind=kind, tools=tools)
        )
    if snapshot.documents is not None:
        tasks.append(
            PlanTask(
                task_id=f"documents:{snapshot.invoice_id}",
                rule_id=snapshot.blockers[0].id,
                role="documents",
                kind="documents",
                tools=("get_supporting_documents",),
            )
        )
    return InvestigationPlan(tasks=tuple(tasks))


def validate_plan(snapshot: InvoiceSnapshot, proposed: object) -> InvestigationPlan:
    plan = InvestigationPlan.model_validate(proposed)
    expected = {task.task_id: task for task in mandatory_plan(snapshot).tasks}
    actual = {task.task_id: task for task in plan.tasks}
    if len(actual) != len(plan.tasks) or actual != expected:
        raise ValueError("Invalid investigation plan: mandatory tasks must match")
    return plan
