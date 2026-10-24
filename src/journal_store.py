from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class JournalEntry:
    id: str
    entry_date: str
    text_content: str
    image_path: str | None
    created_at: str


class JournalStore:
    """SQLite storage and app-private image files for the journal."""

    def __init__(
        self,
        data_dir: str | Path | None = None,
        documents_dir: str | Path | None = None,
    ) -> None:
        configured_dir = data_dir or os.environ.get("FLET_APP_STORAGE_DATA")
        self.data_dir = Path(configured_dir) if configured_dir else Path.home() / ".one-line-journal"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.documents_dir = Path(documents_dir) if documents_dir else self.data_dir
        self.images_dir = self.documents_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = self.data_dir / "journal.sqlite3"
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS JournalEntries (
                    id TEXT PRIMARY KEY,
                    entry_date TEXT UNIQUE NOT NULL,
                    text_content TEXT NOT NULL DEFAULT '' CHECK(length(text_content) <= 140),
                    image_path TEXT,
                    created_at TIMESTAMP NOT NULL
                )
                """
            )

    @staticmethod
    def _entry_from_row(row: sqlite3.Row | None) -> JournalEntry | None:
        if row is None:
            return None
        return JournalEntry(
            id=row["id"],
            entry_date=row["entry_date"],
            text_content=row["text_content"] or "",
            image_path=row["image_path"],
            created_at=row["created_at"],
        )

    def get_entry(self, entry_date: str) -> JournalEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, entry_date, text_content, image_path, created_at "
                "FROM JournalEntries WHERE entry_date = ?",
                (entry_date,),
            ).fetchone()
        return self._entry_from_row(row)

    def get_today_entry(self) -> JournalEntry | None:
        return self.get_entry(date.today().isoformat())

    def save_entry(self, entry_date: str, text_content: str, image_path: str | None) -> JournalEntry:
        entry_id = str(uuid4())
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO JournalEntries (id, entry_date, text_content, image_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entry_date) DO UPDATE SET
                    text_content = excluded.text_content,
                    image_path = excluded.image_path
                """,
                (entry_id, entry_date, text_content[:140], image_path, created_at),
            )
            row = connection.execute(
                "SELECT id, entry_date, text_content, image_path, created_at "
                "FROM JournalEntries WHERE entry_date = ?",
                (entry_date,),
            ).fetchone()
        entry = self._entry_from_row(row)
        if entry is None:
            raise RuntimeError("The journal entry could not be read after saving.")
        return entry

    def list_entries(self) -> list[JournalEntry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, entry_date, text_content, image_path, created_at "
                "FROM JournalEntries ORDER BY entry_date DESC"
            ).fetchall()
        return [entry for row in rows if (entry := self._entry_from_row(row)) is not None]

    def save_image(self, contents: bytes, extension: str = ".jpg") -> str:
        if not contents:
            raise ValueError("The selected image is empty.")
        safe_extension = extension.lower()
        if safe_extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
            safe_extension = ".jpg"
        filename = f"{uuid4().hex}{safe_extension}"
        relative_path = f"images/{filename}"
        (self.images_dir / filename).write_bytes(contents)
        return relative_path

    def read_image(self, relative_path: str | None) -> bytes | None:
        path = self._managed_image_path(relative_path)
        if path is None or not path.is_file():
            return None
        try:
            return path.read_bytes()
        except OSError:
            return None

    def delete_image(self, relative_path: str | None) -> None:
        path = self._managed_image_path(relative_path)
        if path is None:
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def cleanup_unreferenced_images(self) -> None:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT image_path FROM JournalEntries WHERE image_path IS NOT NULL"
            ).fetchall()
        referenced = {row["image_path"] for row in rows}
        for path in self.images_dir.iterdir():
            if path.is_file() and f"images/{path.name}" not in referenced:
                try:
                    path.unlink()
                except OSError:
                    pass

    def _managed_image_path(self, relative_path: str | None) -> Path | None:
        if not relative_path:
            return None
        relative = Path(relative_path)
        if relative.is_absolute() or relative.parts[:1] != ("images",) or len(relative.parts) != 2:
            return None
        return self.images_dir / relative.name

