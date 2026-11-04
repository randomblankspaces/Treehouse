# Strands in Treehouse (W2)

Strands Agents (`strands-agents` 1.63, the `strands` extra) is the agent engine for live runs. Treehouse keeps
the parts that make a run auditable. Every Strands API named here was checked against the installed package.

## What runs on Strands

| Piece | Module | Strands APIs |
|---|---|---|
| Worker harness (`harness: strands`) | `harness/strands_harness.py` `StrandsHarness` | `strands.Agent(model, tools, system_prompt, tool_executor, callback_handler=None, conversation_manager, retry_strategy=None)`, `Agent.invoke_async`, `tools.executors.SequentialToolExecutor`, `agent.conversation_manager.NullConversationManager`, `types.tools.AgentTool`, `hooks.BeforeToolCallEvent` (via `agent.hooks.add_callback`), `types.exceptions.EventLoopException` / `MaxTokensReachedException` |
| Model adapter | `providers/strands_model.py` `TreehouseStrandsModel` | subclass of `strands.models.model.Model` (`stream`, `update_config`, `get_config`, `structured_output`); emits Converse stream events (`messageStart`, `contentBlockStart/Delta/Stop`, `messageStop`, `metadata`) |
| Window-fetching verifier | `verifier/agent.py` `StrandsVerifier` | a `StrandsHarness` run whose gateway lists only `imagery_window`, `stac_search` |
| Embedding search agent | `tools/search_agent.py` + `StrandsHarness` | the same agent, given the `embedding_filter` / `embedding_nearest` tools |

## What stays our code, and why

- **Every model call is `chat_turn`** (`harness/plain_loop.py`), shared by PlainLoop, StrandsHarness and both
  verifiers. Strands never calls Bedrock itself, so the cassette (`(role, trial_index, turn)`), the spend
  ledger, the budget guard, the chat span and the hash chain record every call. A Strands run replays from its
  cassette offline, and the plain loop can replay the same cassette.
- **Every tool call is `ToolGateway.call`**: policy, the key decoy, budget, meter, tool cassette and the trace.
  A tool name the gateway does not list goes to the gateway too (a `BeforeToolCallEvent` hook), so a blocked
  call is on the trace exactly as under PlainLoop instead of Strands answering "Unknown tool".
- **Exact requests.** The request is rebuilt from Strands' messages, but assistant turns and tool results are
  the objects Treehouse produced (side channel), so image `sha256`/bytes survive and request keys equal
  PlainLoop's. The contract test checks identical request keys, claims, blobs and spans (apart from
  `treehouse.harness`).
- **Verifier default is not an agent** (DEFENSE-BOOK #15): `ConverseVerifier` makes one tool-free call per
  `BlindItem`, with the windows passed in. That is cheaper, varies less and replays. Both verifiers build their prompt from
  `BlindItem` fields only; a hypothesis test checks that changing worker label, confidence or reason leaves the
  verifier requests byte-identical. An unparseable answer counts as `cannot_assess`.
- **Search routing** (AWS-BLUEPRINT §2): up to 1 M vectors stays local (numpy, replayable). Above that,
  filters go to Athena (parameterized SQL) and nearest neighbours to S3 Vectors (`query_vectors`, cosine).
  The AWS request builders are Stubber-tested; the live twin is `@live`.
- **No-tool baseline** (DEFENSE-BOOK #10): the gateway is built with `tools=NO_TOOL_TOOLS` (claim tools only).
  Imagery calls are refused on the trace, and `baseline_gap` reads the score difference.
- **Strands OTel stays off.** It is a no-op while no global tracer provider is set. Treehouse's own tracer is
  the record.

## Known gaps

- On `max_tokens`, Strands raises before running that turn's tool uses (PlainLoop would run them). Both end
  `stop="error"`.
- Athena execution parameters and the S3 Vectors metadata filter syntax are checked against the botocore
  model only. They are UNVERIFIED live until Kiro runs the `@live` twin.
