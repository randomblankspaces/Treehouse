#!/usr/bin/env python3
"""Exactly one Kiro live invocation; retain actual evidence and stop its session."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(receipt):
    errors = []
    if not receipt.get("answer", "").strip() or not receipt.get("request_id"):
        errors.append("Runtime answer/request ID missing")
    if len(set(receipt.get("gateway_tools", []))) < 3:
        errors.append("Gateway catalog has fewer than three tools")
    calls = receipt.get("tool_calls", [])
    if not any(
        not call.get("is_error", True)
        and call.get("name") in receipt.get("gateway_tools", [])
        and call.get("request_id")
        for call in calls
    ):
        errors.append("No successful Gateway tool call with transport request ID")
    if not any(
        item.get("uri", "").startswith("s3://") and item.get("quote", "").strip()
        for item in receipt.get("citations", [])
    ):
        errors.append("No owned-document source URI and quote from KB")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kiro", action="store_true")
    parser.add_argument("--invoke", action="store_true")
    parser.add_argument(
        "--prompt",
        default="What is Treehouse's judge demonstration marker, and what three evidence steps does it name? Search the project document and cite the source.",
    )
    args = parser.parse_args(argv)
    if not args.invoke:
        print(
            "PLAN_NO_AWS_CALLS: --invoke --kiro makes one paid Runtime invocation; this proves nothing live yet."
        )
        return
    if not args.kiro or sys.platform == "darwin":
        parser.error("Live smoke must execute in the authorized non-Mac Kiro AWS terminal")
    import boto3
    from botocore.config import Config

    from treehouse.judge.aws import invoke_runtime

    config = json.loads(args.config.read_text())
    client = boto3.client(
        "bedrock-agentcore",
        region_name="us-east-1",
        config=Config(connect_timeout=5, read_timeout=120, retries={"total_max_attempts": 1}),
    )
    receipt = invoke_runtime(config, args.prompt, client=client)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    # Each browser request also has a new session. Its configured idle timeout is 60s.
    try:
        client.stop_runtime_session(
            agentRuntimeArn=config["runtime_arn"], runtimeSessionId=receipt["session_id"], qualifier="DEFAULT"
        )
    except Exception as error:
        print(
            f"Session stop failed ({type(error).__name__}); idle expiry remains 60 seconds", file=sys.stderr
        )
    errors = check(receipt)
    print(
        json.dumps(
            {
                "evidence_file": str(args.output),
                "checks_passed": not errors,
                "errors": errors,
                "request_id": receipt["request_id"],
            },
            indent=2,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
