"""CDK entry point: ``npx -y aws-cdk@2 synth`` (or ``deploy``) from this directory."""

from __future__ import annotations

import aws_cdk as cdk
from treehouse_infra import EvalStack, RunStoreStack

app = cdk.App()
ctx = app.node.try_get_context
# -c bootstrapless=true: only the asset-free run store, deployable with `aws cloudformation deploy` when
# `cdk bootstrap` is denied; the evaluator stack ships a Lambda asset and needs a bootstrapped account.
bootstrapless = str(ctx("bootstrapless")).lower() == "true"
RunStoreStack(app, "TreehouseRunStore", retention_days=int(ctx("retention_days") or 1), lock_mode=ctx("lock_mode") or "compliance",
              synthesizer=cdk.BootstraplessSynthesizer() if bootstrapless else None)
if not bootstrapless:
    EvalStack(app, "TreehouseEval", with_agentcore=str(ctx("agentcore")).lower() != "false")
app.synth()
