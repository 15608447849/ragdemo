import os
import logging
from typing import List, Dict

from transformers import AutoModelForCausalLM, AutoTokenizer
from sentence_transformers import SentenceTransformer
import torch

device = 'cuda' if torch.cuda.is_available() else 'cpu'
logging.info(f'使用设备: {device}')

PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir
            )
)

emb_model_path = os.path.join(PROJECT_BASE, 'models/bge-small-zh-v1.5')
llm_model_path = os.path.join(PROJECT_BASE, 'models/Qwen3-4B-Instruct-2507')

emb_model = SentenceTransformer(emb_model_path).to(device)


tokenizer = AutoTokenizer.from_pretrained(llm_model_path)
llm_model = AutoModelForCausalLM.from_pretrained(
    llm_model_path,
    # torch_dtype="auto",
    dtype="auto",
    device_map=device
)


def embed(chunks: List[str]):
    return emb_model.encode(chunks, normalize_embeddings=True)

def llm(messages: List[Dict[str, str]]):
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    model_inputs = tokenizer([text], return_tensors="pt").to(device)

    generated_ids = llm_model.generate(
        **model_inputs,
        max_new_tokens=16384
    )

    output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
    content = tokenizer.decode(output_ids, skip_special_tokens=True)
    return content


if __name__ == '__main__':
    text = """
        加快北斗与人工智能和大数据等新兴技术融合，创新系统架构、优化运维模式、升级特色功能，努力打造精准可信、随遇接入、智能化、网络化、柔性化的下一代北斗系统。
建功新时代，奋进新征程。让我们继续发扬新时代北斗精神，筑梦星空，勇攀高峰，共同书写北斗规模应用新篇章！倡议人：北斗规模应用国际峰会专家委员会2024年10月24日
# 在北斗规模应用国际峰会专家委员会成立暨第一次全体会议上的主持讲话
·株洲市委书记曹慧泉（2024年10 月23 日下午16：30-17：30）
![](images/d54e93a88ed70d772f7be808dde4305571975ff6c76a25c7a7792ca2fb581b5b.jpg)
尊敬的迎春常务副省长，尊敬的杨长风院士、刘经南院士、李建成院士、王巍院士，各位专家、同志们：大家下午好！
今天，我们在这里隆重举行北斗规模应用国际峰会专家委员会成立暨第一次全体会议，
主要目的是贯彻落实习近平总书记致首届北斗峰会的贺信精神和党中央、国务院系列指示，集聚行业顶尖资源，成立峰会专家委员会，研究部署相关工作，为进一步提高峰会影响力和品牌度提供坚强支撑，推动湖南乃至全国北斗事业谱写崭新篇章。
        """
    messages = [
        {"role": "user", "content": f'#文本片段'
                                    f'\n{text}'
                                    f'\n\n请根据以上内容,模拟提出最多3个问题'
                                    f'\n请以标准JSON数组格式输出,例如：[\"问题1\", \"问题2\", \"问题3\"]'}
    ]
    s = llm(messages)
    logging.info(type(s))
    logging.info(s)

    import ast

    # 直接使用 ast.literal_eval 解析
    ss = ast.literal_eval(s)
    logging.info(type(ss))
    logging.info(ss)