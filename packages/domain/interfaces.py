from typing import Protocol

Vector = list[float]


class VisualEncoder(Protocol):
    def encode_image(self, object_key: str) -> Vector: ...
    def encode_text(self, text: str) -> Vector: ...


class AudioEncoder(Protocol):
    def encode_audio(self, object_key: str) -> Vector: ...


class VectorStore(Protocol):
    def upsert(self, records: list[dict]) -> None: ...
    def search(self, query: dict) -> list[dict]: ...


class FusionStrategy(Protocol):
    def fuse(self, lists: dict[str, list[dict]], context: dict) -> list[dict]: ...
