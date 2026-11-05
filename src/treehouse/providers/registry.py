"""Model registry (``config/models.yaml``) and the role rules that need it.

Rows hold key, family, model_id, inference_profile, region, vision, tool_use, image_delivery,
max_image_px, price_ref and quota_note. Defaults are worker ``claude-sonnet-5-5`` and verifier
``nova-pro``; both are UNVERIFIED until the K1 probe (fact-check U1/U2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from treehouse.paths import repo_root
from treehouse.schemas.base import Frozen
from treehouse.schemas.config import RoleConfig, RunConfig


class RegistryError(ValueError):
    pass


class UnknownModel(RegistryError):
    pass


class RoleRuleViolation(RegistryError):
    pass


class ModelEntry(Frozen):
    key: str
    family: str
    model_id: str
    inference_profile: str | None = None
    alt_profiles: list[str] = []
    region: str
    vision: bool
    tool_use: bool
    image_delivery: Literal["tool_result", "user_turn"]
    max_image_px: int | None = None
    price_ref: str
    quota_note: str = ""
    verified: bool = False
    request_fields: dict[str, Any] = {}

    @property
    def invoke_id(self) -> str:
        """The id passed to ``converse(modelId=...)``: the inference profile when one is set."""
        return self.inference_profile or self.model_id


class ModelRegistry(Frozen):
    schema_version: Literal["treehouse.models/1"] = "treehouse.models/1"
    defaults: dict[str, str] = {}
    models: list[ModelEntry]

    @classmethod
    def load(cls, path: Path | str | None = None) -> ModelRegistry:
        p = Path(path) if path is not None else repo_root() / "config" / "models.yaml"
        reg = cls.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
        keys = [m.key for m in reg.models]
        if len(keys) != len(set(keys)):
            raise RegistryError(f"duplicate model keys in {p}")
        for role, key in reg.defaults.items():
            if key not in keys:
                raise RegistryError(f"default {role}={key!r} is not a registry key")
        return reg

    def get(self, key_or_id: str) -> ModelEntry:
        """Look up by registry key, then by model id or inference profile."""
        for m in self.models:
            if m.key == key_or_id:
                return m
        for m in self.models:
            if key_or_id in {m.model_id, m.inference_profile, *m.alt_profiles}:
                return m
        raise UnknownModel(f"model {key_or_id!r} is not in the registry")

    def keys(self) -> list[str]:
        return [m.key for m in self.models]


def check_role(registry: ModelRegistry, role: str, rc: RoleConfig, *, needs_vision: bool) -> ModelEntry | None:
    if rc.provider not in {"bedrock"} and rc.model_key not in registry.keys():
        return None  # fake/replay roles may use free-form keys
    entry = registry.get(rc.model_key)
    if entry.family != rc.family:
        raise RoleRuleViolation(f"{role}: config says family {rc.family!r} but the registry says "
                                f"{entry.family!r} for {entry.key}")
    if needs_vision and not entry.vision:
        raise RoleRuleViolation(f"{role}: task needs vision but {entry.key} has vision: false")
    if rc.tools and not entry.tool_use:
        raise RoleRuleViolation(f"{role}: role uses tools but {entry.key} has tool_use: false")
    return entry


def check_roles(cfg: RunConfig, registry: ModelRegistry, *, needs_vision: bool) -> None:
    """The same-family rule (by registry family, not the config's word) and the vision rule.

    The worker and verifier both see imagery when the task needs vision; the summarizer never does."""
    w = check_role(registry, "worker", cfg.worker, needs_vision=needs_vision)
    if cfg.verifier is not None:
        v = check_role(registry, "verifier", cfg.verifier, needs_vision=needs_vision)
        wf = w.family if w else cfg.worker.family
        vf = v.family if v else cfg.verifier.family
        if wf == vf and not cfg.allow_same_family:
            raise RoleRuleViolation(f"verifier family {vf!r} equals worker family; set allow_same_family to override")
    if cfg.summarizer is not None:
        check_role(registry, "summarizer", cfg.summarizer, needs_vision=False)
