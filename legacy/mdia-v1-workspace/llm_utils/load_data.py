

from datasets import load_dataset, get_dataset_config_names


mmluPro_path = "/home/[dir]/TIGER-Lab/MMLU-Pro"
gpqa_path = "/home/[dir]/Idavidrein/gpqa"

gsm8k_path = "/home/[dir]/HF_datasets/gsm8k/main"
math500_path = "/home/[dir]/HF_datasets/ankner/math-500"
aime_path = "/home/[dir]/HF_datasets/AIME"

sciQA_path = "/home/[dir]/HF_datasets/ScienceQA"
hotpotQA_path = "/home/[dir]/HF_datasets/hotpotqa"


def load_rawSplits(dataCard=None):

    if dataCard == 'mmlu-pro':
        train_config = '+'.join([f'test[{k+3}%:{k+5}%]' for k in range(0, 100, 5)]) + '+validation'
        test_config = '+'.join([f'test[{k}%:{k+1}%]' for k in range(0, 100, 10)])
        train_DS = load_dataset(mmluPro_path, 'default', split=train_config)
        test_DS = load_dataset(mmluPro_path, 'default', split=test_config)
    elif dataCard == 'gpqa':
        train_DS = load_dataset(gpqa_path, 'gpqa_extended', split='train')
        test_DS = load_dataset(gpqa_path, 'gpqa_main', split='train')
    elif dataCard == 'gsm8k':
        train_DS = load_dataset(gsm8k_path, split='train')
        test_DS = load_dataset(gsm8k_path, split='test')
    elif dataCard == 'math500':
        train_DS = load_dataset(math500_path, split='train')
        test_DS = load_dataset(math500_path, split='test')
    elif dataCard == 'aime':
        train_DS = load_dataset(aime_path, split='train[:830]')
        test_DS = load_dataset(aime_path, split='train[830:]')
    elif dataCard == 'sci-qa':
        train_config = '+'.join([f'train[{k}%:{k+1}%]' for k in range(0, 100, 5)]) + '+validation'
        test_config = '+'.join([f'test[{k}%:{k+1}%]' for k in range(0, 100, 5)])
        train_DS = load_dataset(sciQA_path, split=train_config)
        test_DS = load_dataset(sciQA_path, split=test_config)
    elif dataCard == 'hotpot-qa':
        train_config = '+'.join([f'train[{k}%:{k+1}%]' for k in range(0, 100, 15)])
        test_config = '+'.join([f'validation[{k}%:{k+1}%]' for k in range(0, 100, 15)])
        train_DS = load_dataset(hotpotQA_path, split=train_config)
        test_DS = load_dataset(hotpotQA_path, split=test_config)

    return train_DS, test_DS



def process_cleanDS(_DS, _dataCard=None):
    if _dataCard == 'mmlu-pro':
        res_DS = [{
                'raw_id': _item['question_id'],
                'query': f"{_item['question']} The options are: {_item['options']}.",
                'label': _item['options'][_item['answer_index']],
                'cot_content': _item['cot_content'],
                'category': [_item['category']]
            } for _id, _item in enumerate(_DS)]
    elif _dataCard == 'gpqa':
        res_DS = [{
                'raw_id': _id,
                'query': f"{_item['Question']} The options are: {[_item['Correct Answer'],_item['Incorrect Answer 1'],_item['Incorrect Answer 2'],_item['Incorrect Answer 3']]}.",
                'label': _item['Correct Answer'],
                'cot_content': _item['Explanation'],
                'category': [_item['High-level domain'],_item['Subdomain']]
            } for _id, _item in enumerate(_DS)]
    elif _dataCard == 'gsm8k':
        res_DS = [{
                'raw_id': _id,
                'query': _item['question'],
                'label': _item['answer'].split('####')[1].strip(),
                'cot_content': _item['answer'],
                'category': []
            } for _id, _item in enumerate(_DS)]
    elif _dataCard == 'math500':
        res_DS = [{
                'raw_id': _id,
                'query': _item['problem'],
                'label': '',
                'cot_content': _item['solution'],
                'category': [_item['type'], _item['level']]
            } for _id, _item in enumerate(_DS)]
    elif _dataCard == 'aime':
        res_DS = [{
                'raw_id': _item['ID'],
                'query': _item['Question'],
                'label': _item['Answer'],
                'cot_content': '',
                'category': [_item['Year'], _item['Part'], _item['Problem Number']]
            } for _id, _item in enumerate(_DS)]
    elif _dataCard == 'sci-qa':
        res_DS = [{
                'raw_id': _id,
                'query': f"{_item['question']} The choices are: {_item['choices']}",
                'label': _item['choices'][_item['answer']],
                'cot_content': _item['solution'],
                'category': [_item['category'], _item['topic'], _item['subject'], _item['grade']]
            } for _id, _item in enumerate(_DS)]
    elif _dataCard == 'hotpot-qa':
        res_DS = [{
                'raw_id': _item['id'],
                'query': f"{_item['question']} The supporting context is: {_item['context']}",
                'label': _item['answer'],
                'cot_content': '',
                'category': [_item['type'], _item['level']]
            } for _id, _item in enumerate(_DS)]

    return res_DS



def load_cleanDS(_dataCard=None):

    train_DS, test_DS = load_rawSplits(dataCard=_dataCard)
    clean_trainDS = process_cleanDS(train_DS, _dataCard=_dataCard)
    clean_testDS = process_cleanDS(test_DS, _dataCard=_dataCard)
    print(f"------ Loaded dataset ### {_dataCard} ### with trainSize = {len(clean_trainDS)} and testSize = {len(clean_testDS)} ------")
    return clean_trainDS, clean_testDS


