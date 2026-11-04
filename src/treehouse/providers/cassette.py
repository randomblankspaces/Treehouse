"""Model cassettes: record live turns, replay them offline.

Entries are looked up by ``(role, trial_index, turn)``; the request hash only detects divergence
(§0 row 19: a request hash alone collides across trials). Cassettes are pixel-free: images keep
``format`` and ``sha256`` and lose ``bytes_``, so the replay key equals the live key (OBS-B1).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from treehouse.canon import canonical_json, sha256_bytes
from treehouse.providers.base import ModelProvider, ProviderError, pixel_free, pixel_free_response
from treehouse.schemas.base import Frozen
from treehouse.schemas.model_io import ModelRequest, ModelResponse

Key = tuple[str, int, int]


class CassetteEntry(Frozen):
    role: str
    trial_index: int
    turn: int
    request_hash: str
    request: ModelRequest  # pixel-free
    response: ModelResponse
    provider: str

    @property
    def key(self) -> Key:
        return (self.role, self.trial_index, self.turn)


class CassetteError(ProviderError):
    pass


class CassetteMiss(ProviderError):
    def __init__(self, key: Key, first_divergent_message_index: int | None, detail: str) -> None:
        self.key = key
        self.first_divergent_message_index = first_divergent_message_index
        self.detail = detail
        super().__init__(f"cassette miss at {key}: {detail}"
                         + (f" (first divergent message {first_divergent_message_index})"
                            if first_divergent_message_index is not None else ""))


class Cassette:
    """An append-only JSONL cassette (in memory when ``path`` is None)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self.entries: dict[Key, CassetteEntry] = {}
        if self.path is not None and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    e = CassetteEntry.model_validate_json(line)
                    if e.key in self.entries:
                        raise CassetteError(f"duplicate cassette entry {e.key} in {self.path}")
                    self.entries[e.key] = e

    @property
    def ref(self) -> str:
        """A machine-independent name for traces (never an absolute path)."""
        return self.path.name if self.path is not None else "memory"

    def sha256(self) -> str | None:
        return sha256_bytes(self.path.read_bytes()) if self.path is not None and self.path.exists() else None

    def add(self, entry: CassetteEntry) -> None:
        if entry.key in self.entries:
            raise CassetteError(f"cassette already has an entry for {entry.key}")
        self.entries[entry.key] = entry
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(canonical_json(entry) + "\n")

    def get(self, key: Key) -> CassetteEntry | None:
        return self.entries.get(key)


def first_divergent_message_index(recorded: ModelRequest, live: ModelRequest) -> int | None:
    a = [canonical_json(m) for m in pixel_free(recorded).messages]
    b = [canonical_json(m) for m in pixel_free(live).messages]
    for i, (x, y) in enumerate(zip(a, b, strict=False)):
        if x != y:
            return i
    return min(len(a), len(b)) if len(a) != len(b) else None


class RecordingProvider:
    def __init__(self, inner: ModelProvider, cassette: Cassette) -> None:
        self.inner, self.cassette = inner, cassette
        self.provider_name = inner.provider_name
        self.price_table_version = getattr(inner, "price_table_version", "none")
        self.cassette_ref = cassette.ref

    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse:
        if self.cassette.get((role, trial_index, turn)) is not None:
            raise CassetteError(f"cassette already has an entry for {(role, trial_index, turn)}")
        resp = await self.inner.complete(req, role=role, trial_index=trial_index, turn=turn)
        self.cassette.add(CassetteEntry(role=role, trial_index=trial_index, turn=turn, request_hash=req.key(),
                                        request=pixel_free(req), response=pixel_free_response(resp),
                                        provider=self.inner.provider_name))
        return resp


class ReplayProvider:
    """Serves recorded responses. Accepts pixel-free images. Any miss or divergence raises."""

    provider_name = "replay"

    def __init__(self, cassette: Cassette, miss: Literal["fail"] = "fail") -> None:
        if miss != "fail":
            raise ValueError("only miss='fail' is supported")
        self.cassette = cassette
        self.cassette_ref = cassette.ref

    async def complete(self, req: ModelRequest, *, role: str, trial_index: int, turn: int) -> ModelResponse:
        key = (role, trial_index, turn)
        e = self.cassette.get(key)
        if e is None:
            raise CassetteMiss(key, None, "no recorded entry")
        if e.request_hash != req.key():
            idx = first_divergent_message_index(e.request, req)
            fields = [f for f in ("model_id", "system", "tools", "params") if getattr(e.request, f) != getattr(req, f)]
            raise CassetteMiss(key, idx, "request hash differs" + (f" in {fields}" if fields else ""))
        return e.response
