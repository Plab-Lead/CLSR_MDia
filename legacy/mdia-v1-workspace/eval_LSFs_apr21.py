
import os
import json
import time
import random
import string
from datetime import datetime
from openai import OpenAI
import llm_utils.load_data as load_ds
import llm_utils.eval_llmOutputs as eval_llm


num_FS = 0
#num_FS = 2 #t7-d
#num_FS = 4 #t9-d

TEST_OFFSET = 0
#TEST_OFFSET = 1

#think_mode = True
think_mode = False

num_evalLLM = 2
print_freq = 40
max_numTest = 200


#cur_llm = "Qwen/Qwen3.5-9B" 
#cur_llm = "Qwen/Qwen3.5-27B" 
cur_llm = "Qwen/Qwen3.5-35B-A3B" 
#cur_llm = "Qwen/Qwen3.5-122B-A10B"
#cur_llm = "Pro/moonshotai/Kimi-K2.5"
#cur_llm = "Pro/zai-org/GLM-5"
#cur_llm = "Pro/deepseek-ai/DeepSeek-V3.2"

dataCards_list = ['mmlu-pro','gpqa','gsm8k','math500','aime','sci-qa','hotpot-qa']
_dataCard = dataCards_list[1]

lsf_evID = 10


#### AIME
#lsf_fileName = "LM#Qwen3.5-9B_TM4L#False_NSp#9_NEv#20_InfID#Rfh5p.json"
#lsf_fileName = "LM#Qwen3.5-9B_TM4L#False_NSp#18_NEv#10_InfID#22wg0.json"
#lsf_fileName = "LM#Qwen3.5-35B-A3B_TM4L#False_NSp#9_NEv#20_InfID#FfelL.json"
#lsf_fileName = "LM#Qwen3.5-35B-A3B_TM4L#False_NSp#18_NEv#10_InfID#NUes8.json"
#lsf_fileName = "LM#Qwen3.5-122B-A10B_TM4L#False_NSp#9_NEv#20_InfID#gwnSt.json"
#lsf_fileName = "LM#Qwen3.5-122B-A10B_TM4L#False_NSp#18_NEv#10_InfID#OT82P.json"
#lsf_fileName = "LM#Kimi-K2.5_TM4L#False_NSp#9_NEv#20_InfID#o9vhk.json"
lsf_fileName = "LM#Kimi-K2.5_TM4L#False_NSp#18_NEv#10_InfID#edf1h.json"
#lsf_fileName = "LM#GLM-5_TM4L#False_NSp#9_NEv#20_InfID#s1paj.json"
#lsf_fileName = "LM#GLM-5_TM4L#False_NSp#18_NEv#10_InfID#GeVI1.json"
#lsf_fileName = "LM#DeepSeek-V3.2_TM4L#False_NSp#9_NEv#20_InfID#wKWFh.json"
#lsf_fileName = "LM#DeepSeek-V3.2_TM4L#False_NSp#18_NEv#10_InfID#AOwcp.json"



lsf_records_path = f"evolve_records/{_dataCard}/{lsf_fileName}"

with open(lsf_records_path, 'r') as file: lsf_records = json.load(file)
cur_LSF = lsf_records[lsf_evID]['cur_lsf']

lsf_llm = lsf_records_path.split('LM#')[1].split('_TM4L#')[0]
inf_lsfID = f"{lsf_records_path.split('/')[-1].replace('.json','')}"

print(f"### LSF-path: {lsf_records_path} ###")
print(f"### LSF-evolution-ID: {lsf_evID} ###")


def solve_with_lsf(cur_lsf, cur_query):

    return f"""
You are given a fixed Language Symbolism Framework (LSF). Your task is to solve the query using this LSF as faithfully and efficiently as possible.
Primary objective: Minimize total generated tokens while preserving correctness.

Important:
- Treat the LSF as fixed for this batch.
- Do NOT redesign, explain, extend, or rename the LSF.
- Do NOT invent new symbols unless the fallback policy explicitly allows it.
- Do NOT discuss the LSF.
- Do NOT restate the query.
- Do NOT provide long explanations.
- Use the least latent reasoning necessary for correctness.
- Prefer direct answers whenever the LSF policy says direct answering is safe.

Current LSF:
<LSF_SPEC>
{cur_lsf}
</LSF_SPEC>

Test query:
<QUERY_BATCH>
{cur_query}
</QUERY_BATCH>
"""


print(f"###### LLM={cur_llm} ### Benchmark={_dataCard} ######")

def get_fsPrompt(train_DS, fewShot_ids):
    fs_messages = []
    for fs_id in fewShot_ids:
        fs_item = train_DS[fs_id]
        fs_messages += [{'role': 'user', 'content': fs_item['query']}, {'role': 'assistant', 'content': ''}]
        if fs_item['cot_content'] != '': fs_messages[-1]['content'] += fs_item['cot_content']
        if fs_item['label'] != '': fs_messages[-1]['content'] += f"###### Final answer: {fs_item['label']}."
    return fs_messages



clean_trainDS, clean_testDS = load_ds.load_cleanDS(_dataCard=_dataCard)

if num_FS > 0:
    if _dataCard == 'mmlu-pro': fewShot_ids = list(range(-70,0,int(70/num_FS)+1))
    elif _dataCard in ['gpqa','gsm8k','math500','sci-qa','hotpot-qa','aime']: fewShot_ids = list(range(0, len(clean_trainDS), int(len(clean_trainDS)/num_FS)+1))
else: fewShot_ids = []

exemplars_messages = get_fsPrompt(clean_trainDS, fewShot_ids)
print(f"--- Num Exemplars: {(len(exemplars_messages))//2}")

client = OpenAI(api_key=API_KEY, base_url="https://api.siliconflow.cn/v1")

def eval_LLM(TEST_OFFSET, _testDS, max_numTest, _exemplars, client=None, llm_key=None):

    eval_stat = []
    if think_mode: 
        max_tokens = 8192
        extra_body = {"enable_thinking": True, "thinking_budget": 24576}
    else: 
        max_tokens = 4096
        extra_body = {"enable_thinking": False}

    for test_id in range(TEST_OFFSET, len(_testDS), max(1,len(_testDS)//max_numTest)):
        test_item = _testDS[test_id]
        cur_messages = _exemplars[:] + [{'role': 'user', 'content': solve_with_lsf(cur_LSF, test_item['query'])}]

        response = client.chat.completions.create(
            model = llm_key,
            messages = cur_messages,
            temperature = 0.6,
            max_tokens = max_tokens,
            extra_body = extra_body
        )

        response_content = response.choices[0].message.content
        response_stat = response.usage

        try: raw_eval_item = eval_llm.eval_output(test_item, response_content[:], client, "Qwen/Qwen3.5-9B")
        except:
            print("###### Error occurs when evaluate via Qwen3.5-9B, use Qwen3.5-4B instead...")
            raw_eval_item = eval_llm.eval_output(test_item, response_content[:], client, "Qwen/Qwen3.5-4B")
        # try: raw_eval_item = eval_llm.eval_output(test_item, response_content[:], client, "Qwen/Qwen3.5-4B")
        # except:
        #     print("###### Error occurs when evaluate via Qwen3.5-4B, use Qwen3.5-9B instead...")
        #     raw_eval_item = eval_llm.eval_output(test_item, response_content[:], client, "Qwen/Qwen3.5-9B")

        try: 
            clean_eval_item = eval(raw_eval_item)
            assert 'isCorr' in clean_eval_item
            eval_stat.append({'raw_output': response_content, 
                          'completion_tokens': response_stat.completion_tokens, 
                          'prompt_tokens': response_stat.prompt_tokens, 
                          'reasoning_tokens': 0,
                          **test_item, **clean_eval_item})
            if think_mode: eval_stat[-1]['reasoning_tokens'] = response_stat.completion_tokens_details.reasoning_tokens
        except: 
            print(f"------ Error occurs when parsing stats at Test-ID = {test_id} ------")
            print(raw_eval_item, response_content[-500:])
        
        if len(eval_stat) % print_freq == 0:
            print(f"------ TestID: {test_id} --- {datetime.now().strftime('%H:%M:%S')} ------")
            print(clean_eval_item, response_stat)
        
    return eval_stat





llm_name = cur_llm.split('/')[-1]

preds_record_dir = f"lsfLLM-preds-record/{llm_name}/{_dataCard}"
os.makedirs(preds_record_dir, exist_ok=True)

for trial_id in range(num_evalLLM):
    Inf_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(3))
    custom_id = f"{Inf_id}"

    _now = datetime.now()
    time_ind = f"{_now.month}-{_now.day}-{_now.hour}:{_now.minute}:{_now.second}"
    print(f"------ Trial_ID={trial_id} --- CurTime: {time_ind} ------")

    cur_stat = eval_LLM(TEST_OFFSET, clean_testDS, max_numTest, exemplars_messages, client=client, llm_key=cur_llm)

    total_completions, total_corr, total_count = 0, 0, len(cur_stat)
    for _item in cur_stat: total_completions += _item['completion_tokens']; total_corr += _item['isCorr']

    cur_filePath = f"{preds_record_dir}/InfLM#{llm_name}_LsfLM#{lsf_llm}_Eval#{_dataCard}_EvID#{lsf_evID}_Acc#{100*total_corr/total_count:.02f}_NTk#{total_completions/total_count:.01f}_nFS#{num_FS}_TM#{think_mode}_OffS#{TEST_OFFSET}_NTest#{len(cur_stat)}_LSFID#{inf_lsfID}_ED#{time_ind}_CI#{custom_id}.json"
    with open(cur_filePath, "w") as file: json.dump(cur_stat, file, indent=4)
    print(f"------ Saved to ### {cur_filePath} ------\n")









