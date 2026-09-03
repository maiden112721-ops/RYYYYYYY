from datetime import datetime
from decimal import Decimal
from html import escape
from os import getenv
from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

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

letters: list[dict] = []
reminders: list[dict] = []
wallets: list[dict] = []
transactions: list[dict] = []


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


def with_balance(wallet: dict) -> dict:
    balance = sum((Decimal(str(t["amount"])) if t["type"] == "deposit" else -Decimal(str(t["amount"])) for t in transactions if t["wallet_id"] == wallet["id"]), Decimal("0"))
    return {**wallet, "balance": balance}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "iloveyoury-api"}


@app.get("/api/letters")
def get_letters():
    return sorted(letters, key=lambda item: item["created_at"], reverse=True)


@app.post("/api/letters", status_code=201)
def create_letter(payload: LetterCreate):
    if payload.pin != LETTER_PIN:
        raise HTTPException(status_code=403, detail="That PIN is not quite right.")
    letter = {"id": str(uuid4()), "title": payload.title.strip(), "body_html": clean_html(payload.body_html), "created_at": now().isoformat()}
    letters.append(letter)
    return letter


@app.get("/api/reminders")
def get_reminders():
    return reminders


@app.post("/api/reminders", status_code=201)
def create_reminder(payload: ReminderCreate):
    reminder = {"id": str(uuid4()), **payload.model_dump(mode="json"), "created_at": now().isoformat()}
    reminders.append(reminder)
    return reminder


@app.delete("/api/reminders/{reminder_id}", status_code=204)
def delete_reminder(reminder_id: UUID):
    for index, reminder in enumerate(reminders):
        if reminder["id"] == str(reminder_id):
            reminders.pop(index)
            return
    raise HTTPException(status_code=404, detail="Reminder not found")


@app.get("/api/wallets")
def get_wallets():
    return [with_balance(wallet) for wallet in wallets]


@app.post("/api/wallets", status_code=201)
def create_wallet(payload: WalletCreate):
    wallet = {"id": str(uuid4()), **payload.model_dump(mode="json"), "created_at": now().isoformat()}
    wallets.append(wallet)
    return with_balance(wallet)


@app.get("/api/transactions")
def get_transactions():
    return transactions


@app.post("/api/transactions", status_code=201)
def create_transaction(payload: TransactionCreate):
    if payload.wallet_id and not any(wallet["id"] == str(payload.wallet_id) for wallet in wallets):
        raise HTTPException(status_code=404, detail="Wallet not found")
    if payload.type == "withdraw":
        balance = sum((Decimal(str(t["amount"])) if t["type"] == "deposit" else -Decimal(str(t["amount"])) for t in transactions if t["wallet_id"] == str(payload.wallet_id)), Decimal("0"))
        if payload.amount > balance:
            raise HTTPException(status_code=400, detail="This withdrawal is larger than the available balance.")
    transaction = {"id": str(uuid4()), **payload.model_dump(mode="json"), "occurred_at": now().isoformat()}
    transactions.append(transaction)
    return transaction
