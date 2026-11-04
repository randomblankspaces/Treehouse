# Vote, round 1: OBS

**VOTE: REJECT.** There are two blocking items. Both are narrow, and I will switch to ACCEPT as soon as the replacement text is adopted. I accept everything else, including rows 10, 11, 12, 19 and 21. All six of my round-b blocking items are met by rows 14, 20 and 8, §3 Harnesses, §3 gateway and the §1 boundary.

## Blocking

**B1. §3 gateway `call` step 9 (with row 21): the recorded-source image placeholder breaks replay of real runs.**
- Current text: "Recorded sources attach a text placeholder instead."
- When a run is recorded live (K3/K4), the request carries `Image(sha256, bytes)`. When it is replayed from a pixel-free cassette, the same turn would carry `Text(placeholder)`. `ModelRequest.key()` then differs at the first imagery turn, so ReplayProvider raises a divergence.
- The result: the morning's real Bedrock runs (K5) can never be replayed, and the demo safety net exists only for synthetic data.

Replacement text:
> "9. For `imagery_window`, attach `Image(format, sha256, bytes_)`, with `bytes_` taken from `PixelCache` when present. Recorded and pixel-free sources attach the same block with `bytes_=None`. `key()` is identical with or without bytes. Live providers refuse an `Image` whose `bytes_` is None (`MissingPixels`); only ReplayProvider accepts one."

Add an acceptance test to P3/P4: a live-recorded request key equals the key of its pixel-free replay.

**B2. §2 `model_io` / §3 `key()` / §5.3 step 3: golden trace heads must not depend on PNG encoder bytes.**
- The demo asserts `fixtures/golden/heads.json`. If `Image.sha256` hashes the PNG bytes from `png.py` (zlib), any zlib build difference changes every key and head. zlib-ng versus classic zlib differs across Python builds (`zlib.ZLIB_RUNTIME_VERSION` is 1.3 here).
- So J8 could pass in CI and fail on a judge's Mac.

Replacement text, added to §2 under `Image`:
> "`Image.sha256` and `WindowResult.pixel_sha256` are sha256 of the decoded C-order uint8 array plus its shape string, never of encoded PNG or JPEG bytes. Encoded bytes are transport only and are never hashed into keys, traces or heads."

Add a test: re-encoding the same array at a different zlib level leaves `key()` and the trace head unchanged.

## Non-blocking suggestions

1. **Row 21's "UNVERIFIED" is now verified.** A tool annotated `-> mcp.types.CallToolResult` returns `content=[ImageContent]` together with `structuredContent` (test `scratchpad/obs/t6.py`: `['image'] {'scene_id': 'S1'} False`). Keep the PixelCache side channel tonight, which keeps pixels out of MCP payloads. Record that the stdio path is open via `CallToolResult`.
2. **§8 K5 `cassette export` and K6 `fetch_*` scripts have no W number.** Either add them to the W queue, or state that `RecordingProvider` writes pixel-free cassettes directly, so K5 is only a replay check.
3. **W2 contract test should cover images.** It should include a turn with an image inside `toolResult` (Strands `{"image":{"format","source":{"bytes"}}}` mapped to our `Image`), not just text tools.
4. **Name the span ops `gen_ai.operation.name`.** §3 span records should state that `op` maps to `gen_ai.operation.name` and that span names follow `invoke_agent {agent}`, `chat {model}` and `execute_tool {tool}`. Pin the semantic-conventions-genai repo ref in `versions.semconv_ref`.
5. **Run the C2 deadline check after every merge.** In §7, check C2 (P6 by 08:00) after every merge from H5 onward, not only at 07:15. P6 depends only on P3, so it can be pulled forward if P5 slips.
