

from __future__ import annotations
import os
os.environ['CUDA_LAUNCH_BLOCKING'] = '0,1,2,3,4,5,6,7'
os.environ['CUDA_VISIBLE_DEVICES'] = '0,1,2,3,4,5,6,7'


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

import transformers
transformers.logging.set_verbosity_error()

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
think_mode = 'mLong-eval'
#think_mode = 'mLong-think'
#think_mode = 'long-factual'
#think_mode = 'long-think'

PLL_level = None

meta_version = 'v2'
#meta_version = 'v1'

TEST_OFFSET = 0

cur_evolution = 0

eval_rawCoT = False
#num_rawEval = 1

num_FS = 4

EvalsCount_thres = 0

dataCards_list = ['mmlu-pro','gpqa','gsm8k','math500','aime','sci-qa','hotpot-qa']
_dataCard = dataCards_list[3]

ENABLE_THINKING = False

PLLs_dir = f"evoluted_PLLs_all/ev{cur_evolution}/"
Preds_dir = f"evoluted_Samples/ev{cur_evolution}-raw/"
if TEST_OFFSET != 0: Preds_dir = f"evoluted_Samples/ev{cur_evolution}-raw-ts{TEST_OFFSET}/"

PLLs_paths = os.listdir(PLLs_dir)
Preds_paths = os.listdir(Preds_dir)

def get_fsPrompt(train_DS, fewShot_ids):
    fs_messages = []
    for fs_id in fewShot_ids:
        fs_item = train_DS[fs_id]
        fs_messages += [{'role': 'user', 'content': fs_item['query']}, {'role': 'assistant', 'content': ''}]
        if fs_item['cot_content'] != '': fs_messages[-1]['content'] += fs_item['cot_content']
        if fs_item['label'] != '': fs_messages[-1]['content'] += f"###### Final answer: {fs_item['label']}."
    return fs_messages

random.shuffle(PLLs_paths)

loaded_paths = []
if not eval_rawCoT:
    with open(f"meta_prompts/meta_LSFs_{meta_version}.json", "r") as file: PLL_prompts = json.load(file)
    for _path in PLLs_paths:
        _llm = _path.split('_')[0][3:]
        cur_dataCard = _path.split('_')[1].replace('Eval#','')
        _langID = _path.split('_')[2][7:].replace('.json','')
        if PLL_level is not None: cur_level = f"Level{PLL_level}-{meta_version}"
        else: 
            if random.random() < 0.3: cur_level = _langID.split('#')[0]
            else: cur_level = ''

        if choose_llm != _llm or cur_level != _langID.split('#')[0] or cur_dataCard != _dataCard: continue
        evals_count = 0
        for _ in Preds_paths:
            if f"LM#{choose_llm}_Eval#{_dataCard}_LangID#{_langID}_OffS#{TEST_OFFSET}" in _: evals_count += 1
        if evals_count <= EvalsCount_thres and len(loaded_paths) < 30: loaded_paths.append(_path); print(_path)
else: loaded_paths = ['rawCoT1', 'rawCoT2', 'rawCoT3', 'rawCoT4', 'rawCoT5'][:num_rawEval]

clean_trainDS, clean_testDS = load_ds.load_cleanDS(_dataCard=_dataCard)

if num_FS > 0:
    if _dataCard == 'mmlu-pro': fewShot_ids = list(range(-70,0,int(70/num_FS)+1))
    elif _dataCard in ['gpqa','gsm8k','math500','sci-qa','hotpot-qa','aime']: fewShot_ids = list(range(0, len(clean_trainDS), int(len(clean_trainDS)/num_FS)+1))
else: fewShot_ids = []

exemplars_messages = get_fsPrompt(clean_trainDS, fewShot_ids)
# PLLprompt_messages = [{'role': 'user', 'content': PLL_prompts['root-prompt']+PLL_prompts[f"level-{PLL_level}"]}]

print(f"--- Len Exemplars: {len(exemplars_messages)}")

if choose_llm == 'dsR1-qwen3-8b': eval_model, eval_tokenizer, eval_range = load_llm.get_llm('qwen3-4b')
cur_model, cur_tokenizer, layers_range = load_llm.get_llm(choose_llm)

print(f"------ LLM: {choose_llm} -- dataCard: {_dataCard} -- think_mode: {think_mode} -- {[PLL_level,meta_version,TEST_OFFSET,eval_rawCoT,num_FS,EvalsCount_thres]}")
if eval_rawCoT: _langID = f"RawCoT"
for path_id, _path in enumerate(loaded_paths):
    
    if not eval_rawCoT:
        _langID = _path.split('_')[2][7:].replace('.json','')
        _levelID = _langID.split('-')[0].replace('Level','').strip()
        if '-v' not in _langID: continue
        print(f"------ LangID: {_langID} -- CurID: {path_id} -- {datetime.now().strftime('%H:%M:%S')} -- Path: {_path} ------")
        if choose_llm == 'qwen3-8b':
            if cur_evolution >=1: cur_filePath = f"{PLLs_dir}/LM#{choose_llm}_Eval#{_dataCard}_LangID#{_langID}_FromEv#{cur_evolution-1}.json"
            else: cur_filePath = f"{PLLs_dir}/LM#{choose_llm}_Eval#{_dataCard}_LangID#{_langID}.json"
        else: 
            cur_filePath = f"{PLLs_dir}/LM#{choose_llm}_Eval#{_dataCard}_LangID#{_langID}_FromEv#{cur_evolution-1}.json"

        with open(cur_filePath, "r") as file: loaded_PLL = file.read()
        if _levelID == 'None': gen_PLL_prompt =  PLL_prompts['root-prompt']
        else: gen_PLL_prompt = PLL_prompts['root-prompt']+PLL_prompts[f"level-{_levelID}"]
        PLLprompt_messages = [{'role': 'user', 'content': gen_PLL_prompt}, {'role': 'assistant', 'content': loaded_PLL}]
        
    else: print(f"------ LangID: {_path} -- CurID: {path_id} -- {datetime.now().strftime('%H:%M:%S')} ------")

    Inf_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(3))
    _now = datetime.now()
    time_ind = f"{_now.month}-{_now.day}-{_now.hour}:{_now.minute}:{_now.second}"
    cur_filePath = f"{Preds_dir}LM#{choose_llm}_Eval#{_dataCard}_LangID#{_langID}_OffS#{TEST_OFFSET}_nFS#{num_FS}_TM#{think_mode}_ED#{time_ind}_Inf#{Inf_id}.json"
    print(f"------ tmpPath ### {cur_filePath}")
        
    llmPreds_stat = []
    tmp_corr = 0
    for test_id in range(TEST_OFFSET, len(clean_testDS), max(1,len(clean_testDS)//200)):
        test_item = clean_testDS[test_id]
        cur_messages = exemplars_messages[:]
        if not eval_rawCoT: 
            cur_messages += PLLprompt_messages
            cur_messages += [{'role': 'user', 'content': 'Please use your designed language symbolism framework to answer the following test problem with fewer tokens and ensure reasoning accuracy:'+test_item['query']}]
        else: cur_messages += [{'role': 'user', 'content': test_item['query']}]

        tokenized_inputs = inf_llm.get_llm_inputs(cur_model, cur_tokenizer, cur_messages, enable_thinking=ENABLE_THINKING)        
        with torch.no_grad(): 
            ss_inf = time.time(); think_outputs, raw_outputs = inf_llm.get_llm_outputs(cur_model, cur_tokenizer, tokenized_inputs, think_mode=think_mode); ee_inf = time.time()
            if choose_llm == 'dsR1-qwen3-8b': raw_evalStat = eval_llm.eval_output(test_item, raw_outputs, eval_model, eval_tokenizer)
            else: raw_evalStat = eval_llm.eval_output(test_item, raw_outputs, cur_model, cur_tokenizer)

        try: 
            clean_evalStat = eval(raw_evalStat)
            if 'isCorr' not in clean_evalStat: print(f"------ Error occurs when parsing stats at Test-ID = {test_id} ------"); continue
            if ENABLE_THINKING: raw_outputs = think_outputs + ' ### ' + raw_outputs
            extra_stat = {'num_tokens': len(cur_tokenizer([raw_outputs])['input_ids'][0]), 'inf_TC': round(ee_inf-ss_inf,4)}
            llmPreds_stat.append({**test_item, **clean_evalStat, **extra_stat, 'raw_outputs': raw_outputs})
            if clean_evalStat['isCorr'] == 1: tmp_corr += 1
        except: print(f"------ Error occurs when parsing stats at Test-ID = {test_id} ------")

        if len(llmPreds_stat) % 40 == 0: 
            print(test_id, clean_evalStat, extra_stat, test_item['label'], test_item['cot_content'][-20:], round(tmp_corr/len(llmPreds_stat),4), '---', datetime.now().strftime('%H:%M:%S'))

    total_count = len(llmPreds_stat)
    corr_count, numTokens_count, infTC_count = 0, 0, 0
    for _item in llmPreds_stat: corr_count+=_item['isCorr']; numTokens_count+=_item['num_tokens']; infTC_count+=_item['inf_TC']
    print(f"------ Acc: {corr_count/total_count:.04f} -- Average No.Tokens: {numTokens_count/total_count:.01f} -- Average TC: {infTC_count/total_count:.03f}")

    _now = datetime.now()
    time_ind = f"{_now.month}-{_now.day}-{_now.hour}:{_now.minute}:{_now.second}"
    cur_filePath = f"{Preds_dir}LM#{choose_llm}_Eval#{_dataCard}_LangID#{_langID}_OffS#{TEST_OFFSET}_nFS#{num_FS}_TM#{think_mode}_ED#{time_ind}_Inf#{Inf_id}.json"
    print(f"------ Saved to ### {cur_filePath}\n")
    with open(cur_filePath, "w") as file: json.dump(llmPreds_stat, file, indent=4)


