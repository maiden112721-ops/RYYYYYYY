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

    def create_letter(self, client_id: UUID, title: str, body_html: str, created_at: datetime) -> dict[str, Any]:
        existing = next((item for item in self.letters if item["client_id"] == str(client_id)), None)
        if existing:
            return existing
        letter = {"id": str(uuid4()), "client_id": str(client_id), "title": title, "body_html": body_html, "created_at": created_at}
        self.letters.append(letter)
        return letter

    def list_reminders(self) -> list[dict[str, Any]]:
        return self.reminders

    def create_reminder(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        values = {**values, "client_id": str(values["client_id"])}
        existing = next((item for item in self.reminders if item["client_id"] == values["client_id"]), None)
        if existing:
            return existing
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
        values = {**values, "client_id": str(values["client_id"])}
        existing = next((item for item in self.wallets if item["client_id"] == values["client_id"]), None)
        if existing:
            return {**existing, "balance": self.wallet_balance(existing["id"])}
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
        values = {**values, "client_id": str(values["client_id"])}
        existing = next((item for item in self.transactions if item["client_id"] == values["client_id"]), None)
        if existing:
            return existing
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
            return list(connection.execute("select id, client_id, title, body_html, created_at from letters order by created_at desc").fetchall())

    def create_letter(self, client_id: UUID, title: str, body_html: str, created_at: datetime) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute("insert into letters (client_id, title, body_html, created_at) values (%s, %s, %s, %s) on conflict (client_id) do update set title = excluded.title, body_html = excluded.body_html returning id, client_id, title, body_html, created_at", (client_id, title, body_html, created_at)).fetchone()

    def list_reminders(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select id, client_id, title, description, tags, start_at, end_at, recurrence, created_at from reminders order by start_at").fetchall())

    def create_reminder(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute("insert into reminders (client_id, title, description, tags, start_at, end_at, recurrence, created_at) values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict (client_id) do update set title = excluded.title, description = excluded.description, tags = excluded.tags, start_at = excluded.start_at, end_at = excluded.end_at, recurrence = excluded.recurrence returning id, client_id, title, description, tags, start_at, end_at, recurrence, created_at", (values["client_id"], values["title"], values["description"], values["tags"], values["start_at"], values["end_at"], values["recurrence"], created_at)).fetchone()

    def delete_reminder(self, reminder_id: UUID) -> bool:
        with self._connection() as connection:
            result = connection.execute("delete from reminders where id = %s", (reminder_id,))
            return result.rowcount > 0

    def list_wallets(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select w.id, w.client_id, w.name, w.target, w.created_at, coalesce(sum(case when t.type = 'deposit' then t.amount else -t.amount end), 0) as balance from wallets w left join transactions t on t.wallet_id = w.id group by w.id order by w.created_at").fetchall())

    def create_wallet(self, values: dict[str, Any], created_at: datetime) -> dict[str, Any]:
        with self._connection() as connection:
            return connection.execute("insert into wallets (client_id, name, target, created_at) values (%s, %s, %s, %s) on conflict (client_id) do update set name = excluded.name, target = excluded.target returning id, client_id, name, target, created_at", (values["client_id"], values["name"], values["target"], created_at)).fetchone() | {"balance": Decimal("0")}

    def wallet_exists(self, wallet_id: UUID) -> bool:
        with self._connection() as connection:
            return connection.execute("select 1 from wallets where id = %s", (wallet_id,)).fetchone() is not None

    def list_transactions(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return list(connection.execute("select id, client_id, wallet_id, type, amount, merchant, note, occurred_at from transactions order by occurred_at desc").fetchall())

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
            return connection.execute("insert into transactions (client_id, wallet_id, type, amount, merchant, note, occurred_at) values (%s, %s, %s, %s, %s, %s, %s) on conflict (client_id) do update set wallet_id = excluded.wallet_id, type = excluded.type, amount = excluded.amount, merchant = excluded.merchant, note = excluded.note returning id, client_id, wallet_id, type, amount, merchant, note, occurred_at", (values["client_id"], wallet_id, values["type"], values["amount"], values["merchant"], values["note"], occurred_at)).fetchone()


def create_repository() -> MemoryRepository | PostgresRepository:
    database_url = getenv("DATABASE_URL", "").strip()
    return PostgresRepository(database_url) if database_url else MemoryRepository()
