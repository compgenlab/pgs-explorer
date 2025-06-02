from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from apps.core.config import create_app, templates
from apps.core.startup import register_startup_events

from apps.distribution.router import router as distribution_router
from apps.multivariate.router import router as multivariate_router
from apps.subcohorts.router import router as subcohort_router
from apps.tasks.router import router as tasks_router
from apps.core.router import router as core_router

# Create the app
app = create_app()

# Register startup events
register_startup_events(app)

# Root route 
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Include routers
app.include_router(distribution_router)
app.include_router(multivariate_router)
app.include_router(subcohort_router)
app.include_router(tasks_router)
app.include_router(core_router)