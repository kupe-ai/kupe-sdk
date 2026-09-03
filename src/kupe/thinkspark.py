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


def _tune_backend(device: str) -> None:
    """Per-device knobs that matter for per-frame latency.

    Verified-safe defaults across CPU, Apple MPS, and every consumer/datacenter CUDA
    card (3060/4060/3090/4090/5090, L4, H100, RTX 6000). Nothing here changes model
    outputs — only how the kernels are scheduled.
    """
    import torch

    torch.set_grad_enabled(False)

    if device == "cuda":
        # TF32 matmuls: large speedup on Ampere and newer, ignored on older cards
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        torch.backends.cudnn.benchmark = True
    elif device == "cpu":
        # one frame at a time is latency-bound, not throughput-bound; oversubscribing
        # threads adds sync overhead per 80 ms frame
        try:
            import os as _os
            torch.set_num_threads(min(4, _os.cpu_count() or 4))
        except Exception:
            pass

DEFAULT_MODEL = "anuj-inavlabs/Kupe-ThinkSpark-Realtime-270M"
# Fallback only. The model repo ships its own tokenizer + config, so nothing is fetched
# from the gated Gemma repo — see _resolve_repo().
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
        revision: git revision/branch/tag in the model repo.
        subfolder: path inside the repo, e.g. "phase2/runs/<run-id>/step5500".
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        device: str = "auto",
        *,
        agent_text: str = "",
        hf_token: str | None = None,
        revision: str | None = None,
        subfolder: str = "",
    ):
        try:
            import torch
            from huggingface_hub import snapshot_download
            from transformers import AutoTokenizer
        except ImportError as e:  # pragma: no cover - dependency guard
            raise ImportError(_MISSING_DEPS) from e

        from kupe._thinkspark import vocab
        from kupe._thinkspark.inference import StreamingReferee
        from kupe._thinkspark.mimi_codec import MimiEncoder, StreamingMimiEncoder
        from kupe._thinkspark.model import ThinkSparkModel

        token = hf_token or os.environ.get("HF_TOKEN")

        if device == "auto":
            device = (
                "cuda" if torch.cuda.is_available()
                else "mps" if torch.backends.mps.is_available()
                else "cpu"
            )
        self.device = device
        _tune_backend(device)

        # Pull the whole checkpoint folder: weights + tokenizer + config. This repo is
        # self-contained, so google/gemma-3-270m (gated) is never touched.
        pat = f"{subfolder}/" if subfolder else ""
        local = snapshot_download(
            repo_id=model, token=token, revision=revision,
            allow_patterns=[f"{pat}*.json", f"{pat}model.pt"],
        )
        if subfolder:
            local = os.path.join(local, subfolder)

        has_own = os.path.exists(os.path.join(local, "config.json"))
        tok_src = local if os.path.exists(os.path.join(local, "tokenizer.json")) else BASE_MODEL

        tok = AutoTokenizer.from_pretrained(tok_src, token=token)
        # the checkpoint's tokenizer already has these; add_special_tokens is a no-op then
        tok.add_special_tokens({"additional_special_tokens": vocab.ALL_SPECIAL_TOKENS})
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token

        self._encoder = MimiEncoder(device=device)
        # streaming encoder: keeps rolling context so per-frame Mimi tokens carry the same
        # left context they had offline (a bare per-frame encode feeds the model a stream
        # of context-less "first frames" — see mimi_codec.StreamingMimiEncoder).
        self._stream_encoder = StreamingMimiEncoder(self._encoder)

        net = ThinkSparkModel(
            base_model=BASE_MODEL,
            codebook_size=self._encoder.codebook_size,
            hf_token=token,
            gradient_checkpointing=False,
            config_source=local if has_own else None,
        )
        net.resize_token_embeddings(len(tok))

        weights = os.path.join(local, "model.pt")
        state = torch.load(weights, map_location=device)
        missing, unexpected = net.load_state_dict(state, strict=False)
        if len(missing) > 20:
            raise RuntimeError(
                f"checkpoint does not fit the model: {len(missing)} missing / "
                f"{len(unexpected)} unexpected keys. Wrong repo or revision?"
            )

        # Precision: bf16 on CUDA (the training precision — halves memory traffic and is
        # the single biggest per-frame speedup on Ampere+), fp32 on MPS/CPU where bf16
        # kernels are slower or unavailable. The streaming referee builds ALL front-end
        # input tensors (prosody etc.) in the model's own dtype, so there is no more
        # "mat1 and mat2 must have the same dtype" mismatch that forced fp32 before.
        # The Gemma3 backbone was constructed in bf16. Keep bf16 ONLY on CUDA; force
        # fp32 on MPS/CPU. Apple's MPS has no bf16 matmul kernel — a bf16 module there
        # aborts with "Destination NDArray and Accumulator NDArray cannot have different
        # datatype in MPSNDArrayMatrixMultiplication". fp32 is correct and plenty fast.
        net = net.to(device).eval()
        net = net.to(torch.bfloat16) if device == "cuda" else net.float()
        for p_ in net.parameters():
            p_.requires_grad_(False)

        self._referee = StreamingReferee(
            net, tok, system_prompt=DEFAULT_SYSTEM, device=device,
        )
        self._referee.set_context(agent_text=agent_text)
        self.last_encode_ms = 0.0
        self._warmup()

    def _warmup(self) -> None:
        """Prime the streaming encoder + KV-cache decode at the real shapes so the first
        live frame is not the slow one (kernel autotune, cache allocation, lazy weights)."""
        import numpy as np
        from kupe._thinkspark.inference import FrameInput

        samples = int(SAMPLE_RATE * FRAME_MS / 1000) * 2
        dummy = np.zeros(samples, dtype=np.float32)
        enc = self._stream_encoder.push(dummy, SAMPLE_RATE)
        for i in range(enc.num_frames):
            self._referee.step(
                FrameInput(cb0=int(enc.cb0[i]), energy=float(enc.energy[i]),
                           f0=float(enc.f0[i]), agent_state="IDLE")
            )
        # exercise the incremental path and the spoken decoder too
        self._referee.generate_spoken("IDLE")
        self._referee.reset()
        self._stream_encoder.reset()
        if self.device == "mps":
            import torch
            torch.mps.synchronize()

    def set_context(self, agent_text: str = "", stt_partial: str = "") -> None:
        """Update what the agent is saying — decisions depend on it."""
        self._referee.set_context(agent_text=agent_text, stt_partial=stt_partial)

    def reset(self) -> None:
        """Clear rolling audio history + KV cache + encoder context (turn boundary)."""
        self._referee.reset()
        self._stream_encoder.reset()

    def generate_spoken(self, agent_state: str = "IDLE") -> str:
        """Decode a short spoken back-channel / thinking-sound from the current context.

        Call this ONLY when the orchestrator has decided to speak — it is deliberately
        NOT run every frame (that was the old latency bug). Returns "" for the silent
        case. Decodes from a clone of the live cache, so streaming state is untouched.
        """
        return self._referee.generate_spoken(agent_state)

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
            enc = self._stream_encoder.push(chunk, sample_rate)
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
                # spoken text is decoupled: step() no longer decodes it every frame.
                # The orchestrator calls generate_spoken() only when it decides to speak.
                yield Decision(result.flag, "", latency)

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
