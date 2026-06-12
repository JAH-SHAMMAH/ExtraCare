"""
Business module AI handler.

Same contract as school/hospital. The templates focus on sales and
inventory digests because those are the two dashboards the business
module surfaces today — if a new area lands (e.g. HR), add a task
here rather than reaching for a free-form prompt.

Supported tasks:
  • summarise_sales    — period sales digest
  • summarise_inventory — stock-level snapshot
  • suggest            — operational nudge for an owner/manager
"""

from __future__ import annotations

from typing import Any


SUPPORTED_TASKS = ("summarise_sales", "summarise_inventory", "suggest")


def _summarise_sales(context: dict[str, Any]) -> str:
    period = context.get("period") or "the selected period"
    total = context.get("total_revenue")
    orders = context.get("order_count")
    top_product = context.get("top_product")
    currency = context.get("currency") or "NGN"

    lines = [f"Sales summary for {period}."]
    if total is not None:
        lines.append(f"Total revenue: {currency} {total}.")
    if orders is not None:
        lines.append(f"Orders fulfilled: {orders}.")
    if top_product:
        lines.append(f"Top product: {top_product}.")
    if len(lines) == 1:
        lines.append("No sales data supplied — pass total_revenue/order_count for a fuller digest.")
    return " ".join(lines)


def _summarise_inventory(context: dict[str, Any]) -> str:
    items = context.get("items") or []
    low_stock = [i for i in items if isinstance(i, dict) and i.get("quantity") is not None and i.get("reorder_at") is not None and i["quantity"] <= i["reorder_at"]]
    total = len(items)
    if not items:
        return "Inventory snapshot: no items supplied."
    head = f"Inventory snapshot: {total} item(s) tracked."
    if low_stock:
        names = ", ".join(str(i.get("name") or i.get("sku") or "item") for i in low_stock[:5])
        return f"{head} {len(low_stock)} below reorder threshold ({names})."
    return f"{head} All items above their reorder thresholds."


def _suggest(context: dict[str, Any]) -> str:
    audience = context.get("audience") or "the operations lead"
    goal = context.get("goal") or "tighten cash flow this week"
    return (
        f"Suggestion for {audience}: {goal}. "
        "Pick one lever (pricing, stock, collections), set a 7-day target, and review on Friday."
    )


_DISPATCH = {
    "summarise_sales": _summarise_sales,
    "summarise_inventory": _summarise_inventory,
    "suggest": _suggest,
}


def handle(task: str, context: dict[str, Any]) -> str:
    fn = _DISPATCH.get(task)
    if fn is None:
        raise ValueError(f"Unsupported business task: {task!r}. Supported: {SUPPORTED_TASKS}")
    return fn(context or {})
