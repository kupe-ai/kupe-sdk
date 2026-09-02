"""Kupe-ThinkSpark-Realtime — local audio-in, decision-out streaming.

    pip install kupe[thinkspark]   # pulls in the `thinkspark` runtime package

Not a floor controller. Just: give it audio, get decisions back.
"""

from __future__ import annotations

import queue
from collections.abc import Generator, Iterable

DEFAULT_MODEL = "anuj-inavlabs/Kupe-ThinkSpark-Realtime-270M"


class Decision:
    __slots__ = ("flag", "spoken", "latency_ms")

    def __init__(self, flag: str, spoken: str, latency_ms: float):
        self.flag = flag
        self.spoken = spoken
        self.latency_ms = latency_ms

    def __repr__(self) -> str:
        return f"Decision(flag={self.flag!r}, latency_ms={self.latency_ms:.2f})"


class ThinkSpark:
    """Streams 80ms audio frames through Kupe-ThinkSpark-Realtime-270M."""

    def __init__(self, model: str = DEFAULT_MODEL, device: str = "auto"):
        try:
            from thinkspark import ThinkSparkPipeline
        except ImportError as e:
            raise ImportError("pip install thinkspark") from e
        self._pipeline = ThinkSparkPipeline.from_pretrained(model, device=device)

    def stream(
        self,
        source: str | Iterable = "mic",
        *,
        sample_rate: int = 24_000,
    ) -> Generator[Decision, None, None]:
        """Yield a Decision for every audio frame.

        source="mic" reads the default microphone. Or pass any iterable of
        float32 numpy arrays — audio from a call, a websocket, a file, anything.
        """
        frames = self._mic_frames(sample_rate) if source == "mic" else source
        for chunk in frames:
            result = self._pipeline(chunk, sample_rate=sample_rate)
            yield Decision(result.flag, getattr(result, "spoken", ""), result.latency_ms)

    @staticmethod
    def _mic_frames(sample_rate: int):
        try:
            import sounddevice as sd
        except ImportError as e:
            raise ImportError("pip install sounddevice") from e

        frame_samples = int(sample_rate * 0.08)
        q: queue.Queue = queue.Queue()

        def _cb(indata, frames_, time_info, status):
            q.put(indata[:, 0].copy())

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32",
                            blocksize=frame_samples, callback=_cb):
            while True:
                yield q.get()
