from fastapi import FastAPI

from app.database.mongodb import check_database_connection
from app.routes.organizations import router as organizations_router
from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="HemaHub API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await check_database_connection()


@app.get("/")
async def root():
    return {
        "message": "HemaHub API is running"
    }


app.include_router(organizations_router)
app.include_router(auth_router)
app.include_router(users_router)