import logging
import time

from fastapi import APIRouter
from pydantic import BaseModel

from ser.utils.comm import get_current_time, create_response
from ser.utils.elasticsearch_cli import es_client
from ser.utils.model_cli import embed, llm
from ser.utils.redis_cli import redis_client

router = APIRouter()

# 历史记录条数
history_chat_limit = 20

index_name = 'rag_demo_es_document_index'


prompt = '''
#角色
- 你是基于文档片段进行整理总结要点进行回复的小助理
- 你是可以自我思考的智慧体
- 你是理性又逻辑性的语言专家
#指令
- 优先根据文档片段回复问题
- 考虑上下文或历史聊天记录
- 没有文档片段时以引导的方式提出问题
- 逐步思考
#限制
- 禁止胡言乱语
- 不知道或不清楚直接明确回复'无法回答您的问题'

<文档片段>
{document_chunk}
</文档片段>


<当前问题>
{question}
</当前问题>
'''


class ChatSendRequest(BaseModel):
    user_identifier: str
    message: str


def query_elasticsearch(query_text,top_k=20, min_score=6):
    '''混合搜索：结合全文检索和向量相似度'''

    query_vector = embed([query_text])[0].tolist()
    es_query = {
        "query": {
            "bool": {

                "should": [
                    {
                        "multi_match": {
                            "query": query_text,
                            "fields": ["content","questions"],
                            "boost": 0.4
                        }
                    },
                    {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": f"Math.max(0, cosineSimilarity(params.query_vector, 'emb_512')) * {0.6}",
                                "params": {
                                    "query_vector": query_vector
                                }
                            }
                        }
                    }
                ]
            }
        },
        "size": top_k,
        "min_score": min_score
    }
    content_str = ''
    es_result = es_client.search(index=index_name, query=es_query)
    for i, hit in enumerate(es_result['hits']['hits']):
        logging.info(f"结果 {i + 1}  ID: {hit['_id']} 分数: {hit['_score']}")
        logging.info(f"  内容预览: {hit['_source']['content'][:100]}...")
        if hit['_score'] >= min_score:
            content_str += hit['_source']['content'] + '\n'
        else:
            logging.info("pass..")
    # 重排序-暂不实现
    return content_str




@router.post("/chat/send")
async def send_chat_message(request: ChatSendRequest):
    """发送聊天消息"""
    question = request.message
    user_identifier = request.user_identifier
    st = time.time()
    # 根据问题搜索es
    content_str = query_elasticsearch( question )
    # 获取历史
    chat_his_list = redis_client.get_list(f"chat_history:{user_identifier}")
    logging.info(f"历史记录条数: {len(chat_his_list)}")
    # 构建提示词
    sys_prom= prompt.format(document_chunk=content_str, question=question)

    # 构建数据体
    messages = [{"role": "system", "content": sys_prom, "timestamp": get_current_time()}]

    chat_his_msg = chat_his_list[-history_chat_limit:] if len(chat_his_list) > history_chat_limit else chat_his_list
    messages.extend(chat_his_msg)
    et = time.time()

    # 开始使用llm
    chat_his_msg.append({"role": "user", "content": question, 'timestamp': get_current_time()})
    answer = llm(chat_his_list)
    chat_his_msg.append({"role": "assistant", "content": answer, 'timestamp': get_current_time()})

    # 存入redis覆盖历史记录
    redis_client.set_list(f"chat_history:{user_identifier}", chat_his_msg)
    response_time =  round((et - st) * 1000)

    # 构建响应
    return create_response(data={
        'ai_response': answer,
        'response_time': response_time,
        'related_docs' : content_str
    })

@router.get("/chat/history")
async def get_chat_history(user_identifier: str):
    """获取聊天历史
    结构如下:
    [{"role": "user", "content":"问题","timestamp":'时间戳'},
    {"role": "assistant", "content":"回复","timestamp":'时间戳'}
    ...
    ]
    """
    chat_his_list = redis_client.get_list(f"chat_history:{user_identifier}")

    return create_response(data=chat_his_list)
