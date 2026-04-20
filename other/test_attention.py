import time
import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

transformers.logging.set_verbosity_error()
transformers.logging.disable_progress_bar()

model_id = "meta-llama/Llama-3.2-1B"
PROMPT = "Hello, world!"
MAX_NEW_TOKENS = 50
WARMUP_RUNS = 2
TIMED_RUNS = 5

tokenizer = AutoTokenizer.from_pretrained(model_id)
tokenizer.pad_token_id = tokenizer.eos_token_id

# Determine which implementations to benchmark
IMPLEMENTATIONS = ["eager", "sdpa"]
try:
    import flash_attn  # noqa: F401
    IMPLEMENTATIONS.append("flash_attention_2")
except ImportError:
    print("flash-attn not available, skipping flash_attention_2")

def benchmark(impl: str) -> dict:
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        dtype=torch.bfloat16,
        device_map="auto",
        attn_implementation=impl,
        trust_remote_code=True,
    )
    inputs = tokenizer(PROMPT, return_tensors="pt").to(model.device)

    # Warmup
    with torch.no_grad():
        for _ in range(WARMUP_RUNS):
            model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)

    torch.cuda.synchronize()
    latencies = []
    with torch.no_grad():
        for _ in range(TIMED_RUNS):
            start = time.perf_counter()
            out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
            torch.cuda.synchronize()
            latencies.append(time.perf_counter() - start)

    tokens_generated = MAX_NEW_TOKENS * TIMED_RUNS
    total_time = sum(latencies)
    return {
        "impl": impl,
        "mean_latency_ms": 1000 * total_time / TIMED_RUNS,
        "tokens_per_sec": tokens_generated / total_time,
        "output": tokenizer.decode(out[0], skip_special_tokens=True),
    }


print(f"{'Implementation':<20} {'Mean latency (ms)':>20} {'Tokens/sec':>12}")
print("-" * 55)
for impl in IMPLEMENTATIONS:
    r = benchmark(impl)
    print(f"{r['impl']:<20} {r['mean_latency_ms']:>20.1f} {r['tokens_per_sec']:>12.1f}")
print()
print("Sample output (last impl):", r["output"])
