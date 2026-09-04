from datetime import datetime
from decimal import Decimal
from os import getenv
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .database import MemoryRepository, PostgresRepository, create_repository

LETTER_PIN = getenv("LETTER_PIN", "091425")
FRONTEND_ORIGIN = getenv("FRONTEND_ORIGIN", "*")

app = FastAPI(title="ILOVEYOURY API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN != "*" else ["*"],
    allow_credentials=FRONTEND_ORIGIN != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = create_repository()

# Kept as aliases for the local test suite and preview mode.
letters = repository.letters if isinstance(repository, MemoryRepository) else []
reminders = repository.reminders if isinstance(repository, MemoryRepository) else []
wallets = repository.wallets if isinstance(repository, MemoryRepository) else []
transactions = repository.transactions if isinstance(repository, MemoryRepository) else []


def now() -> datetime:
    return datetime.now().astimezone()


def clean_html(value: str) -> str:
    allowed = {"p", "br", "strong", "em", "u", "s", "ul", "ol", "li", "h1", "h2", "blockquote"}
    result = value
    import re
    result = re.sub(r"<(?!/?(?:" + "|".join(allowed) + r")\b)[^>]*>", "", result, flags=re.I)
    return result.strip()


class LetterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body_html: str = Field(min_length=1, max_length=50000)
    pin: str = Field(min_length=1, max_length=32)


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=8)
    start_at: datetime
    end_at: datetime
    recurrence: Literal["none", "daily", "weekly", "monthly"] = "none"

    @field_validator("end_at")
    @classmethod
    def end_after_start(cls, value: datetime, info):
        start = info.data.get("start_at")
        if start and value <= start:
            raise ValueError("end_at must be after start_at")
        return value


class WalletCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target: Decimal | None = Field(default=None, ge=0, decimal_places=2)


class TransactionCreate(BaseModel):
    type: Literal["deposit", "withdraw"]
    amount: Decimal = Field(gt=0, decimal_places=2)
    merchant: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=500)
    wallet_id: UUID | None = None


@app.get("/api/health")
def health():
    try:
        repository.check_connection()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.") from error
    return {
        "status": "ok",
        "service": "iloveyoury-api",
        "storage": "supabase" if isinstance(repository, PostgresRepository) else "memory",
    }


@app.get("/api/letters")
def get_letters():
    return repository.list_letters()


@app.post("/api/letters", status_code=201)
def create_letter(payload: LetterCreate):
    if payload.pin != LETTER_PIN:
        raise HTTPException(status_code=403, detail="That PIN is not quite right.")
    return repository.create_letter(payload.title.strip(), clean_html(payload.body_html), now())


@app.get("/api/reminders")
def get_reminders():
    return repository.list_reminders()


@app.post("/api/reminders", status_code=201)
def create_reminder(payload: ReminderCreate):
    return repository.create_reminder(payload.model_dump(), now())


@app.delete("/api/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: UUID):
    if not repository.delete_reminder(reminder_id):
        raise HTTPException(status_code=404, detail="Reminder not found")


@app.get("/api/wallets")
def get_wallets():
    return repository.list_wallets()


@app.post("/api/wallets", status_code=201)
def create_wallet(payload: WalletCreate):
    return repository.create_wallet(payload.model_dump(), now())


@app.get("/api/transactions")
def get_transactions():
    return repository.list_transactions()


@app.post("/api/transactions", status_code=201)
def create_transaction(payload: TransactionCreate):
    if payload.wallet_id and not repository.wallet_exists(payload.wallet_id):
        raise HTTPException(status_code=404, detail="Wallet not found")
    try:
        return repository.create_transaction(payload.model_dump(), now())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
