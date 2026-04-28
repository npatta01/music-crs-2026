from .llama import LLAMA_MODEL
from .dummy import DUMMY_LM

def load_lm_module(lm_type, device, attn_implementation, dtype, lm_kwargs=None):
    lm_kwargs = lm_kwargs or {}
    if lm_type == "dummy":
        return DUMMY_LM()
    elif lm_type == "litellm":
        from .litellm_chat import LITELLM_LM
        return LITELLM_LM(**lm_kwargs)
    elif lm_type == "meta-llama/Llama-3.2-1B-Instruct":
        return LLAMA_MODEL(model_name=lm_type, device=device, attn_implementation=attn_implementation, dtype=dtype)
    else:
        raise ValueError(f"Unsupported LM type: {lm_type}")
