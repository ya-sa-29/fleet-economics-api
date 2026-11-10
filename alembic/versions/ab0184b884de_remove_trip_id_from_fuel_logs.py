"""Remove trip_id from fuel logs and update trip lifecycle.

Revision ID: ab0184b884de
Revises: b71c4e9a2f30
Create Date: 2026-11-10 10:14:33.727645
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ab0184b884de"
down_revision: Union[str, Sequence[str], None] = "b71c4e9a2f30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Видаляємо trip_id разом із пов'язаним FK через перебудову таблиці SQLite.
    with op.batch_alter_table("fuel_logs") as batch_op:
        batch_op.drop_column("trip_id")

    # Оновлюємо структуру рейсів відповідно до нової моделі.
    with op.batch_alter_table("trips") as batch_op:
        batch_op.add_column(
            sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False)
        )
        batch_op.add_column(
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.drop_column("status")


def downgrade() -> None:
    # Відновлюємо стару структуру trips.
    with op.batch_alter_table("trips") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.String(length=11),
                nullable=False,
                server_default="scheduled"
            )
        )
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("arrival_time")

    # Відновлюємо trip_id у fuel_logs.
    with op.batch_alter_table("fuel_logs") as batch_op:
        batch_op.add_column(
            sa.Column("trip_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_fuel_logs_trip_id_trips",
            "trips",
            ["trip_id"],
            ["id"]
        )