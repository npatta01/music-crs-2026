# Model registry — b1 fine-tuned checkpoints (Issue #153)

**Source of truth:** Modal volume **`scout-models`** (account `npatta01`). These `_l2048` paths are
**SCRATCH / MUTABLE** — they get overwritten when the same variant is re-run (they were overwritten
twice this session: buggy → off-by-one-corrected labels). **Do NOT serve directly from these.**
Promotion = copy to an immutable, checksummed location (HF private repo, bf16 — see below).

All checkpoints below are the **off-by-one-corrected-label** models, fp32, computed 2026-06-25 via
`scripts/rerank/modal_ckpt_info.py`.

| model | Modal path (`scout-models` volume) | `model.safetensors` (fp32) | sha256 (fp32) | corrected r@100 |
|---|---|---|---|---|
| **v_struct_pt · 0.6B** (winner) | `/biencoder_variant_v_struct_pt_l2048` | 2,383,139,480 B (2.38 GB) | `ef412dd1d39444bc0f81279b507a5df8f68f1b2a73fa4a8674f11bb0c9216184` | 51.7 |
| **v_struct_pt · 4B** (winner) | `/biencoder_variant_v_struct_pt_l2048_qwen3-embedding-4b` | 16,087,140,808 B (16.09 GB) | `c78eb09b2ab012f4fb8f3b32b95fea18eed50de81a5e9e088099a30bc61308ef` | 54.0 |
| baseline · 0.6B (ref) | `/biencoder_variant_baseline_l2048` | 2,383,139,480 B | `0e3d58658ea47b5b875c2b98d25dbb39f1431fd96b3c7f512d6003cb53f4ded9` | 46.6 |
| baseline · 4B (ref) | `/biencoder_variant_baseline_l2048_qwen3-embedding-4b` | 16,087,140,808 B | `e4ffbfdf8fc543b0e9b2e06857421c2845aafd3ebbe9bf55cda09b46e395a945` | 49.5 |

Base: `Qwen/Qwen3-Embedding-{0.6B,4B}` (Apache-2.0). Full fine-tune (whole encoder). Input =
`[prev] <prev turn> [now] <current turn> [prev_track] <just-played artist—title>` (goal-free).
Recipe: variant-b MOVES-only (corrected labels), kf-dropout 0.3, n_hardneg 4, bs64, 1 epoch, MNRL,
last-token pool, max_len 2048.

## Promoted (immutable) — HF private repos, bf16
Promotion via `scripts/rerank/modal_promote_hf.py` (casts fp32→bf16, ~halves size, pushes to a
private HF repo, tags `v1`). The bf16 file gets its **own** sha256 (recorded on upload); the fp32
sha256 above is the source-of-truth provenance.

| model | HF repo (private) | bf16 `model.safetensors` | bf16 sha256 |
|---|---|---|---|
| v_struct_pt · 0.6B | `Npatta01/music-recsys-2026-retriever-0.6b` | 1.19 GB (1,191,586,416 B) | `94e1e9d393b038398100529eb2548f78814ec123391059e72100b429b53db506` |
| v_struct_pt · 4B | `Npatta01/music-recsys-2026-retriever-4b` | 8.04 GB (8,043,592,168 B) | `79aa4d26be96a117d749c6f067d31306b21a1e34fb1525a5aa9246537fe4c9a9` |

Promoted 2026-06-25 (bf16, private). Load: `AutoModel.from_pretrained("Npatta01/music-recsys-2026-retriever-0.6b", token=...)`.
**Rotate the HF write token** used for this push (it was shared in chat).
