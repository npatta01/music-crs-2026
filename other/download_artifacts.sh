
uvx hf auth login 
uv run python - <<'EOF'
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModel, AutoModelForCausalLM

# Datasets
load_dataset('talkpl-ai/TalkPlayData-Challenge-Dataset')
load_dataset('talkpl-ai/TalkPlayData-Challenge-Track-Metadata')
load_dataset('talkpl-ai/TalkPlayData-Challenge-User-Metadata')
load_dataset('talkpl-ai/TalkPlayData-Challenge-Blind-A')

# Models
AutoTokenizer.from_pretrained('bert-base-uncased')
AutoModel.from_pretrained('bert-base-uncased')
AutoTokenizer.from_pretrained('meta-llama/Llama-3.2-1B-Instruct')
AutoModelForCausalLM.from_pretrained('meta-llama/Llama-3.2-1B-Instruct')
EOF