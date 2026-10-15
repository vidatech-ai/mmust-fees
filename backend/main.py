from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import FRONTEND_ORIGIN
from api import timetable as timetable_api
from api import academic as academic_api
from api.auth import router as auth_router
from api.students import router as students_router
from api.messages import router as messages_router
from api.admin import router as admin_router
from api.admin_messages import router as admin_messages_router
from api.admin_fees import router as admin_fees_router
from api.public import router as public_router
from api.admin_students import router as admin_students_router
from api.settings import router as settings_router
from api.statement import router as statement_router
from api.photo import router as photo_router
from api.payments import router as payments_router

app = FastAPI(title="Sample University Fee Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(students_router)
app.include_router(messages_router)
app.include_router(admin_router)
app.include_router(admin_messages_router)
app.include_router(admin_fees_router)
app.include_router(public_router)
app.include_router(admin_students_router)
app.include_router(settings_router)
app.include_router(statement_router)
app.include_router(photo_router)
app.include_router(payments_router)
app.include_router(timetable_api.router)
app.include_router(academic_api.router)


@app.get("/health")
def health():
    return {"status": "ok"}
