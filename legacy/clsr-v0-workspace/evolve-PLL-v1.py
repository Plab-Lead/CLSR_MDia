
from __future__ import annotations
import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '0,1,2,3,4,5,6,7'
os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2,3,4,5,6,7'

#os.environ['CUDA_LAUNCH_BLOCKING'] = '0,1,2,3,7'
#os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2,3,7'

import json
import time
import torch
import string
import random
from datetime import datetime
import llm_utils.inf_llm as inf_llm
import llm_utils.load_llm as load_llm
import llm_utils.load_data as load_ds
import llm_utils.eval_llmOutputs as eval_llm


#choose_llm = 'qwen3-4b'
choose_llm = 'qwen3-8b'
#choose_llm = 'qwen3-14b'
#choose_llm = 'qwen3-32b'
#choose_llm = 'mistral-7b'
#choose_llm = 'llama3-8b'
#choose_llm = 'dsR1-qwen3-8b'
#choose_llm = 'dsR1-llama-8b'

#think_mode = None
#think_mode = 'short-factual'
#think_mode = 'short-think'
#think_mode = 'medium-factual'
#think_mode = 'medium-think'
#think_mode = 'mLong-factual'
#think_mode = 'mLong-eval'
think_mode = 'mLong-think'
#think_mode = 'long-factual'
#think_mode = 'long-think'

Num_SEEDs = 10
cur_evolution = 0
#cur_evolution = 1
#cur_evolution = 2
#cur_evolution = 3
#cur_evolution = 4
#LenCoeff = 2.5 # for others
#LenCoeff = 2.0 
#LenCoeff = 0.5

meta_version = 'v2'

dataCards_list = ['mmlu-pro','gpqa','gsm8k','math500','aime','sci-qa','hotpot-qa']
#_dataCard = dataCards_list[1]
_dataCard = dataCards_list[3]

exemplars_clip = None

def init_fsPrompt(train_DS, _dataCard):

    if _dataCard == 'mmlu-pro': fewShot_ids = list(range(-70,0,2))
    elif _dataCard in ['gpqa','gsm8k','math500','sci-qa']: fewShot_ids = list(range(0, len(train_DS), len(train_DS)//40))
    elif _dataCard in ['hotpot-qa']: fewShot_ids = list(range(0, len(train_DS), len(train_DS)//20))
    elif _dataCard in ['aime']: fewShot_ids = list(range(0, len(train_DS), len(train_DS)//40))

    fs_messages = []
    for fs_id in fewShot_ids:
        fs_item = train_DS[fs_id]
        fs_messages += [{'role': 'user', 'content': fs_item['query']}, {'role': 'assistant', 'content': ''}]
        if fs_item['cot_content'] != '': fs_messages[-1]['content'] += fs_item['cot_content']
        if fs_item['label'] != '': fs_messages[-1]['content'] += f"###### Final answer: {fs_item['label']}."
    return fs_messages


def evolve_fsPrompt(_bestSamples):
    fs_messages = []
    for sample_id in _bestSamples:
        _item = _bestSamples[sample_id]
        if _item['isCorr'] == 1: fs_messages += [{'role': 'user', 'content': _item['query']}, {'role': 'assistant', 'content': _item['raw_output']}]
    return fs_messages

if cur_evolution > 0:
    samples_paths = os.listdir(f'evoluted_Samples/ev{cur_evolution-1}')
    selected_paths = [_path for _path in samples_paths if choose_llm in _path and _dataCard in _path]
    max_score, max_path = 0, ''
    for _path in selected_paths:
        cur_acc = float(_path.split('_Acc#')[1].split('_')[0])
        cur_len = float(_path.split('_Len#')[1].split('_')[0])
        cur_score = cur_acc/cur_len
        if cur_score > max_score: max_score, max_path = cur_score, _path
        print(_path, cur_acc, cur_len, round(cur_score, 6), round(max_score, 6))
    evolveSamples_path = max_path
    print(f"--- Picked EvolveSamples: evoluted_Samples/ev{cur_evolution-1}/{evolveSamples_path}")
    with open(f"evoluted_Samples/ev{cur_evolution-1}/{evolveSamples_path}", "r") as file: cur_bestSamples = json.load(file)
    exemplars_messages = evolve_fsPrompt(cur_bestSamples)
else:
    print('--- First Evolution uses TrainDS to generate PLL ---')
    clean_trainDS, clean_testDS = load_ds.load_cleanDS(_dataCard=_dataCard)
    exemplars_messages = init_fsPrompt(clean_trainDS, _dataCard)

print(f"--- No.Evoluted_samples: {len(exemplars_messages)/2}")


if exemplars_clip is not None: exemplars_messages = exemplars_messages[:exemplars_clip]

with open(f"meta_prompts/meta_LSFs_{meta_version}.json", "r") as file: PLL_prompts = json.load(file)
cur_model, cur_tokenizer, layers_range = load_llm.get_llm(choose_llm)


for PLL_level in list(range(10)) + [None]*2:

    if PLL_level is not None: PLLprompt_messages = [{'role': 'user', 'content': PLL_prompts['root-prompt']+PLL_prompts[f"level-{PLL_level}"]}]
    else: PLLprompt_messages = [{'role': 'user', 'content': PLL_prompts['root-prompt']}]

    cur_messages = exemplars_messages + PLLprompt_messages

    for _seed in range(Num_SEEDs):
        print(f"------ SEED: {_seed} -- Level-{PLL_level} -- {datetime.now().strftime('%H:%M:%S')} ------")
        cur_messages = exemplars_messages + PLLprompt_messages

        tokenized_inputs = inf_llm.get_llm_inputs(cur_model, cur_tokenizer, cur_messages)
        print(f"--- Len Input: {len(tokenized_inputs['input_ids'][0])}")
        with torch.no_grad(): 
            ss_inf = time.time(); think_outputs, raw_outputs = inf_llm.get_llm_outputs(cur_model, cur_tokenizer, tokenized_inputs, think_mode=think_mode); ee_inf = time.time()

        tokenized_outputs = cur_tokenizer([raw_outputs], return_tensors="pt")
        len_LLP = len(tokenized_outputs['input_ids'][0])
        print(f"--- Len Output: {len_LLP} ---")

        if len_LLP < 4096 and len_LLP > 300:
            Lang_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(6))
            cur_filePath = f"evoluted_PLLs_all/ev{cur_evolution}/LM#{choose_llm}_Eval#{_dataCard}_LangID#Level{PLL_level}-{meta_version}#{Lang_id}_FromEv#{cur_evolution-1}.json"
            print(cur_filePath)
            with open(cur_filePath, "w") as file: file.write(raw_outputs)
        print()




