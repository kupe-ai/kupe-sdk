"""Vendored Gemma-3-270M architecture spec.

The ThinkSpark checkpoint carries all 542 MB of trained weights but no HF-format model
config, and google/gemma-3-270m is a GATED repo — so fetching even its 1 KB config.json
made the whole model unloadable for anyone who had not accepted that license.

These are architecture hyperparameters (layer counts, dimensions), not weights. Copied
verbatim from the published config so the backbone can be constructed offline, with
zero network calls to any gated repo.
"""

from __future__ import annotations

GEMMA3_270M: dict = {
    "model_type": "gemma3_text",
    "architectures": ["Gemma3ForCausalLM"],
    "_sliding_window_pattern": 6,
    "attention_bias": False,
    "attention_dropout": 0.0,
    "attn_logit_softcapping": None,
    "bos_token_id": 2,
    "eos_token_id": 1,
    "pad_token_id": 0,
    "final_logit_softcapping": None,
    "head_dim": 256,
    "hidden_activation": "gelu_pytorch_tanh",
    "hidden_size": 640,
    "initializer_range": 0.02,
    "intermediate_size": 2048,
    "layer_types": [
        "sliding_attention", "sliding_attention", "sliding_attention",
        "sliding_attention", "sliding_attention", "full_attention",
        "sliding_attention", "sliding_attention", "sliding_attention",
        "sliding_attention", "sliding_attention", "full_attention",
        "sliding_attention", "sliding_attention", "sliding_attention",
        "sliding_attention", "sliding_attention", "full_attention",
    ],
    "max_position_embeddings": 32768,
    "num_attention_heads": 4,
    "num_hidden_layers": 18,
    "num_key_value_heads": 1,
    "query_pre_attn_scalar": 256,
    "rms_norm_eps": 1e-06,
    "rope_local_base_freq": 10000.0,
    "rope_scaling": None,
    "rope_theta": 1000000.0,
    "sliding_window": 512,
    "use_bidirectional_attention": False,
    "use_cache": True,
    "vocab_size": 262144,
}


def backbone_config(attn_implementation: str = "sdpa"):
    """Build the backbone config locally — no download, no gated repo.

    Tries the explicit config class first, then the auto mapping, so it keeps working
    across transformers versions that move these around.
    """
    params = {k: v for k, v in GEMMA3_270M.items() if k != "model_type"}
    cfg = None

    try:
        from transformers import Gemma3TextConfig

        cfg = Gemma3TextConfig(**params)
    except Exception:
        pass

    if cfg is None:
        try:
            from transformers.models.auto.configuration_auto import CONFIG_MAPPING

            cfg = CONFIG_MAPPING["gemma3_text"](**params)
        except Exception:
            pass

    if cfg is None:
        from transformers import AutoConfig

        cfg = AutoConfig.for_model("gemma3_text", **params)

    try:
        cfg._attn_implementation = attn_implementation
    except Exception:
        pass
    return cfg
