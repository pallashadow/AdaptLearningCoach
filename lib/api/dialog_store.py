import json
from typing import Any

from lib.api.firestore_crud import FirestoreCRUD


class FirestoreDialogStore:
    def __init__(self, firestore_client: Any, collection: str = "agentic_dialogs") -> None:
        self._crud = FirestoreCRUD(firestore_client)
        self._collection = collection

    async def get(self, dialog_id: str) -> dict[str, Any] | None:
        data = await self._crud.get(self._collection, dialog_id)
        if data is None:
            return None
        return json.loads(json.dumps(data))

    async def set(self, dialog_id: str, value: dict[str, Any]) -> None:
        await self._crud.set(self._collection, dialog_id, value)

    async def compare_and_set(self, dialog_id: str, expected_updated_at: str, value: dict[str, Any]) -> bool:
        return await self._crud.compare_and_set(self._collection, dialog_id, expected_updated_at, value)

    async def delete(self, dialog_id: str) -> bool:
        return await self._crud.delete(self._collection, dialog_id)
