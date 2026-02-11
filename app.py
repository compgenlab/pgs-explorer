from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from apps.core.config import create_app, templates
from apps.core.startup import register_startup_events
from apps.session.service import add_session_middleware
from apps.session.service import SessionManager

from apps.distribution.router import router as distribution_router
from apps.multivariate.router import router as multivariate_router
from apps.subcohorts.router import router as subcohort_router
from apps.tasks.router import router as tasks_router
from apps.core.router import router as core_router
from apps.session.router import router as session_router
from apps.cohorts.router import router as cohorts_router
from apps.temporary_scores.router import router as temporary_scores_router

# Create the app
app = create_app()

# Add session middleware (must be added before other middleware/routers)
add_session_middleware(app)

# Register startup events
register_startup_events(app)

# Root route 
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    SessionManager.get_or_create_user_id(request)
    return templates.TemplateResponse("index.html", {"request": request})

# Include routers
app.include_router(distribution_router)
#app.include_router(multivariate_router)
app.include_router(subcohort_router)
app.include_router(tasks_router)
app.include_router(core_router)
app.include_router(session_router)  
app.include_router(cohorts_router)
app.include_router(temporary_scores_router)
