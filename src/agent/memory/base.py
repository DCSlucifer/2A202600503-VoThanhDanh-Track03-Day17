from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MemoryBackend(Protocol):
    """Stable read/write/search contract shared by every memory backend.

    Kept deliberately generic so concrete backends can use their native object
    types (Preference/Fact/Episode/SemanticChunk) in their own method signatures.
    """

    name: str

    def health(self) -> bool:
        ...

    def read(self, **kwargs: Any) -> Any:
        ...

    def write(self, obj: Any, **kwargs: Any) -> Any:
        ...

    def search(self, query: str, k: int = 5, **kwargs: Any) -> list[Any]:
        ...

    def delete(self, **kwargs: Any) -> bool:
        ...
