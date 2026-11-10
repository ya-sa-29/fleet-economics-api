
"""Seed Ukrainian oblast centers

Revision ID: b71c4e9a2f30
Revises: 42d7303d3ec7
Create Date: 2026-11-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b71c4e9a2f30"
down_revision: Union[str, Sequence[str], None] = "42d7303d3ec7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LOCATIONS = [
    ("Вінниця", "vinnytsia"),
    ("Луцьк", "lutsk"),
    ("Дніпро", "dnipro"),
    ("Донецьк", "donetsk"),
    ("Житомир", "zhytomyr"),
    ("Ужгород", "uzhhorod"),
    ("Запоріжжя", "zaporizhzhia"),
    ("Івано-Франківськ", "ivano-frankivsk"),
    ("Київ", "kyiv"),
    ("Кропивницький", "kropyvnytskyi"),
    ("Луганськ", "luhansk"),
    ("Львів", "lviv"),
    ("Миколаїв", "mykolaiv"),
    ("Одеса", "odesa"),
    ("Полтава", "poltava"),
    ("Рівне", "rivne"),
    ("Суми", "sumy"),
    ("Тернопіль", "ternopil"),
    ("Харків", "kharkiv"),
    ("Херсон", "kherson"),
    ("Хмельницький", "khmelnytskyi"),
    ("Черкаси", "cherkasy"),
    ("Чернівці", "chernivtsi"),
    ("Чернігів", "chernihiv"),
]


def upgrade() -> None:
    locations = sa.table(
        "locations",
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
    )

    bind = op.get_bind()

    existing = bind.execute(
        sa.select(locations.c.name, locations.c.slug)
    ).all()

    existing_names = {row.name for row in existing}
    existing_slugs = {row.slug for row in existing}

    new_locations = [
        {"name": name, "slug": slug}
        for name, slug in LOCATIONS
        if name not in existing_names and slug not in existing_slugs
    ]

    if new_locations:
        op.bulk_insert(locations, new_locations)


def downgrade() -> None:
    # Довідникові записи можуть бути використані рейсами.
    # Не видаляємо їх автоматично, щоб не пошкодити дані.
    pass
