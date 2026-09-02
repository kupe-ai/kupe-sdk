"""Kupe-ThinkSpark-Realtime — local audio-in, decision-out streaming.

    pip install kupe[thinkspark]

Downloads Kupe-ThinkSpark-Realtime-270M from Hugging Face on first use and runs it
locally on GPU, Apple Silicon, or CPU. Give it audio, get decisions back.

    from kupe import ThinkSpark

    ts = ThinkSpark()
    for decision in ts.stream(source="mic"):
        print(decision.flag, decision.latency_ms)
"""

from __future__ import annotations

import os
import queue
import time
from collections.abc import Generator, Iterable
from dataclasses import dataclass

DEFAULT_MODEL = "anuj-inavlabs/Kupe-ThinkSpark-Realtime-270M"
BASE_MODEL = "google/gemma-3-270m"
SAMPLE_RATE = 24_000
FRAME_MS = 80
DEFAULT_SYSTEM = (
    "You are a polite Indic voice agent. Decide when to listen, hold, "
    "interrupt, or back-channel."
)

_MISSING_DEPS = (
    "ThinkSpark needs the local inference extras:\n"
    "    pip install 'kupe[thinkspark]'\n"
    "(installs torch, transformers, numpy, huggingface_hub)"
)


@dataclass
class Decision:
    """One control decision for one 80 ms audio frame."""

    flag: str
    spoken: str = ""
    latency_ms: float = 0.0


class ThinkSpark:
    """Streams 80 ms audio frames through Kupe-ThinkSpark-Realtime-270M.

    Args:
        model: Hugging Face repo id. Defaults to the public Kupe model.
        device: "auto" (default), "cuda", "mps", or "cpu".
        agent_text: what your agent is currently saying, used as context.
        hf_token: Hugging Face token; falls back to $HF_TOKEN.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        device: str = "auto",
        *,
        agent_text: str = "",
        hf_token: str | None = None,
    ):
        try:
            import torch
            from huggingface_hub import hf_hub_download
            from transformers import AutoTokenizer
        except ImportError as e:  # pragma: no cover - dependency guard
            raise ImportError(_MISSING_DEPS) from e

        from kupe._thinkspark import vocab
        from kupe._thinkspark.inference import StreamingReferee
        from kupe._thinkspark.mimi_codec import MimiEncoder
        from kupe._thinkspark.model import ThinkSparkModel

        token = hf_token or os.environ.get("HF_TOKEN")

        if device == "auto":
            device = (
                "cuda" if torch.cuda.is_available()
                else "mps" if torch.backends.mps.is_available()
                else "cpu"
            )
        self.device = device

        tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=token)
        tok.add_special_tokens({"additional_special_tokens": vocab.ALL_SPECIAL_TOKENS})
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token

        self._encoder = MimiEncoder(device=device)

        net = ThinkSparkModel(
            base_model=BASE_MODEL,
            codebook_size=self._encoder.codebook_size,
            hf_token=token,
            gradient_checkpointing=False,
        )
        net.resize_token_embeddings(len(tok))

        weights = hf_hub_download(repo_id=model, filename="model.pt", token=token)
        state = torch.load(weights, map_location=device)
        net.load_state_dict(state, strict=False)

        self._referee = StreamingReferee(
            net.to(device).eval(), tok, system_prompt=DEFAULT_SYSTEM, device=device
        )
        self._referee.set_context(agent_text=agent_text)
        self.last_encode_ms = 0.0
        self._warmup()

    def _warmup(self) -> None:
        """Compile encoder + referee at the mic chunk shape so frame 1 is not 10s+."""
        import numpy as np
        from kupe._thinkspark.inference import FrameInput

        samples = int(SAMPLE_RATE * FRAME_MS / 1000) * 2
        dummy = np.zeros(samples, dtype=np.float32)
        enc = self._encoder.encode_waveform(dummy, SAMPLE_RATE)
        for i in range(enc.num_frames):
            self._referee.step(
                FrameInput(
                    cb0=int(enc.cb0[i]),
                    energy=float(enc.energy[i]),
                    f0=float(enc.f0[i]),
                    agent_state="IDLE",
                )
            )
        self._referee.reset()
        if self.device == "mps":
            import torch
            torch.mps.synchronize()

    def set_context(self, agent_text: str = "", stt_partial: str = "") -> None:
        """Update what the agent is saying — decisions depend on it."""
        self._referee.set_context(agent_text=agent_text, stt_partial=stt_partial)

    def stream(
        self,
        source: str | Iterable = "mic",
        *,
        sample_rate: int = SAMPLE_RATE,
        agent_state: str = "IDLE",
    ) -> Generator[Decision, None, None]:
        """Yield a Decision per 80 ms frame.

        agent_state is one of IDLE, LLM_GEN, TTS_SPEAKING, TTS_DONE — decisions
        depend on it (barge-in only means something while TTS_SPEAKING).

        source="mic" reads the default microphone. Otherwise pass any iterable of
        float32 numpy arrays — audio from a call leg, a websocket, a file, anything.
        Chunks of any length are fine; they are re-framed internally.
        """
        from kupe._thinkspark.inference import FrameInput

        frames = self._mic_chunks(sample_rate) if source == "mic" else source

        for chunk in frames:
            t0 = time.perf_counter()
            enc = self._encoder.encode_waveform(chunk, sample_rate)
            self.last_encode_ms = (time.perf_counter() - t0) * 1000.0

            for i in range(enc.num_frames):
                t1 = time.perf_counter()
                result = self._referee.step(
                    FrameInput(
                        cb0=int(enc.cb0[i]),
                        energy=float(enc.energy[i]),
                        f0=float(enc.f0[i]),
                        agent_state=agent_state,
                    )
                )
                latency = getattr(result, "decode_ms", None)
                if latency is None:
                    latency = (time.perf_counter() - t1) * 1000.0
                yield Decision(result.flag, getattr(result, "spoken", "") or "", latency)

    @staticmethod
    def _mic_chunks(sample_rate: int):
        try:
            import sounddevice as sd
        except ImportError as e:  # pragma: no cover - dependency guard
            raise ImportError("microphone capture needs: pip install sounddevice") from e

        # 2 frames per chunk: 160 ms of buffering, the responsiveness/overhead sweet spot
        blocksize = int(sample_rate * FRAME_MS / 1000) * 2
        q: queue.Queue = queue.Queue()

        def _cb(indata, frames_, time_info, status):
            q.put(indata[:, 0].copy())

        with sd.InputStream(
            samplerate=sample_rate, channels=1, dtype="float32",
            blocksize=blocksize, callback=_cb,
        ):
            while True:
                yield q.get()
