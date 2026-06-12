"""
Platform admin endpoints. Everything here is super-admin only and meant
for operational diagnostics, not tenant-facing features.
"""

from fastapi import APIRouter, Depends

from app.core.permissions import require_superadmin
from app.core.tenant import denial_counters_snapshot
from app.models.user import User


router = APIRouter(prefix="/admin", tags=["Admin (Platform)"])


@router.get("/metrics", summary="In-process denial counters (super-admin only)")
async def get_metrics(_: User = Depends(require_superadmin)):
    """
    Snapshot of `module_access_denied` and `role_permission_denied` counts
    since the app booted. Surfaces the noisy tenants first, which is what
    we actually want when diagnosing 'nobody in org X can use feature Y'.
    """
    counters = denial_counters_snapshot()
    totals: dict[str, int] = {}
    for row in counters:
        totals[row["event"]] = totals.get(row["event"], 0) + row["count"]
    return {"totals": totals, "by_bucket": counters}
