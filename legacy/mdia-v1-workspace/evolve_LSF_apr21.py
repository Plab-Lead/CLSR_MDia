
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

#TEST_OFFSET = 0
TEST_OFFSET = 1

#think_mode = True
think_mode = False

#think_mode_for_lsf = True
think_mode_for_lsf = False

#do_initLSF = True
#do_initLSF = False

initLSF_id = 'v1'
#initLSF_id = 'v2'
#initLSF_id = 'v3'

NUM_SAMPLE, NUM_EVOLVE = 9, 20
#NUM_SAMPLE, NUM_EVOLVE = 18, 10


#cur_llm = "Qwen/Qwen3.5-9B" 
#cur_llm = "Qwen/Qwen3.5-27B" 
cur_llm = "Qwen/Qwen3.5-35B-A3B" 
#cur_llm = "Qwen/Qwen3.5-122B-A10B"
#cur_llm = "Pro/zai-org/GLM-5"
#cur_llm = "Pro/moonshotai/Kimi-K2.5"
#cur_llm = "Pro/deepseek-ai/DeepSeek-V3.2"

dataCards_list = ['mmlu-pro','gpqa','gsm8k','math500','aime','sci-qa','hotpot-qa']
_dataCard = dataCards_list[4]

print(f"###### LLM={cur_llm} ### data={_dataCard} ######")
print(f"###### NUM_SAMPLE={NUM_SAMPLE}, NUM_EVOLVE={NUM_EVOLVE} ######")

client = OpenAI(api_key=API_key, base_url="https://api.siliconflow.cn/v1")


llmCards_list = ['Qwen3.5-9B', 'Qwen3.5-27B', 'Qwen3.5-35B-A3B', 'Qwen3.5-122B-A10B', 'GLM-5', 'Kimi-K2.5', 'DeepSeek-V3.2']
tar_preds_paths = []
for _llmCard in llmCards_list:
    _paths = os.listdir(f"rawLLM-preds-record/{_llmCard}/{_dataCard}")
    tar_preds_paths += [_path for _path in _paths if f"_nFS#{num_FS}" in _path and 
                        f"_OffS#{TEST_OFFSET}" in _path and
                        f"_TM#{think_mode}" in _path and 
                        f"LSFID{initLSF_id}" in _path]


def cold_start_lsf(cur_exemplars):
    return f"""
You are designing a compact machine-oriented Language Symbolism Framework (LSF) for token-efficient and correct problem solving.
Goal:
Infer a general reusable LSF from the high-quality solved examples below.

Important:
- The examples may use different local symbolic styles.
- Do NOT copy any one example's notation directly.
- Instead, extract their shared strategic patterns, compression opportunities, and reasoning abstractions.
- The LSF must be more general, more consistent, and more reusable than any single example.
- The LSF is intended for future unseen queries.
- Human readability is NOT required.
- Internal consistency, non-ambiguity, and low token cost are required.

Optimization priority:
1. correctness on future unseen problems
2. low total generation tokens
3. low LSF complexity
4. notation stability across iterations

Design constraints:
- one symbol/operator = one stable meaning
- no synonym switching
- no contradictory notation
- no overloaded operators unless explicitly typed
- prefer reusable compositional primitives over many ad hoc symbols
- avoid domain-specific hacks unless they generalize
- the LSF should help reduce both visible answer length and latent reasoning burden
- do not include verbose explanations

You are given a set of high-quality exemplars. Each exemplar contains:
- query
- high_quality_answer
- token_count
- optional notes about why it is strong

Exemplars:
<EXEMPLAR_BATCH>
{cur_exemplars}
</EXEMPLAR_BATCH>

Your task:
Design a new LSF specification inspired by the exemplars' underlying problem-solving strategies.
Additional requirements:
- Keep the symbol inventory as small as possible.
- Prefer a small stable core over a large expressive vocabulary.
- Make the LSF general across task types if possible.
- Do not mention the exemplars in the output.
- Do not provide chain-of-thought.
- Output JSON only.
"""


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

def analyse_failures(cur_lsf, failed_samples):

    return f"""
You are analyzing failure cases for a compact machine-oriented Language Symbolism Framework (LSF).

Goal:
Extract reusable lessons from the failure cases without rewriting the LSF yet.

Important:
- This stage is analysis only.
- Do NOT propose a new LSF.
- Do NOT rewrite the current LSF.
- Do NOT optimize for any one isolated case.
- Focus on recurring weaknesses, not surface wording artifacts.
- Distinguish between:
  1. LSF representation failures
  2. reasoning-control failures
  3. answer-emission failures
  4. fallback-policy failures
  5. evaluation/formatting failures
- Prefer general patterns over case-by-case commentary.
- Human readability is allowed here, but be concise and structured.
- Do not provide chain-of-thought.

Current LSF:
<CURRENT_LSF>
{cur_lsf}
</CURRENT_LSF>

Failure bundle:
Each case contains:
- case_id
- query
- model_answer
- gold_answer
- reference_high_quality_answer
- error_type
- token_delta_vs_reference
- optional metadata

<FAILURE_BUNDLE>
{failed_samples}
</FAILURE_BUNDLE>

Your task:
Analyze the failures and summarize what the current LSF is doing wrong, what kinds of tasks are most affected, and what lessons should guide the next LSF revision.

Additional constraints:
- If multiple cases share one underlying issue, merge them into one cluster.
- If a failure appears due to over-compression, state that explicitly.
- If a failure appears due to ambiguity or notation drift, state that explicitly.
- If a failure seems unrelated to the LSF itself, say so.
- Keep the output compact.
"""


def update_lsf(cur_lsf, _analysis):

    return f"""
You are updating an existing compact machine-oriented Language Symbolism Framework (LSF).

Goal:
Produce the smallest useful LSF revision that addresses the diagnosed failure patterns while preserving prior strengths.

Important:
- This stage is update generation, not failure analysis.
- Use the diagnosis object as the authoritative summary of what went wrong.
- Do NOT re-analyze the raw failures from scratch.
- Do NOT rewrite the LSF unless the diagnosis explicitly indicates that a major edit is necessary.
- Prefer the smallest patch that fixes multiple failure clusters at once.
- Preserve backward compatibility whenever possible.
- Avoid adding new symbols unless existing symbols are insufficient.
- Avoid case-specific hacks.
- Keep the LSF compact, stable, and reusable.
- Do not provide chain-of-thought.

Current LSF:
<CURRENT_LSF>
{cur_lsf}
</CURRENT_LSF>

Diagnosis object:
<FAILURE_ANALYSIS>
{_analysis}
</FAILURE_ANALYSIS>

Your task:
Generate an updated LSF that follows the diagnosis object's priorities and patch scope.

Additional constraints:
- If the diagnosis says that emission policy or fallback policy is the main issue, prefer modifying those before touching the symbol core.
- If new symbols are added, keep the number as small as possible.
- If a rule can be clarified instead of adding a new primitive, prefer clarification.
- The updated LSF must remain internally consistent and non-ambiguous.
"""




samples_set = {}
for _path in tar_preds_paths:
    cur_llmCard = _path.split('LM#')[1].split('_Eval#')[0]
    with open(f"rawLLM-preds-record/{cur_llmCard}/{_dataCard}/{_path}", 'r') as file: cur_records = json.load(file)
    for _item in cur_records:
        raw_id = _item['raw_id']
        if raw_id not in samples_set: samples_set[raw_id] = {}
        assert _path not in samples_set[raw_id]
        f_score = _item['isCorr'] + 1/_item['completion_tokens']
        samples_set[raw_id][_path] = {**_item, 'f_score': round(f_score, 6)}


gold_set = []
for raw_id in samples_set:
    pred_items = samples_set[raw_id]
    cur_maxFScore, cur_path = 0, None
    for _path in pred_items:
        _item = pred_items[_path]
        if _item['f_score'] > cur_maxFScore: cur_maxFScore = _item['f_score']; cur_path = _path
    if cur_maxFScore > 1: gold_set.append(pred_items[cur_path])

gold_dict = {_item['raw_id']: _item for _item in gold_set}


print('###### Size gold_set:', len(gold_set), len(gold_dict))



def eval_cur_lsf(_lsf, _llm, gold_set, num_sample=10):

    eval_stat = []
    for _iter in range(num_sample):
        test_item = random.choice(gold_set)
        response = client.chat.completions.create(
                model = _llm,
                messages = [{'role': 'user', 'content': solve_with_lsf(_lsf, test_item['query'])}],
                temperature = 0.6,
                max_tokens = 4096,
                extra_body = {"enable_thinking": False}
            )
        
        raw_pred = response.choices[0].message.content
        pred_stat = response.usage
        #print('--- newLSF:', raw_pred)
        #print(pred_stat)
        #print('--- goldRef:', test_item['raw_output'])
        #print()

        #raw_eval_item = eval_llm.eval_output(test_item, raw_pred, client, "Qwen/Qwen3.5-9B")
        try: raw_eval_item = eval_llm.eval_output(test_item, raw_pred, client, "Qwen/Qwen3.5-9B")
        except:
            print("###### Error occurs when evaluate via Qwen3.5-9B, use Qwen3.5-4B instead...")
            raw_eval_item = eval_llm.eval_output(test_item, raw_pred, client, "Qwen/Qwen3.5-4B")
        
        try: 
            clean_eval_item = eval(raw_eval_item)
            eval_stat.append({**test_item, **clean_eval_item,
                            'raw_output': raw_pred, 
                            'completion_tokens': pred_stat.completion_tokens, 
                            'prompt_tokens': pred_stat.prompt_tokens, 
                            'reasoning_tokens': 0})
        except: 
            print(f"------ Error occurs when parsing stats ------")
            print(raw_eval_item, pred_stat)

    return eval_stat

    
def get_failed_samples(gold_dict, _stat):

    res_list = []
    for _item in _stat:
        raw_id = _item['raw_id']
        gold_item = gold_dict[raw_id]
        print(f"### new ## isCorr={_item['isCorr']} ## Tkn={_item['completion_tokens']} ### gold ## isCorr={gold_item['isCorr']} ## Tkn={gold_item['completion_tokens']} ###")
        new_fscore = _item['isCorr'] + 1/_item['completion_tokens']
        gold_fscore = gold_item['isCorr'] + 1/gold_item['completion_tokens']
        if gold_fscore > new_fscore:
            res_list.append({
                'query': _item['query'],
                'lsf_output': _item['raw_output'],
                'gold_output': gold_item['raw_output'],
                'is_Correct': _item['isCorr'],
                'label': _item['label']
            })

    return res_list


def get_updated_lsf(_lsf, _fails):
    if _fails == []: return _lsf
    if think_mode_for_lsf: extra_body = {"enable_thinking": True, "thinking_budget": 24576}
    else: extra_body = {"enable_thinking": False}
    response = client.chat.completions.create(
        model = cur_llm,
        messages = [{'role': 'user', 'content': analyse_failures(_lsf, _fails)}],
        temperature = 0.6,
        max_tokens = 4096,
        extra_body = extra_body
    )
    cur_analysis = response.choices[0].message.content

    response2 = client.chat.completions.create(
        model = cur_llm,
        messages = [
            {'role': 'user', 'content': analyse_failures(_lsf, _fails)},
            {'role': 'assistant', 'content': cur_analysis},
            {'role': 'user', 'content': update_lsf(_lsf, cur_analysis)},
            ],
        temperature = 0.6,
        max_tokens = 4096,
        extra_body = extra_body
    )
    new_lsf = response2.choices[0].message.content
    return new_lsf


raw_gold_samples = random.sample(gold_set, NUM_SAMPLE)
clean_gold_samples = [{'query': _sample['query'], 'output': _sample['raw_output'], 'label': _sample['label']} for _sample in raw_gold_samples]

if think_mode_for_lsf: extra_body = {"enable_thinking": True, "thinking_budget": 24576}
else: extra_body = {"enable_thinking": False}

response = client.chat.completions.create(
    model = cur_llm,
    messages = [{'role': 'user', 'content': cold_start_lsf(clean_gold_samples)}],
    temperature = 0.6,
    max_tokens = 4096,
    extra_body = extra_body
)
init_LSF = response.choices[0].message.content

llm_name = cur_llm.split('/')[-1]

evolve_record_dir = f"evolve_records/{_dataCard}"
os.makedirs(evolve_record_dir, exist_ok=True)

evolve_records = []
init_eval = eval_cur_lsf(init_LSF, cur_llm, gold_set, num_sample=NUM_SAMPLE)
init_fails = get_failed_samples(gold_dict, init_eval)
updated_lsf = get_updated_lsf(init_LSF, init_fails)

evolve_records.append({
    'eval': init_eval,
    'fails': init_fails,
    'cur_lsf': updated_lsf
})

Inf_id = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(5))
saved_path = f"{evolve_record_dir}/LM#{llm_name}_TM4L#{think_mode_for_lsf}_NSp#{NUM_SAMPLE}_NEv#{NUM_EVOLVE}_InfID#{Inf_id}.json"

#with open(saved_path, "w") as file: json.dump(evolve_records, file, indent=4)

for _iter in range(NUM_EVOLVE):
    print(f"###### Evolution={_iter+1} ######")
    _eval = eval_cur_lsf(updated_lsf, cur_llm, gold_set, num_sample=NUM_SAMPLE)
    _fails = get_failed_samples(gold_dict, _eval)
    updated_lsf = get_updated_lsf(updated_lsf, _fails)

    evolve_records.append({'eval': _eval, 'fails': _fails, 'cur_lsf': updated_lsf})
    if _iter > 14: 
        with open(saved_path, "w") as file: json.dump(evolve_records, file, indent=4)

    
    
with open(saved_path, "w") as file: json.dump(evolve_records, file, indent=4)
#print(updated_lsf)
print()
print(f"###### Saved to {saved_path} ###")



