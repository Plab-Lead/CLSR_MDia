
import torch
from transformers import Qwen3ForCausalLM
from transformers import AutoModelForCausalLM, AutoTokenizer



# load the tokenizer and the model
qwen3_4B_path = "/Qwen/Qwen3-4B"
qwen3_8B_path = "/Qwen/Qwen3-8B"
qwen3_14B_path = "/Qwen/Qwen3-14B"
qwen3_32B_path = "/Qwen/Qwen3-32B-AWQ"
MISTRAL_7B_path = "/mistralai/Mistral-7B-Instruct-v0.3"
LLaMA3_8B_path = "/meta-llama/Llama-3.1-8B-Instruct"
dsR1_qwen3_8B_path = "/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
dsR1_llama_8B_path = "/deepseek-ai/DeepSeek-R1-Distill-Llama-8B"

def get_llm(choose_llm):

    if choose_llm == 'qwen3-4b':
        cur_model = AutoModelForCausalLM.from_pretrained(qwen3_4B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(qwen3_4B_path)
        layers_range = [0, 36]

    if choose_llm == 'qwen3-8b':
        cur_model = AutoModelForCausalLM.from_pretrained(qwen3_8B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(qwen3_8B_path)
        layers_range = [0, 36]

    if choose_llm == 'qwen3-14b':
        cur_model = AutoModelForCausalLM.from_pretrained(qwen3_14B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(qwen3_14B_path)
        layers_range = [0, 40]

    if choose_llm == 'qwen3-32b':
        cur_model = AutoModelForCausalLM.from_pretrained(qwen3_32B_path, torch_dtype=torch.float16, device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(qwen3_32B_path)
        layers_range = [0, 40]

    if choose_llm == 'mistral-7b':
        cur_model = AutoModelForCausalLM.from_pretrained(MISTRAL_7B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(MISTRAL_7B_path, torch_dtype="auto", device_map="auto")
        layers_range = [0, 32]

    if choose_llm == 'llama3-8b':
        cur_model = AutoModelForCausalLM.from_pretrained(LLaMA3_8B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(LLaMA3_8B_path, torch_dtype="auto", device_map="auto")
        layers_range = [0, 32]

    if choose_llm == 'dsR1-qwen3-8b':
        cur_model = AutoModelForCausalLM.from_pretrained(dsR1_qwen3_8B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(dsR1_qwen3_8B_path, torch_dtype="auto", device_map="auto")
        layers_range = [0, 32]

    if choose_llm == 'dsR1-llama-8b':
        cur_model = AutoModelForCausalLM.from_pretrained(dsR1_llama_8B_path, torch_dtype="auto", device_map="auto")
        cur_tokenizer = AutoTokenizer.from_pretrained(dsR1_llama_8B_path, torch_dtype="auto", device_map="auto")
        layers_range = [0, 32]

    return cur_model, cur_tokenizer, layers_range


