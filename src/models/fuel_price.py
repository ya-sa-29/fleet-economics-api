import enum
from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.sql import func
from src.models.base import Base

class FuelCategory(str, enum.Enum):
    A95 = "a-95"
    DIESEL = "diesel"
    GAS = "gas"

class FuelPrice(Base):
    __tablename__ = "fuel_prices"

    id = Column(Integer, primary_key=True, index=True)
    fuel_type = Column(String, nullable=False, index=True)
    price_per_liter = Column(Integer, nullable=False)  # Ціна в копійках
    parsed_at = Column(Date, default=func.current_date(), nullable=False, index=True)
    source = Column(String, default="minfin.com.ua")