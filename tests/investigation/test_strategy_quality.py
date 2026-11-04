"""Equal-sized strategies differ when they cover different reference objects."""
from test_investigation_acceptance import ScriptProvider, claim, numbers, reference


def test_equal_action_counts_can_produce_different_keyed_outcomes(context):
    store, card, config, execute, evaluate, _ = context
    productive = claim("a", .002, .002) + claim("b", .008, .008, "footbridge")
    repetitive = claim("a", .002, .002) + claim("b", .002, .002)
    good_provider, poor_provider = ScriptProvider(productive), ScriptProvider(repetitive)
    execute(store, card, config, good_provider, run_id="productive")
    execute(store, card, config, poor_provider, run_id="repetitive")
    assert len(good_provider.requests) == len(poor_provider.requests)
    good = numbers(evaluate(store, "productive", reference=reference()))
    poor = numbers(evaluate(store, "repetitive", reference=reference()))
    assert (good["catalog_tp"], good["catalog_fp"], good["catalog_fn"]) == (2, 0, 0)
    assert (poor["catalog_tp"], poor["catalog_fp"], poor["catalog_fn"]) == (1, 1, 1)
    assert good["catalog_recall"] > poor["catalog_recall"]
