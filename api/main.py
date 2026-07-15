from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import country_profile, forecasts, historical, overview, scenarios
from .schemas import HealthResponse

app = FastAPI(title="GHG Emissions Analysis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(overview.router, prefix="/api")
app.include_router(historical.router, prefix="/api")
app.include_router(country_profile.router, prefix="/api")
app.include_router(forecasts.router, prefix="/api")
app.include_router(scenarios.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")
