"""K1 capability probe: writes ``treehouse.aws-capabilities/v1`` JSON. Never aborts; at most $3 of Bedrock.

    uv run python scripts/aws_probe.py --region us-east-1 --out aws-capabilities.json
    uv run treehouse probe import aws-capabilities.json

Spend goes to the repo ledger ``.spend/spend.jsonl`` (or ``$TREEHOUSE_SPEND_LEDGER``), which must exist:
run ``uv run treehouse budget init`` once first. The region defaults to us-east-1 everywhere (the price
table and registry are us-east-1). Requires ``uv sync --extra aws``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from treehouse.probe import LOG_GROUP, PROBE_CAP_USD, Probe, default_client_factory
from treehouse.providers.registry import ModelRegistry
from treehouse.providers.spend import SpendLedger


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", default="us-east-1", help="default us-east-1 (ignores AWS_REGION on purpose)")
    ap.add_argument("--out", type=Path, default=Path("aws-capabilities.json"))
    ap.add_argument("--models", type=Path, default=None, help="model registry (default config/models.yaml)")
    ap.add_argument("--bucket", default=None, help="S3 bucket to check for versioning and Object Lock")
    ap.add_argument("--log-group", default=LOG_GROUP, help="CloudWatch log group for the PutLogEvents check")
    ap.add_argument("--no-log-write", action="store_true", help="skip the CloudWatch PutLogEvents check")
    ap.add_argument("--cap-usd", type=float, default=PROBE_CAP_USD, help="probe cap (may only be lowered)")
    a = ap.parse_args(argv)
    ledger = SpendLedger()
    if not ledger.initialized:
        print(f"REFUSED: spend ledger {ledger.path} does not exist. Run `uv run treehouse budget init` once "
              "(first live step only) or point TREEHOUSE_SPEND_LEDGER at the existing ledger.", file=sys.stderr)
        return 2
    probe = Probe(default_client_factory(a.region), region=a.region, registry=ModelRegistry.load(a.models),
                  ledger=ledger, bucket=a.bucket, log_group=None if a.no_log_write else a.log_group,
                  cap_usd=a.cap_usd)
    report = probe.run()
    a.out.write_text(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    print(f"wrote {a.out}: {report.summary}; probe spend reserved ${report.spend.reserved_usd:.2f}, "
          f"committed ${report.spend.committed_usd:.4f} (estimated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
