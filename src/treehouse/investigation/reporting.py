"""Availability of historical held-out protocol measurements."""


from treehouse.paths import repo_root as repo_root


def protocol_panels(run):
    """The current sealed schema pins reference bytes, but contains no split content binding.

    An adjacent mutable split cannot establish a historical evaluation population. Explicit
    current comparisons use the server-owned reference route instead; old seals stay unchanged.
    """
    return None, "Historical held-out scores are unavailable: no split content is bound to this sealed run. Supply an explicit current server reference for a separately labelled comparison."


def deliberation_scores(result):
    """Named, separate observations; no blended cognition or accuracy score."""
    return [{"metric": name, "value": metric["value"], "unit": "ratio",
             "numerator": metric["numerator"], "denominator": metric["denominator"],
             "basis": result["basis"], "status": metric["status"],
             "reason": metric.get("reason")}
            for name, metric in result["metrics"].items()]
