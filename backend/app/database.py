from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from os import getenv
from typing import Any
from uuid import UUID, uuid4

from psycopg import connect
from psycopg.rows import dict_row


class MemoryRepository:
    def __init__(self) -> None:
        self.letters: list[dict[str, Any]] = []
        self.reminders: list[dict[str, Any]] = []
        self.wallets: list[dict[str, Any]] = []
        self.transactions: list[dict[str, Any]] = []

    def list_letters(self) -> list[dict[str, Any]]:
        return sorted(self.letters, key=lambda item: item["created_at"], reverse=True)

    def check_connection(self) -> bool:
        return True

    def create_letter(self, title: str, body_html: str, created_at: datetime) -> dict[str, Any]:
        letter = {"id": str(uuid4()), "title": title, "body_html": body_html, "created_at": created_at}
        self.letters.append(letter)
        return letter

    def list_reminders(self) -> list[dict[str, Any]]:
        return self.reminders

    def create_reminder(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        reminder = {"id": str(uuid4()), **values, "created_at": created_at}
        self.reminders.append(reminder)
        return reminder

    def delete_reminder(self, reminder_id: UUID) -> bool:
        for index, reminder in enumerate(self.reminders):
            if reminder["id"] == str(reminder_id):
                self.reminders.pop(index)
                return True
        return False

    def list_wallets(self) -> list[dict[str, Any]]:
        return [{**wallet, "balance": self.wallet_balance(wallet["id"])} for wallet in self.wallets]

    def create_wallet(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        wallet = {"id": str(uuid4()), **values, "created_at": created_at}
        self.wallets.append(wallet)
        return {**wallet, "balance": Decimal("0")}

    def wallet_exists(self, wallet_id: UUID) -> bool:
        return any(wallet["id"] == str(wallet_id) for wallet in self.wallets)

    def wallet_balance(self, wallet_id: str | None) -> Decimal:
        return sum((Decimal(str(item["amount"])) if item["type"] == "deposit" else -Decimal(str(item["amount"])) for item in self.transactions if item["wallet_id"] == wallet_id), Decimal("0"))

    def list_transactions(self) -> list[dict[str, Any]]:
        return self.transactions

    def create_transaction(self, values: dict[str, Any], occurred_at: datetime) -> dict[str, Any]:
        wallet_id = str(values["wallet_id"]) if values.get("wallet_id") else None
        values = {**values, "wallet_id": wallet_id}
        if values["type"] == "withdraw" and Decimal(str(values["amount"])) > self.wallet_balance(wallet_id):
            raise ValueError("This withdrawal is larger than the available balance.")
        transaction = {"id": str(uuid4()), **values, "occurred_at": occurred_at}
        self.transactions.append(transaction)
        return transaction


class PostgresRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connection(self):
        return connect(self.database_url, row_factory=dict_row)

    def check_connection(self) -> bool:
        with self._connection() as connection:
            connection.execute("select 1")
        return True

    def list_letters(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select id, title, body_html, created_at from letters order by created_at desc").fetchall())

    def create_letter(self, title: str, body_html: str, created_at: datetime) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute("insert into letters (title, body_html, created_at) values (%s, %s, %s) returning id, title, body_html, created_at", (title, body_html, created_at)).fetchone()

    def list_reminders(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select id, title, description, tags, start_at, end_at, recurrence, created_at from reminders order by start_at").fetchall())

    def create_reminder(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute("insert into reminders (title, description, tags, start_at, end_at, recurrence, created_at) values (%s, %s, %s, %s, %s, %s, %s) returning id, title, description, tags, start_at, end_at, recurrence, created_at", (*values.values(), created_at)).fetchone()

    def delete_reminder(self, reminder_id: UUID) -> bool:
        with self._connection() as connection:
            result = connection.execute("delete from reminders where id = %s", (reminder_id,))
            return result.rowcount > 0

    def list_wallets(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select w.id, w.name, w.target, w.created_at, coalesce(sum(case when t.type = 'deposit' then t.amount else -t.amount end), 0) as balance from wallets w left join transactions t on t.wallet_id = w.id group by w.id order by w.created_at").fetchall())

    def create_wallet(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute("insert into wallets (name, target, created_at) values (%s, %s, %s) returning id, name, target, created_at", (*values.values(), created_at)).fetchone() | {"balance": Decimal("0")}

    def wallet_exists(self, wallet_id: UUID) -> bool:
        with self._connection() as connection:
            return connection.execute("select 1 from wallets where id = %s", (wallet_id,)).fetchone() is not None

    def list_transactions(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select id, wallet_id, type, amount, merchant, note, occurred_at from transactions order by occurred_at desc").fetchall())

    def create_transaction(self, values: dict[str, Any], occurred_at: datetime) -> dict[str, Any]:
        wallet_id = values.get("wallet_id")
        with self._connection() as connection:
            if wallet_id is not None:
                connection.execute("select id from wallets where id = %s for update", (wallet_id,))
            else:
                connection.execute("select pg_advisory_xact_lock(hashtext('iloveyoury:general-balance'))")
            balance = connection.execute("select coalesce(sum(case when type = 'deposit' then amount else -amount end), 0) as balance from transactions where wallet_id is not distinct from %s", (wallet_id,)).fetchone()["balance"]
            if values["type"] == "withdraw" and values["amount"] > balance:
                raise ValueError("This withdrawal is larger than the available balance.")
            return connection.execute("insert into transactions (wallet_id, type, amount, merchant, note, occurred_at) values (%s, %s, %s, %s, %s, %s) returning id, wallet_id, type, amount, merchant, note, occurred_at", (wallet_id, values["type"], values["amount"], values["merchant"], values["note"], occurred_at)).fetchone()


def create_repository() -> MemoryRepository | PostgresRepository:
    database_url = getenv("DATABASE_URL", "").strip()
    return PostgresRepository(database_url) if database_url else MemoryRepository()
