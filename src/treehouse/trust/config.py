"""Trust-engine identity: the pre-registered constants live in ``schemas.config.TrustConfig``."""

from __future__ import annotations

from treehouse.canon import sha256_json
from treehouse.schemas.config import TrustConfig

ESTIMATOR_VERSION = "treehouse-trust-core/1"
PPI_METHOD = "ppi-2phase-rbs-v1"


def trust_config_hash(cfg: TrustConfig) -> str:
    return sha256_json(cfg)
