"""Render a run's plain-language narration to speech with Amazon Polly (neural).

    uv run --extra api python scripts/narrate_polly.py --store <store> --run <id> --out ui/public/narration/

Writes two files into ``--out``:
  <run>.mp3   the spoken narration (neural engine), chunks concatenated in order
  <run>.json  {run_id, text, sha256, voice, engine, chunks, sample_rate, created}

The UI plays the MP3 only when sha256(shown text) == the sidecar sha256; otherwise it falls back to the
browser's speech synthesiser. Text comes from ``treehouse.ui.narration`` (public snapshot only). Polly calls
cost a few cents for a demo run; this is not a Bedrock charge, but we still print the Bedrock budget first so
the operator sees it. Chunks are capped at 2,900 characters (Polly's neural synchronous limit is 3,000).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path

from treehouse import service
from treehouse.store.local import LocalStore
from treehouse.ui.narration import narration_text, text_sha256
from treehouse.ui.snapshot import snapshot as build_snapshot

CHUNK_LIMIT = 2900
DEFAULT_VOICE = "Joanna"
ENGINE = "neural"


def chunk_text(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Split on sentence boundaries, never exceeding ``limit`` characters per chunk."""
    chunks: list[str] = []
    current = ""
    for sentence in _sentences(text):
        if len(sentence) > limit:
            # A single over-long sentence: hard-split on spaces.
            for piece in _hard_split(sentence, limit):
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(piece)
            continue
        if len(current) + len(sentence) + (1 if current else 0) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks or [""]


def _sentences(text: str) -> list[str]:
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in ".!?" and len(buf) > 1:
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def _hard_split(text: str, limit: int) -> list[str]:
    words, out, cur = text.split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > limit:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def synthesize(chunks: list[str], *, voice: str, region: str) -> bytes:
    """Call Amazon Polly neural per chunk and concatenate the MP3 streams."""
    import boto3

    polly = boto3.client("polly", region_name=region)
    audio = bytearray()
    for chunk in chunks:
        if not chunk:
            continue
        response = polly.synthesize_speech(Text=chunk, OutputFormat="mp3", VoiceId=voice, Engine=ENGINE)
        audio.extend(response["AudioStream"].read())
    return bytes(audio)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", required=True, help="path to the sealed run store")
    ap.add_argument("--run", required=True, help="run id to narrate")
    ap.add_argument("--out", default="ui/public/narration", help="output directory for <run>.mp3 and <run>.json")
    ap.add_argument("--voice", default=DEFAULT_VOICE, help="Polly neural voice id (default Joanna)")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--text-only", action="store_true", help="write only the text sidecar; do not call Polly")
    args = ap.parse_args(argv)

    store = LocalStore(Path(args.store))
    run = service.load_sealed(store, args.run)
    snap = build_snapshot(store, run)
    text = narration_text(snap)
    sha = text_sha256(text)
    chunks = chunk_text(text)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sidecar = {"run_id": args.run, "text": text, "sha256": sha, "voice": args.voice,
               "engine": ENGINE, "chunks": len(chunks), "sample_rate": "24000",
               "created": _dt.datetime.now(_dt.UTC).isoformat()}

    if not args.text_only:
        try:
            audio = synthesize(chunks, voice=args.voice, region=args.region)
        except Exception as exc:  # noqa: BLE001 - surface any AWS/credential/region error plainly
            print(f"Polly synthesis failed ({type(exc).__name__}: {exc}).", file=sys.stderr)
            print("Wrote the text sidecar only; the UI will fall back to browser speech.", file=sys.stderr)
            args.text_only = True
        else:
            (out / f"{args.run}.mp3").write_bytes(audio)
            sidecar["bytes"] = len(audio)

    (out / f"{args.run}.json").write_text(json.dumps(sidecar, indent=2) + "\n")
    where = "text sidecar" if args.text_only else f"{len(chunks)} chunk(s) of audio + sidecar"
    print(f"narrate_polly: wrote {where} for {args.run} to {out} (sha256 {sha[:12]}…, voice {args.voice}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
