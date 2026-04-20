from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.modules.notes.schemas import FolderItem, NoteItem, NoteUpsertRequest


class NoteService:
    """笔记领域服务。

    当前以内存目录树与笔记集合提供联调能力，后续迁移到关系库。
    """

    def __init__(self) -> None:
        # 文件夹和笔记分离，便于后续扩展树结构与权限模型。
        self._folders: list[FolderItem] = [
            FolderItem(folder_id="f_root", name="默认文件夹", parent_id=None),
            FolderItem(folder_id="f_watchlist", name="重点观察", parent_id="f_root"),
        ]
        self._notes: dict[str, NoteItem] = {
            "n_watch_1": NoteItem(
                note_id="n_watch_1",
                folder_id="f_watchlist",
                title="AI算力板块跟踪",
                content_markdown="### 观察结论\n龙头强于板块，关注分歧后的二次上攻。",
                updated_at=datetime.now(tz=UTC),
            )
        }

    def list_folders(self) -> list[FolderItem]:
        return sorted(
            self._folders,
            key=lambda folder: (
                folder.parent_id is not None,
                folder.parent_id or "",
                folder.name,
                folder.folder_id,
            ),
        )

    def list_notes(self, folder_id: str | None = None) -> list[NoteItem]:
        notes = list(self._notes.values())
        if folder_id:
            notes = [note for note in notes if note.folder_id == folder_id]
        return sorted(notes, key=lambda note: note.updated_at, reverse=True)

    def upsert_note(self, note_id: str | None, payload: NoteUpsertRequest) -> NoteItem:
        folder_ids = {folder.folder_id for folder in self._folders}
        if payload.folder_id not in folder_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件夹不存在")

        target_id = note_id or f"note_{uuid4().hex[:10]}"
        note = NoteItem(
            note_id=target_id,
            folder_id=payload.folder_id,
            title=payload.title,
            content_markdown=payload.content_markdown,
            updated_at=datetime.now(tz=UTC),
        )
        self._notes[target_id] = note
        return note
