
import time
import types

################## general model generation ##################

def get_llm_inputs(_model, _tokenizer, _messages, enable_thinking=False):
    text = _tokenizer.apply_chat_template(_messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    model_inputs = _tokenizer([text], return_tensors="pt").to(_model.device)
    return model_inputs


def get_llm_outputs(_model, _tokenizer, _inputs, think_mode=None):

    if think_mode is None: generated_ids = _model.generate(**_inputs, max_new_tokens=2048, temperature = 0.7, top_p=0.8, top_k=20, min_p=0)
    elif think_mode == 'short-factual': generated_ids = _model.generate(**_inputs, max_new_tokens=1024, temperature = 0.1, top_p=0.5, top_k=20, min_p=0)
    elif think_mode == 'short-eval': generated_ids = _model.generate(**_inputs, max_new_tokens=1024, temperature = 0.3, top_p=0.8, top_k=30, min_p=0)
    elif think_mode == 'short-think': generated_ids = _model.generate(**_inputs, max_new_tokens=1024, temperature = 0.9, top_p=0.9, top_k=50, min_p=0)
    elif think_mode == 'medium-factual': generated_ids = _model.generate(**_inputs, max_new_tokens=4096, temperature = 0.1, top_p=0.5, top_k=20, min_p=0)
    elif think_mode == 'medium-eval': generated_ids = _model.generate(**_inputs, max_new_tokens=4096, temperature = 0.3, top_p=0.8, top_k=30, min_p=0)
    elif think_mode == 'medium-think': generated_ids = _model.generate(**_inputs, max_new_tokens=4096, temperature = 0.9, top_p=0.9, top_k=50, min_p=0)
    elif think_mode == 'mLong-factual': generated_ids = _model.generate(**_inputs, max_new_tokens=8192, temperature = 0.1, top_p=0.5, top_k=20, min_p=0)
    elif think_mode == 'mLong-eval': generated_ids = _model.generate(**_inputs, max_new_tokens=8192, temperature = 0.3, top_p=0.8, top_k=30, min_p=0)
    elif think_mode == 'mLong-think': generated_ids = _model.generate(**_inputs, max_new_tokens=8192, temperature = 0.9, top_p=0.9, top_k=50, min_p=0)
    elif think_mode == 'long-factual': generated_ids = _model.generate(**_inputs, max_new_tokens=16384, temperature = 0.1, top_p=0.5, top_k=20, min_p=0)
    elif think_mode == 'long-eval': generated_ids = _model.generate(**_inputs, max_new_tokens=16384, temperature = 0.3, top_p=0.8, top_k=30, min_p=0)
    elif think_mode == 'long-think': generated_ids = _model.generate(**_inputs, max_new_tokens=16384, temperature = 0.9, top_p=0.9, top_k=50, min_p=0)

    output_ids = generated_ids[0][len(_inputs.input_ids[0]):].tolist() 
    try: index = len(output_ids) - output_ids[::-1].index(151668)
    except ValueError: index = 0
    thinking_content = _tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
    content = _tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")
    
    return thinking_content, content

