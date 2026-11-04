"""resolve_backends(): what actually runs for each backend slot.

Tonight only local backends exist. S3 storage and IAM key isolation (W5) degrade to local when
``allow_degrade`` is set and are refused otherwise; the manifest records the degradation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from treehouse.schemas.config import RunConfig
from treehouse.schemas.manifest import BackendResolution

KEY_ISOLATION_LOCAL = "local convention, not IAM-enforced"


class BackendUnavailable(RuntimeError):
    pass


def _res(slot: str, requested: str, ran: str, reason: str, allow: bool, **kw: Any) -> BackendResolution:
    if requested == ran:
        return BackendResolution(requested=requested, ran=ran, **kw)
    if not allow:
        raise BackendUnavailable(f"{slot}: {requested} requested but {reason}; allow_degrade is false")
    return BackendResolution(requested=requested, ran=ran, degraded_from=requested, reason=reason, **kw)


def resolve_backends(cfg: RunConfig, probes: Mapping[str, Any] | None = None) -> dict[str, BackendResolution]:
    """``probes`` (S3/IAM read-backs and canary denials) are consumed from W5; ignored tonight."""
    b, allow = cfg.backends, cfg.backends.allow_degrade
    out = {
        "store": _res("store", b.store, "local", "S3Store is not built yet (W5); local store used", allow,
                      evidence=["local filesystem"]),
        "key_isolation": _res("key_isolation", b.key_isolation, "local",
                              "IAM key isolation is not built yet (W5)", allow, statement=KEY_ISOLATION_LOCAL),
        "tracer": _res("tracer", ",".join(b.tracer), "jsonl", "only the jsonl tracer is built (otlp/cwlogs W9)",
                       allow),
        "model.worker": BackendResolution(requested=cfg.worker.provider, ran=cfg.worker.provider,
                                          evidence=[f"model_key={cfg.worker.model_key}"]),
    }
    if cfg.verifier is not None:
        out["model.verifier"] = BackendResolution(requested=cfg.verifier.provider, ran=cfg.verifier.provider,
                                                  evidence=[f"model_key={cfg.verifier.model_key}"])
    return out
