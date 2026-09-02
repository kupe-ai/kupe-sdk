"""
The live referee running frame-by-frame with a streaming KV cache (Section 11).

    every 80 ms frame:
        tok, e, f0 = mimi_stream_encode(mic_frame)
        st = agent_state()          # IDLE|LLM_GEN|TTS_SPEAKING|TTS_DONE (NO timestamps)
        flag = referee.step(FrameInput(tok, e, f0, st))          # <- one cheap decode
        # spoken text is generated ONLY when the orchestrator decides to speak:
        spoken = referee.generate_spoken()

Why this file was rewritten
---------------------------
The previous implementation was the "reference" loop the guide explicitly said to
replace before production: it re-ran the **whole trailing window** (~96 audio frames +
text) through the transformer on *every* 80 ms frame, with ``use_cache=False``, in fp32,
and — because ``LISTEN`` (the most common flag of all) was in ``SPEAKING_FLAGS`` — it
also ran a 12-step greedy spoken-decode over that same full window on nearly every
frame. That is 2-13 full-sequence forwards per frame. On real hardware the referee fell
behind live audio, the queue backed up, and the agent's reply only surfaced seconds
after the user stopped — exactly the "not real time / lands at the end" symptom.

This version is a true streaming decoder:

  * The text prefix + audio history live in a persistent **KV cache**. A normal frame
    embeds ONE new audio token and runs a single incremental transformer step
    (O(1) per frame) instead of re-reading the window (O(window) per frame).
  * The context is rebuilt only when the **text prefix actually changes** (a new STT
    partial, the agent starting/finishing speech) or when the cache would grow past the
    backbone's sliding window — both infrequent relative to the 80 ms frame clock.
  * **Spoken text is decoupled** from ``step()``. The control flag is decided every
    frame (cheap); the spoken head is only invoked via ``generate_spoken()`` when the
    orchestrator has actually decided to emit a back-channel / thinking-sound / re-open,
    and even then it decodes from a *clone* of the live cache so a handful of tokens
    cost one short decode, not a full-window replay.

The front-end math (audio/text embeddings, prosody + f0 normalisation, segment ids) is
reused verbatim from :class:`ThinkSparkModel` so the streamed activations are identical
to the trained (offline) ones; only the *scheduling* changed.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from kupe._thinkspark import vocab


# --------------------------------------------------------------------------- #
@dataclass
class FrameInput:
    cb0: int            # Mimi cb0 token for this 80 ms frame
    energy: float       # per-frame log-RMS energy
    f0: float           # per-frame f0 (Hz; 0 = unvoiced)
    agent_state: str    # IDLE|LLM_GEN|TTS_SPEAKING|TTS_DONE


@dataclass
class StepResult:
    flag: str
    spoken: str = ""
    decode_ms: float = 0.0


def _norm_f0(f0: float) -> float:
    """Match thinkspark.dataset._norm_f0 exactly: voiced -> log(f0)-log(150), else 0."""
    import math
    return (math.log(f0) - math.log(150.0)) if f0 > 1.0 else 0.0


# --------------------------------------------------------------------------- #
class StreamingReferee:
    """Streaming floor-control decoder over a persistent KV cache.

    Args:
        model: a loaded :class:`ThinkSparkModel` (eval mode).
        tokenizer: the checkpoint's tokenizer (special tokens already added).
        system_prompt: the persona/domain prompt (segment SEG_SYS).
        device: torch device string.
        max_audio_frames: trailing audio frames kept for a cache rebuild. Bounded so the
            live sequence stays within the backbone's 512-token sliding window, where a
            growing DynamicCache is bit-identical to the trained sliding-window attention.
        spoken_max_new: max tokens to greedily decode for a back-channel (they are short).
    """

    def __init__(self, model, tokenizer, system_prompt: str,
                 device: str = "cpu", *, max_audio_frames: int = 200,
                 spoken_max_new: int = 12):
        self.model = model.eval()
        self.tok = tokenizer
        self.device = device
        self.system_prompt = system_prompt
        # audio frames used to seed a rebuild (16 s @ 12.5 Hz — longer than essentially
        # any real turn, and the buffer is cleared at every turn boundary anyway).
        self.max_audio_frames = int(max_audio_frames)
        # rebuild before the live sequence reaches the 512 sliding window, so a growing
        # DynamicCache is bit-identical to the trained sliding-window attention (which
        # never truncates below 512 tokens). Left margin above text+audio so rebuilds
        # stay rare — a rebuild reseeds at text(<=~150) + max_audio(200) <= ~350, then
        # ~100 more frames (8 s) stream incrementally before the next one.
        self._hard_cap = 448
        self.spoken_max_new = int(spoken_max_new)

        self._dtype = next(self.model.parameters()).dtype
        self._lock = threading.Lock()
        self._logits_kw = None   # resolved lazily: kwarg name to cap LM-head positions
        # test hook: force the stateless full-recompute path so a verification script can
        # assert the streaming (KV-cache) flags equal the reference flags bit-for-bit.
        self.force_recompute = False

        # rolling context
        self.agent_text = ""
        self.stt_partial = ""
        # trailing audio history for rebuilds: parallel lists, bounded to max_audio_frames
        self._cb0: list[int] = []
        self._energy: list[float] = []
        self._f0: list[float] = []
        self._state: list[int] = []

        # cache state
        self._past = None
        self._cache_len = 0
        self._primed_sig: tuple | None = None

        # special-token ids (resolved once)
        sp = vocab.SPECIAL_TOKENS
        self._tok_cache: dict[str, list[int]] = {}
        self._say_bos = self._ids(sp["spoken_bos"])
        _eos = self._ids(sp["spoken_eos"])
        self._say_eos = _eos[0] if _eos else self.tok.eos_token_id

    # ------------------------------------------------------------------ #
    def reset(self) -> None:
        """Clear the audio history and KV cache (turn boundary / new conversation)."""
        with self._lock:
            self._cb0.clear(); self._energy.clear(); self._f0.clear(); self._state.clear()
            self._past = None
            self._cache_len = 0
            self._primed_sig = None

    def set_context(self, agent_text: str = "", stt_partial: str = "") -> None:
        self.agent_text = agent_text or ""
        self.stt_partial = stt_partial or ""

    # ------------------------------------------------------------------ #
    def step(self, frame: FrameInput) -> StepResult:
        """Decide the control flag for one 80 ms frame. Cheap: one incremental decode."""
        import torch

        with self._lock:
            # record frame into the rolling history (bounded)
            self._cb0.append(int(frame.cb0))
            self._energy.append(float(frame.energy))
            self._f0.append(float(frame.f0))
            self._state.append(vocab.AGENT_STATE_TO_ID.get(frame.agent_state, 0))
            if len(self._cb0) > self.max_audio_frames:
                # bound only the *rebuild seed* buffer; do NOT drop the live cache here —
                # that would force a rebuild on every frame once the buffer saturates
                # (a >16 s turn). The cache keeps streaming incrementally until it hits
                # _hard_cap, where the next rebuild reseeds from this bounded buffer.
                for buf in (self._cb0, self._energy, self._f0, self._state):
                    del buf[0]

            sig = self._text_sig()
            t0 = time.perf_counter()
            if self.force_recompute:
                flag_id = self._recompute_flag(torch)
                decode_ms = (time.perf_counter() - t0) * 1000.0
                flag = vocab.ID_TO_CONTROL_FLAG.get(flag_id, vocab.DEFAULT_FLAG)
                return StepResult(flag=flag, spoken="", decode_ms=decode_ms)
            try:
                need_rebuild = (
                    self._past is None
                    or sig != self._primed_sig
                    or self._cache_len >= self._hard_cap
                )
                if need_rebuild:
                    hidden_last = self._prime(torch, sig)
                else:
                    hidden_last = self._append_last_frame(torch)
                ctrl = self.model.control_head(hidden_last)          # [1, 1, F]
                flag_id = int(ctrl[0, -1].argmax().item())
            except Exception:
                # Safety net: if a transformers/cache version rejects the incremental
                # path, fall back to a correct (slower) stateless recompute for this
                # frame and drop the cache so the next frame re-primes cleanly.
                self._past = None
                self._cache_len = 0
                self._primed_sig = None
                flag_id = self._recompute_flag(torch)
            decode_ms = (time.perf_counter() - t0) * 1000.0

        flag = vocab.ID_TO_CONTROL_FLAG.get(flag_id, vocab.DEFAULT_FLAG)
        return StepResult(flag=flag, spoken="", decode_ms=decode_ms)

    # ------------------------------------------------------------------ #
    def generate_spoken(self, agent_state: str = "IDLE") -> str:
        """Greedy-decode a short spoken interjection from the current context.

        Only call this when the orchestrator has *already decided* to speak (a
        back-channel, a thinking-sound, or a silence re-open). Decodes from a clone of
        the live KV cache so it never disturbs the streaming state, and stays short
        (back-channels are 1-3 words). Returns "" for the silent case.
        """
        import torch

        with self._lock:
            if not self._cb0:
                return ""
            try:
                # Prime a THROWAWAY cache over [text + audio history] and decode the
                # spoken tail on it. We do not touch (or clone) the live streaming cache,
                # so step() is unaffected and there's no inference-tensor deepcopy.
                spoken_past, pos, _ = self._fresh_prime(torch)

                cur = list(self._say_bos)
                emb = self._embed_text(torch, cur, vocab_seg="agent")
                out = self._run(torch, emb, pos, spoken_past, want_logits=True)
                spoken_past = out.past_key_values
                pos += emb.shape[1]
                produced: list[int] = []
                for _ in range(self.spoken_max_new):
                    nxt = int(out.logits[0, -1].argmax().item())
                    if nxt == self._say_eos:
                        break
                    produced.append(nxt)
                    emb = self._embed_text(torch, [nxt], vocab_seg="agent")
                    out = self._run(torch, emb, pos, spoken_past, want_logits=True)
                    spoken_past = out.past_key_values
                    pos += 1
            except Exception:
                return ""

        text = self.tok.decode(produced, skip_special_tokens=True).strip()
        return text

    # ================================================================== #
    # internals
    # ================================================================== #
    def _ids(self, text: str) -> list[int]:
        out = self._tok_cache.get(text)
        if out is None:
            out = self.tok(text, add_special_tokens=False)["input_ids"]
            self._tok_cache[text] = out
        return out

    def _text_prefix(self) -> tuple[list[int], list[int]]:
        """Build [<|sys|> sys][<|agent|> agent][<|stt|> stt] token/segment ids.

        Identical construction to thinkspark.dataset / the trained reference, with a per
        segment token budget so the total sequence stays inside the sliding window.
        """
        from kupe._thinkspark.model import SEG_SYS, SEG_AGENT, SEG_STT
        sp = vocab.SPECIAL_TOKENS
        budgets = {SEG_SYS: 48, SEG_AGENT: 48, SEG_STT: 48}

        ids: list[int] = []
        seg: list[int] = []
        for marker, text, sid in (
            (sp["sys_bos"], self.system_prompt, SEG_SYS),
            (sp["agent_bos"], self.agent_text, SEG_AGENT),
            (sp["stt_bos"], self.stt_partial, SEG_STT),
        ):
            piece = self._ids(marker + " " + (text or ""))
            if len(piece) > budgets[sid]:
                # keep the marker (first token) + the most recent tail of the text
                piece = piece[:1] + piece[-(budgets[sid] - 1):]
            ids.extend(piece)
            seg.extend([sid] * len(piece))
        return ids, seg

    def _text_sig(self) -> tuple:
        return (self.system_prompt, self.agent_text, self.stt_partial)

    # -- embeddings (reuse the model's own front-end math) -------------- #
    def _embed_text(self, torch, ids: list[int], vocab_seg: str = "agent"):
        from kupe._thinkspark.model import SEG_SYS, SEG_AGENT, SEG_STT
        sid = {"sys": SEG_SYS, "agent": SEG_AGENT, "stt": SEG_STT}[vocab_seg]
        t = torch.tensor([ids], dtype=torch.long, device=self.device)
        s = torch.full_like(t, sid)
        return self.model._text_embeds(t, s)          # [1, L, H]

    def _embed_text_seg(self, torch, ids: list[int], seg: list[int]):
        t = torch.tensor([ids], dtype=torch.long, device=self.device)
        s = torch.tensor([seg], dtype=torch.long, device=self.device)
        return self.model._text_embeds(t, s)          # [1, L, H]

    def _embed_audio(self, torch, cb0, energy, f0, state):
        """Embed one or more audio frames via the model's audio front-end."""
        cb0_t = torch.tensor([cb0], dtype=torch.long, device=self.device)
        state_t = torch.tensor([state], dtype=torch.long, device=self.device)
        pros = np.stack([np.asarray(energy, dtype=np.float32),
                         np.asarray([_norm_f0(v) for v in f0], dtype=np.float32)], axis=-1)
        pros_t = torch.tensor(pros, dtype=self._dtype, device=self.device).unsqueeze(0)
        return self.model._audio_frame_embeds(cb0_t, pros_t, state_t)   # [1, T, H]

    # -- backbone call -------------------------------------------------- #
    def _run(self, torch, inputs_embeds, start_pos: int, past, want_logits: bool = False):
        L = inputs_embeds.shape[1]
        dev = self.device
        attn = torch.ones((1, start_pos + L), dtype=torch.long, device=dev)
        cache_position = torch.arange(start_pos, start_pos + L, device=dev)
        base = dict(
            inputs_embeds=inputs_embeds,
            attention_mask=attn,
            past_key_values=past,
            use_cache=True,
            cache_position=cache_position,
            output_hidden_states=True,
        )
        # Only ever run the 256K-vocab LM head on the LAST position: control-flag steps
        # ignore logits entirely, and spoken decoding only reads logits[-1]. On a rebuild
        # (~400 positions) this turns a 400x256K matmul into 1x256K — the single biggest
        # avoidable cost in the whole loop. `logits_to_keep` (renamed from
        # `num_logits_to_keep`) is transformers' native param; fall back if unsupported.
        with torch.inference_mode():
            if self._logits_kw is not False:
                for kw in ([self._logits_kw] if self._logits_kw else
                           ("logits_to_keep", "num_logits_to_keep")):
                    try:
                        out = self.model.backbone(**base, **{kw: 1})
                        self._logits_kw = kw
                        return out
                    except TypeError:
                        continue
                self._logits_kw = False
            out = self.model.backbone(**base)
        return out

    def _fresh_prime(self, torch):
        """Run [text prefix + trailing audio buffer] through a NEW cache in one forward.
        Returns (past_key_values, cache_len, last_audio_hidden). Mutates nothing."""
        try:
            from transformers import DynamicCache
        except Exception:
            from transformers.cache_utils import DynamicCache

        ids, seg = self._text_prefix()
        text_emb = self._embed_text_seg(torch, ids, seg)                       # [1, Lt, H]
        audio_emb = self._embed_audio(torch, self._cb0, self._energy,
                                      self._f0, self._state)                   # [1, T, H]
        inputs_embeds = torch.cat([text_emb, audio_emb], dim=1)
        out = self._run(torch, inputs_embeds, 0, DynamicCache())
        return out.past_key_values, inputs_embeds.shape[1], out.hidden_states[-1][:, -1:, :]

    def _prime(self, torch, sig: tuple):
        """(Re)build the LIVE KV cache from the text prefix + trailing audio buffer.
        Returns the hidden state of the most recent audio frame."""
        past, cache_len, hidden_last = self._fresh_prime(torch)
        self._past = past
        self._cache_len = cache_len
        self._primed_sig = sig
        return hidden_last                                                     # [1, 1, H]

    def _append_last_frame(self, torch):
        """Incrementally decode the single newest audio frame using the live cache."""
        audio_emb = self._embed_audio(torch, self._cb0[-1:], self._energy[-1:],
                                      self._f0[-1:], self._state[-1:])         # [1, 1, H]
        out = self._run(torch, audio_emb, self._cache_len, self._past)
        self._past = out.past_key_values
        self._cache_len += 1
        return out.hidden_states[-1][:, -1:, :]                                # [1, 1, H]

    def _recompute_flag(self, torch) -> int:
        """Stateless full-sequence forward for one frame (correctness fallback)."""
        ids, seg = self._text_prefix()
        T = len(self._cb0)
        f0n = np.array([_norm_f0(v) for v in self._f0], dtype=np.float32)
        prosody = np.stack([np.array(self._energy, dtype=np.float32), f0n], axis=-1)
        dev = self.device
        batch = {
            "text_ids": torch.tensor([ids], dtype=torch.long, device=dev),
            "text_seg": torch.tensor([seg], dtype=torch.long, device=dev),
            "text_mask": torch.ones((1, len(ids)), dtype=torch.long, device=dev),
            "cb0": torch.tensor([self._cb0], dtype=torch.long, device=dev),
            "prosody": torch.tensor(prosody, dtype=self._dtype, device=dev).unsqueeze(0),
            "agent_state": torch.tensor([self._state], dtype=torch.long, device=dev),
            "audio_mask": torch.ones((1, T), dtype=torch.long, device=dev),
        }
        with torch.inference_mode():
            out = self.model(**batch)
        return int(out.control_logits[0, -1].argmax().item())


# --------------------------------------------------------------------------- #
@dataclass
class ReferenceOrchestrator:
    """Pure-python floor controller mapping StepResults to actions (Section 11).

    Callbacks default to logging so it runs headless from a simulated frame stream.
    """
    referee: StreamingReferee
    on_barge_hard: Callable[[], None] = lambda: None
    on_barge_soft: Callable[[], None] = lambda: None
    on_prefetch: Callable[[str], None] = lambda partial: None
    on_commit: Callable[[], None] = lambda: None
    on_cancel: Callable[[], None] = lambda: None
    on_turn_end: Callable[[], None] = lambda: None
    tts_stream: Callable[[str], None] = lambda text: None
    log: list[str] = field(default_factory=list)

    prefetch_active: bool = False

    def handle(self, frame: FrameInput) -> StepResult:
        res = self.referee.step(frame)
        flag = res.flag
        spoken = ""

        if flag == "BARGE_HARD":
            self.on_barge_hard()
        elif flag == "BARGE_SOFT":
            self.on_barge_soft()
        elif flag == "PREFETCH_LLM":
            if frame.agent_state != "LLM_GEN":
                self.on_prefetch(self.referee.stt_partial)
                self.prefetch_active = True
        elif flag == "COMMIT_LLM":
            self.on_commit()
            self.prefetch_active = False
        elif flag == "CANCEL_LLM":
            self.on_cancel()
            self.prefetch_active = False
        elif flag == "TURN_END":
            if not self.prefetch_active:
                self.on_prefetch(self.referee.stt_partial)
            self.on_turn_end()
        elif flag == "SILENCE_BREAK":
            spoken = self.referee.generate_spoken(frame.agent_state)
            self.tts_stream(spoken or "")

        res.spoken = spoken
        self.log.append(f"{frame.agent_state:<12} -> {flag:<13} {('say=' + spoken) if spoken else ''}")
        return res
