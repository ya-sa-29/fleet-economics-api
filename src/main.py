from fastapi import FastAPI
from src.api import auth, vehicles, trips, fuel_logs, maintenance_logs, fuel_prices, economics

app = FastAPI(
    title="B2B Fleet Economics API",
    description="API для управління автопарком мікроперевізників та розрахунку економіки.",
    version="1.0.0"
)

app.include_router(auth.router)
app.include_router(vehicles.router)
app.include_router(trips.router)
app.include_router(fuel_logs.router)
app.include_router(maintenance_logs.router)
app.include_router(economics.router)
app.include_router(fuel_prices.router)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok", "message": "Fleet Economics API is running"}