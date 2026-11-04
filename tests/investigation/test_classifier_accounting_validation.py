"""Untrusted classifier accounting must not create a negative or fictitious charge."""
import math

import pytest
from test_classifier_boundary import CapturingClassifier, ImageThenClassify


class MalformedAccounting(CapturingClassifier):
    def __init__(self, field, value):
        super().__init__()
        self.field, self.value = field, value

    async def classify(self, *, window, image, cls):
        result = await super().classify(window=window, image=image, cls=cls)
        if self.field == "cost_usd":
            result["cost_usd"] = self.value
        else:
            result["usage"][self.field] = self.value
        return result


@pytest.mark.parametrize(("field", "value"), [
    ("cost_usd", -1), ("cost_usd", True), ("cost_usd", float("nan")),
    ("cost_usd", float("inf")), ("input_tokens", -1), ("output_tokens", True),
    ("input_tokens", float("nan")), ("output_tokens", 1.5),
])
def test_malformed_classifier_accounting_is_rejected_or_reported_unpriced(context, field, value):
    store, card, config, execute, evaluate, _ = context
    classifier = MalformedAccounting(field, value)
    try:
        execute(store, card, config, ImageThenClassify(), run_id="malformed", classifier=classifier)
    except (ValueError, RuntimeError):
        return
    assert classifier.calls, "the malformed accounting must reach the classifier boundary"
    try:
        report = evaluate(store, "malformed")
    except (ValueError, RuntimeError):
        return  # A corrupt or non-finite ledger fails closed.
    price = report["cost"]["numbers"]["classifier_usd"]
    assert price["value"] is None or (math.isfinite(price["value"]) and price["value"] >= 0)
    decision = next(d for d in report["decisions"] if d["action_id"] == "classify")
    if field == "cost_usd":
        assert decision["action"]["status"] != "success" or (price["value"] is None and price["reasons"])
    else:
        assert decision["action"]["status"] != "success" or report["process"]["limitations"]
