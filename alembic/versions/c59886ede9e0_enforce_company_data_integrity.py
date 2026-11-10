"""enforce company data integrity

Revision ID: c59886ede9e0
Revises: ab0184b884de
Create Date: 2026-11-10 10:53:00.298118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c59886ede9e0'
down_revision: Union[str, Sequence[str], None] = 'ab0184b884de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Спочатку створюємо унікальні індекси на батьківських таблицях.
    op.create_index(
        "uq_users_id_company",
        "users",
        ["id", "company_id"],
        unique=True,
    )

    op.create_index(
        "uq_vehicles_id_company",
        "vehicles",
        ["id", "company_id"],
        unique=True,
    )

    # Старі FK не мали імен.
    # Naming convention дозволяє Alembic знайти їх під час batch-перебудови.
    fk_naming = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    }

    # 2. FuelLog: vehicle_id -> (vehicle_id, company_id)
    with op.batch_alter_table(
        "fuel_logs",
        naming_convention=fk_naming,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_fuel_logs_vehicle_id_vehicles",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_fuel_logs_vehicle_company",
            "vehicles",
            ["vehicle_id", "company_id"],
            ["id", "company_id"],
        )

    # 3. MaintenanceLog: vehicle_id -> (vehicle_id, company_id)
    with op.batch_alter_table(
        "maintenance_logs",
        naming_convention=fk_naming,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_maintenance_logs_vehicle_id_vehicles",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_maintenance_logs_vehicle_company",
            "vehicles",
            ["vehicle_id", "company_id"],
            ["id", "company_id"],
        )

    # 4. Trip: vehicle_id і driver_id -> складені FK
    with op.batch_alter_table(
        "trips",
        naming_convention=fk_naming,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_trips_vehicle_id_vehicles",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_trips_driver_id_users",
            type_="foreignkey",
        )

        batch_op.create_foreign_key(
            "fk_trips_vehicle_company",
            "vehicles",
            ["vehicle_id", "company_id"],
            ["id", "company_id"],
        )

        batch_op.create_foreign_key(
            "fk_trips_driver_company",
            "users",
            ["driver_id", "company_id"],
            ["id", "company_id"],
        )


def downgrade() -> None:
    fk_naming = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"
    }

    # 1. Повертаємо старі FK у trips.
    with op.batch_alter_table(
        "trips",
        naming_convention=fk_naming,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_trips_vehicle_company",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_trips_driver_company",
            type_="foreignkey",
        )

        batch_op.create_foreign_key(
            "fk_trips_vehicle_id_vehicles",
            "vehicles",
            ["vehicle_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_trips_driver_id_users",
            "users",
            ["driver_id"],
            ["id"],
        )

    # 2. Повертаємо старий FK у maintenance_logs.
    with op.batch_alter_table(
        "maintenance_logs",
        naming_convention=fk_naming,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_maintenance_logs_vehicle_company",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_maintenance_logs_vehicle_id_vehicles",
            "vehicles",
            ["vehicle_id"],
            ["id"],
        )

    # 3. Повертаємо старий FK у fuel_logs.
    with op.batch_alter_table(
        "fuel_logs",
        naming_convention=fk_naming,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_fuel_logs_vehicle_company",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_fuel_logs_vehicle_id_vehicles",
            "vehicles",
            ["vehicle_id"],
            ["id"],
        )

    # 4. Видаляємо унікальні індекси.
    op.drop_index("uq_vehicles_id_company", table_name="vehicles")
    op.drop_index("uq_users_id_company", table_name="users")