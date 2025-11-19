from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import canvas
from routers.github_webhook import router as github_router
# from routers.costs import costs as costs_router




app = FastAPI(title="FOUNDRYFORGER")

# origins = ['http://localhost:3000']

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(canvas.router)
app.include_router(canvas.builds)
app.include_router(github_router)
# app.include_router(costs_router)