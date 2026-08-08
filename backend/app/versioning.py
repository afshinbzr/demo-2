"""Version history for corrected line items (spec 1.4 — keep version history,
soft-delete instead of hard-delete)."""

from sqlalchemy.orm import Session

from .audit import log_action
from .models import LineItem, User


def correct_line_item(
    db: Session,
    old_item: LineItem,
    *,
    new_value: float | None = None,
    new_raw_label: str | None = None,
    new_unit: str | None = None,
    new_period: str | None = None,
    user: User,
    source: str,
) -> LineItem:
    """Soft-delete `old_item` and insert a new versioned row with the correction.
    Never overwrites in place, so the full history stays queryable."""
    old_snapshot = {
        "value": old_item.value,
        "raw_label": old_item.raw_label,
        "unit": old_item.unit,
        "period": old_item.period,
        "version": old_item.version,
    }
    old_item.is_deleted = True

    new_item = LineItem(
        statement_id=old_item.statement_id,
        field_name=old_item.field_name,
        raw_label=new_raw_label if new_raw_label is not None else old_item.raw_label,
        value=new_value if new_value is not None else old_item.value,
        unit=new_unit if new_unit is not None else old_item.unit,
        period=new_period if new_period is not None else old_item.period,
        confidence="manual",
        is_outlier=False,
        version=old_item.version + 1,
    )
    db.add(new_item)
    db.flush()

    log_action(
        db,
        entity_type="line_item",
        entity_id=new_item.id,
        action="update",
        user=user,
        old_value=old_snapshot,
        new_value={
            "value": new_item.value,
            "raw_label": new_item.raw_label,
            "unit": new_item.unit,
            "period": new_item.period,
            "version": new_item.version,
        },
        detail=f"Corrected via {source} (superseded line_item #{old_item.id})",
    )
    db.commit()
    db.refresh(new_item)
    return new_item
