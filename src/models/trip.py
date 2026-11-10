import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
)
from sqlalchemy.sql import func
from src.models.base import Base


class TripStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Trip(Base):
    __tablename__ = "trips"

    __table_args__ = (
        ForeignKeyConstraint(
            ["vehicle_id", "company_id"],
            ["vehicles.id", "vehicles.company_id"],
            name="fk_trips_vehicle_company",
        ),
        ForeignKeyConstraint(
            ["driver_id", "company_id"],
            ["users.id", "users.company_id"],
            name="fk_trips_driver_company",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, nullable=False, index=True)
    driver_id = Column(Integer, nullable=False, index=True)

    origin_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    destination_id = Column(Integer, ForeignKey("locations.id"), nullable=False)

    departure_time = Column(DateTime(timezone=True), nullable=False)
    arrival_time = Column(DateTime(timezone=True), nullable=False)

    distance_km = Column(Integer, nullable=False)
    ticket_price = Column(Integer, nullable=False)
    passengers_carried = Column(Integer, default=0)

    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    @property
    def status(self) -> TripStatus:
        if self.cancelled_at is not None:
            return TripStatus.CANCELLED

        now = datetime.now(timezone.utc)

        departure = self.departure_time
        arrival = self.arrival_time

        # SQLite може повертати datetime без timezone,
        # навіть якщо в колонці timezone=True.
        if departure.tzinfo is None:
            departure = departure.replace(tzinfo=timezone.utc)

        if arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=timezone.utc)

        if now < departure:
            return TripStatus.SCHEDULED

        if now < arrival:
            return TripStatus.IN_PROGRESS

        return TripStatus.COMPLETED
