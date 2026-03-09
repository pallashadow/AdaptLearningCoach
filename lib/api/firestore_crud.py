from typing import Any


class FirestoreCRUD:
    def __init__(self, firestore_client: Any) -> None:
        self._firestore = firestore_client

    def _doc(self, collection: str, document_id: str) -> Any:
        return self._firestore.collection(collection).document(document_id)

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        snapshot = await self._doc(collection, document_id).get()
        if not snapshot.exists:
            return None
        return dict(snapshot.to_dict() or {})

    async def set(self, collection: str, document_id: str, value: dict[str, Any]) -> None:
        await self._doc(collection, document_id).set(value)

    async def update(self, collection: str, document_id: str, value: dict[str, Any]) -> None:
        await self._doc(collection, document_id).update(value)

    async def delete(self, collection: str, document_id: str) -> bool:
        doc_ref = self._doc(collection, document_id)
        snapshot = await doc_ref.get()
        if not snapshot.exists:
            return False
        await doc_ref.delete()
        return True

    async def list_by_field(self, collection: str, field_name: str, field_value: Any) -> list[dict[str, Any]]:
        query = self._firestore.collection(collection).where(field_name, "==", field_value)
        snapshots = [snapshot async for snapshot in query.stream()]
        rows: list[dict[str, Any]] = []
        for snapshot in snapshots:
            data = dict(snapshot.to_dict() or {})
            data["_doc_id"] = snapshot.id
            rows.append(data)
        return rows

    async def compare_and_set(
        self,
        collection: str,
        document_id: str,
        expected_updated_at: str,
        value: dict[str, Any],
    ) -> bool:
        from google.cloud import firestore_v1  # type: ignore

        doc_ref = self._doc(collection, document_id)
        transaction = self._firestore.transaction()

        @firestore_v1.async_transactional
        async def _cas(txn: Any) -> bool:
            snapshot = await doc_ref.get(transaction=txn)
            if not snapshot.exists:
                return False
            data = snapshot.to_dict() or {}
            current_updated_at = str(data.get("updated_at", ""))
            if current_updated_at != expected_updated_at:
                return False
            txn.set(doc_ref, value)
            return True

        return bool(await _cas(transaction))
