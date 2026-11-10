import enum
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.sql import func
from src.models.base import Base
from sqlalchemy import Index

class FuelType(str, enum.Enum):
    PETROL = "petrol"
    DIESEL = "diesel"
    GAS = "gas"
    ELECTRIC = "electric"

class Vehicle(Base):
    __tablename__ = "vehicles"

    __table_args__ = (
        Index("uq_vehicles_id_company", "id", "company_id", unique=True),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    
    brand = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    
    current_mileage = Column(Integer, default=0)
    fuel_type = Column(Enum(FuelType), nullable=False)
    fuel_consumption = Column(Numeric(5, 2), nullable=False)  # Літрів на 100 км
    passenger_capacity = Column(Integer, nullable=False)
    
    # Фінанси для EconomicsService (зберігаємо в копійках/центах)
    purchase_price = Column(Integer, nullable=False)
    purchase_mileage = Column(Integer, default=0)
    expected_life_km = Column(Integer, nullable=False)
    residual_value = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)