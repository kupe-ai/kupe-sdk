"""Stdin/stdout JSON-lines bridge used by kupe-sdk's (npm) ThinkSpark class.

Not meant to be run by hand — invoked as a subprocess:
    python -m kupe.thinkspark_bridge --source mic
    python -m kupe.thinkspark_bridge --source stdin   # raw float32 frames on stdin

Prints one JSON decision per line as frames arrive.
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from kupe.thinkspark import ThinkSpark


def _stdin_frames(sample_rate: int):
    frame_bytes = int(sample_rate * 0.08) * 4  # float32
    buf = b""
    while True:
        chunk = sys.stdin.buffer.read(65536)
        if not chunk:
            break
        buf += chunk
        while len(buf) >= frame_bytes:
            piece, buf = buf[:frame_bytes], buf[frame_bytes:]
            yield np.frombuffer(piece, dtype=np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--sample-rate", type=int, default=24_000)
    ap.add_argument("--source", choices=["mic", "stdin"], default="mic")
    args = ap.parse_args()

    kwargs = {"device": args.device}
    if args.model:
        kwargs["model"] = args.model
    ts = ThinkSpark(**kwargs)

    source = "mic" if args.source == "mic" else _stdin_frames(args.sample_rate)
    for d in ts.stream(source, sample_rate=args.sample_rate):
        print(json.dumps({"flag": d.flag, "spoken": d.spoken, "latency_ms": d.latency_ms}), flush=True)


if __name__ == "__main__":
    main()
