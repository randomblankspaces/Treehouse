"""Names accepted by ``treehouse schema <name>``."""

from __future__ import annotations

from pydantic import BaseModel

from treehouse.schemas.bundle import ReportBundle
from treehouse.schemas.checks import CheckLedger
from treehouse.schemas.claims import Claim, UnderstandingStatement
from treehouse.schemas.config import EvalSpec, RunConfig, TrustConfig
from treehouse.schemas.manifest import Manifest
from treehouse.schemas.model_io import ModelRequest, ModelResponse
from treehouse.schemas.numbers import TypedNumber
from treehouse.schemas.passport import TrustPassport
from treehouse.schemas.sampling import BlindItem, GoldDraw, SampleDesign
from treehouse.schemas.scorecard import Scorecard
from treehouse.schemas.task import TaskCard
from treehouse.schemas.tools import ClaySearchResult, SceneSummary, StacSearchResult, WindowResult
from treehouse.schemas.trace import ChainHead, ChainLine, SpanRecord
from treehouse.schemas.verdicts import GoldLabel, VerifierVerdict

SCHEMAS: dict[str, type[BaseModel]] = {
    "task": TaskCard,
    "runconfig": RunConfig,
    "evalspec": EvalSpec,
    "trustconfig": TrustConfig,
    "model-request": ModelRequest,
    "model-response": ModelResponse,
    "span": SpanRecord,
    "chain-line": ChainLine,
    "chain-head": ChainHead,
    "scene-summary": SceneSummary,
    "window-result": WindowResult,
    "clay-search-result": ClaySearchResult,
    "stac-search-result": StacSearchResult,
    "claim": Claim,
    "understanding": UnderstandingStatement,
    "check-ledger": CheckLedger,
    "sample-design": SampleDesign,
    "gold-draw": GoldDraw,
    "blind-item": BlindItem,
    "verifier-verdict": VerifierVerdict,
    "gold-label": GoldLabel,
    "typed-number": TypedNumber,
    "scorecard": Scorecard,
    "passport": TrustPassport,
    "manifest": Manifest,
    "bundle": ReportBundle,
}
