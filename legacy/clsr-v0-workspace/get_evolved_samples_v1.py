
import os
import json
import random
import string
import numpy as np
from datetime import datetime

num_evolve = 0

choose_llm = 'qwen3-8b'

eval_benchmark = 'mmlu-pro'

TEST_OFFSET = 0

if TEST_OFFSET == 0: Preds_dir = f"evoluted_Samples/ev{num_evolve}-raw/"
else: Preds_dir = f"evoluted_Samples/ev{num_evolve}-raw-ts{TEST_OFFSET}/"

SAVED_DIR = f"evoluted_Samples/ev{num_evolve}"

Preds_paths = os.listdir(Preds_dir)
select_paths = [_path for _path in Preds_paths if choose_llm in _path and eval_benchmark in _path]

def get_stats(_paths):
    _stat = {}
    for _path in _paths:
        path_configs = _path.split('_')
        _llm = path_configs[0][3:]
        _dataCard = path_configs[1][5:]
        _level = path_configs[2].split('#')[1]
        if _llm not in _stat: _stat[_llm] = {}
        if _dataCard not in _stat[_llm]: _stat[_llm][_dataCard] = {}

        if _level not in _stat[_llm][_dataCard]: _stat[_llm][_dataCard][_level] = 1
        else: _stat[_llm][_dataCard][_level] += 1

    return _stat


def get_predsDict(_dir, _paths):

    _Preds_dict = {}
    for _path in _paths:
        with open(_dir + _path, "r") as file: _Preds_dict[_path] = json.load(file)
    return _Preds_dict


def get_evalStats(_dict, _paths):

    eval_dict = {}
    for _path in _paths:
        _langID = _path.split('_')[2][7:]
        num_items = len(_dict[_path])
        count_corr = sum([_item['isCorr'] for _item in _dict[_path]])
        count_tokens = sum([_item['num_tokens'] for _item in _dict[_path]])
        overall_score = (count_corr**2)/(count_tokens**0.5)
        print(f"{_langID} - score: {overall_score:.02f} - Acc: {count_corr/num_items:.04f} - Len: {count_tokens/num_items:.02f} - Totals: {num_items}")
        eval_dict[_langID] = {'score': overall_score, 'acc': count_corr/num_items, 'len': count_tokens/num_items, 'totals': num_items}
    
    return eval_dict



def collect_allSamples(_dict, select_mode=None, max_keys=None):

    count_collect = 0
    rawId_to_samples_clean = {}
    for _key in _dict:
        if max_keys is not None and count_collect >= max_keys: break
        if select_mode is not None:
            if select_mode == 'RawCoT' and 'RawCoT' not in _key: continue
            elif select_mode == 'PLL' and 'RawCoT' in _key: continue
            
        count_collect += 1
        _samples = _dict[_key]
        _langID = _key.split('_')[2][7:]
        for _id, _item in enumerate(_samples):
            _rawID = _item['raw_id']
            if _rawID not in rawId_to_samples_clean: rawId_to_samples_clean[_rawID] = []

            rawId_to_samples_clean[_rawID].append({'langID': _langID, 
                                                   'isCorr': _item['isCorr'],
                                                   'query': _item['query'],
                                                   'num_tokens': _item['num_tokens'], 
                                                   'raw_output': _item['raw_outputs'], 
                                                   'full_path': _key})

    return rawId_to_samples_clean


def collect_bestSamples(_corrSamples, corr_coeff=0.1, len_coeff=0.1, pick_Corr=False):

    res_dict = {}
    for _rawID in _corrSamples:
        _samples = _corrSamples[_rawID]
        max_score, best_sId = 0, ''
        for s_id, s_item in enumerate(_samples):
            if not pick_Corr: cur_score = ((s_item['isCorr']+0.1)**corr_coeff)/((s_item['num_tokens']+0.1)**len_coeff)
            else: 
                if s_item['isCorr'] == 0: cur_score = -1
                else: cur_score = 1/s_item['num_tokens']
            if cur_score > max_score: max_score = cur_score; best_sId = s_id
        if best_sId != '': res_dict[_rawID] = _samples[best_sId]

    return res_dict


if eval_benchmark in ['aime']: len_coeff_list = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
else: len_coeff_list = [1.2, 1.5, 1.8, 2.1, 2.4, 2.7]

cur_preds_ev0 = get_predsDict(Preds_dir, select_paths)
cur_evals = get_evalStats(cur_preds_ev0, select_paths)

corr_coeff = 0.5
for len_coeff in len_coeff_list:
    for _max_keys in [5, 10, 15, 20, None]:
        #print(f"--- Len_Coeff: {len_coeff} -- Max_Keys: {_max_keys} ---")
        _collected_samples = collect_allSamples(cur_preds_ev0, select_mode="PLL", max_keys=_max_keys)
        cur_bestSamples = collect_bestSamples(_collected_samples, corr_coeff=corr_coeff, len_coeff=len_coeff, pick_Corr=False)

        num_items = len(cur_bestSamples)
        count_corr = sum([cur_bestSamples[_rawID]['isCorr'] for _rawID in cur_bestSamples])
        count_tokens = sum([cur_bestSamples[_rawID]['num_tokens'] for _rawID in cur_bestSamples])
        #print(f"--- Len_Coeff: {len_coeff} -- Max_Keys: {_max_keys} ---", round(count_corr/num_items, 4), round(count_tokens/num_items, 2), num_items, corr_coeff, len_coeff)

        _now = datetime.now(); time_ind = f"{_now.month}-{_now.day}-{_now.hour}:{_now.minute}:{_now.second}"
        Inf_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(3))

        cur_filePath = f"{SAVED_DIR}/LM#{choose_llm}_Eval#{eval_benchmark}_CorrCoeff#{corr_coeff}_LenCoeff#{len_coeff}_Acc#{count_corr/num_items:.02f}_Len#{count_tokens/num_items:.01f}_ED#{time_ind}_Inf#{Inf_id}.json"
        with open(cur_filePath, "w") as file: json.dump(cur_bestSamples, file, indent=4)

        print(f"--- Len_Coeff: {len_coeff} -- Max_Keys: {_max_keys} -- Curr_Acc: {count_corr/num_items:.04f} -- Cur_Len: {count_tokens/num_items:.02f}-- InfID: {Inf_id} ---")





