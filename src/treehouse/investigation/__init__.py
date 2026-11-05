"""Opt-in agent investigations and read-only, independent sealed-run evaluation."""

from functools import partial

import yaml

from treehouse.investigation.classifier import BuiltinVisionClassifier, VisionClassifier
from treehouse.investigation.evaluation import database_geojson, evaluate_investigation, export_database
from treehouse.investigation.review import review_investigation
from treehouse.investigation.runtime import InvestigationSession
from treehouse.runner import RunSpec, execute
from treehouse.schemas.config import Budget
from treehouse.schemas.model_io import ProviderEvent


class _ObservedProvider:
    """Add price availability to opt-in traces without changing the default loop or provider."""

    def __init__(self, provider):
        self.provider = provider
        self.model_turns = {}

    def __getattr__(self, name):
        return getattr(self.provider, name)

    async def complete(self, *args, **kwargs):
        response = await self.provider.complete(*args, **kwargs)
        event = ProviderEvent(name="treehouse.investigation.model_pricing",
                              attributes={"pricing": "unpriced" if response.cost_usd is None else "reported"})
        response = response.model_copy(update={"events": [*response.events, event]})
        self.model_turns[f"t-{kwargs['trial_index']}"] = response
        return response


def run_investigation(store, card, config, provider, *, run_id, classifier=None, server_factory=None):
    """Run an explicitly injected provider through the ordinary runner/gateway/seal path.

    ``server_factory`` is trusted local Python, not an OS isolation boundary. Its optional
    keyword inputs are card, ledger, pixels, default_servers; it returns MCP servers.
    """
    if "record_decision" not in card.tools_allowed:
        raise ValueError("investigation requires record_decision in the task tool allowlist")
    if config.task_ref != card.ref():
        raise ValueError("config.task_ref must match the investigation task card")
    if card.budget.enabled:
        limits = {}
        for axis in ("usd", "tool_calls", "bytes", "wall_s", "tokens"):
            values = [v for v in (getattr(card.budget, axis),
                                  getattr(config.budget, axis) if config.budget.enabled else None) if v is not None]
            limits[axis] = min(values) if values else None
        config = config.model_copy(update={"budget": Budget(**limits)})
    observed = _ObservedProvider(provider)
    factory = partial(InvestigationSession, card, classifier=classifier, server_factory=server_factory,
                      model_turns=observed.model_turns)
    return execute(store, RunSpec(run_id=run_id, card=card, config=config, provider=observed,
                                 card_bytes=yaml.safe_dump(card.model_dump(mode="json")).encode(),
                                 investigation=factory))


__all__ = ["run_investigation", "evaluate_investigation", "export_database",
           "database_geojson", "review_investigation", "VisionClassifier", "BuiltinVisionClassifier"]
