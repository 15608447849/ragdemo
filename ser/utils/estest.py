# 创建文档分片索引，支持全文和向量混合检索
import logging
logging.basicConfig(level=logging.DEBUG)

import os
from datetime import datetime

from sentence_transformers import SentenceTransformer

from ser.utils.comm import generate_vector_id

PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir
            )
)
from ser.utils.elasticsearch_cli import es_client

document_chunk_mapping = {
    "settings": {

        "number_of_shards": 2,
        "number_of_replicas": 0,
        "refresh_interval": "1000ms",

        "similarity": {
            "scripted_sim": {
                "type": "scripted",
                "script": {
                    "source": "double idf = Math.log(1+(field.docCount-term.docFreq+0.5)/(term.docFreq + 0.5))/Math.log(1+((field.docCount-0.5)/1.5)); return query.boost * idf * Math.min(doc.freq, 1);"
                }
            }
        }
    },

    "mappings": {
        "properties": {
            "doc_oid": {"type": "keyword","index": True},  # 文档ID
            "chunk_oid": {"type": "keyword" },  # 分片ID
            "chunk_index": {"type": "integer","index": True},  # 分片序号
            "vector_id": {"type": "keyword", "index": True},  # 向量ID (hash)
            "content": {"type": "text",  "analyzer": "whitespace" , "similarity": "scripted_sim"},  # 分片文本内容 使用标准分析器
            "emb_512": {
                "type": "dense_vector",
                "dims": 512,  # bge-small-zh-v1.5 维度
                "index": True,
                "similarity": "cosine"
            },
            "questions": {
                "type": "text",
                "analyzer": "standard",  # 如果安装了中文分词器 "analyzer": "ik_max_word" , "search_analyzer": "ik_smart"

            },
            "metadata": {"type": "object"},  # 元数据
            "created_at": {"type": "date",
                           "store": True,
                           "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||yyyy-MM-dd_HH:mm:ss"
                           }
        }
    }
}


def mian_test_save():
    model_path = os.path.join(PROJECT_BASE, 'models/bge-small-zh-v1.5')
    import torch
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logging.info(f'使用设备: {device}')
    model = SentenceTransformer(model_path)
    model = model.to(device)

    chunks = [
        """
        为深入贯彻习近平主席致首届北斗规模应用国际峰会贺信精神，推动北斗规模应用纵深发展，值此工程立项三十周年之际，我们联合倡议：立足性能稳定可靠，推动系统与各行业深度耦合。秉持“建好、管好、用好”的理念，以智能化的运管，确保系统连续稳定运行和高质量发展，筑牢安全可信的时空底座。持续拓展服务能力，加强北斗跨界融合深度，不断迭代创新产品应用形态，将“好用的北斗”用好，使其深度融入国民经济发展全局。
优化产业生态环境，引导规模应用良性发展。强化产业发展顶层设计，发挥好有为政府与有效市场作用，完善政策法规体系，深化北斗专项标准和国家标准建设，加强知识产权保护，加快打造高水平产业人才队伍，成体系营造要素完备、创新活跃、良性健康的产业生态。着眼成果开放共享，服务全球贡献中国智慧。积极响应“一带一路”倡议，满足国际用户多样化应用需求，深化卫星导航领域合作，推动芯片、模块、终端等北斗产品加速融入国际产业体系，建立卫星导航国际应用服务体系，拓展北斗海外应用服务，为推动构建人类命运共同体作出更大贡献。
瞄准未来发展趋势，着力打造下一代北斗系统。强化科技创新引领作用，优化创新组织体系，推动综合时空体系国家级实验室建立；
        """,
        """
        加快北斗与人工智能和大数据等新兴技术融合，创新系统架构、优化运维模式、升级特色功能，努力打造精准可信、随遇接入、智能化、网络化、柔性化的下一代北斗系统。
建功新时代，奋进新征程。让我们继续发扬新时代北斗精神，筑梦星空，勇攀高峰，共同书写北斗规模应用新篇章！倡议人：北斗规模应用国际峰会专家委员会2024年10月24日
# 在北斗规模应用国际峰会专家委员会成立暨第一次全体会议上的主持讲话
·株洲市委书记曹慧泉（2024年10 月23 日下午16：30-17：30）
![](images/d54e93a88ed70d772f7be808dde4305571975ff6c76a25c7a7792ca2fb581b5b.jpg)
尊敬的迎春常务副省长，尊敬的杨长风院士、刘经南院士、李建成院士、王巍院士，各位专家、同志们：大家下午好！
今天，我们在这里隆重举行北斗规模应用国际峰会专家委员会成立暨第一次全体会议，
主要目的是贯彻落实习近平总书记致首届北斗峰会的贺信精神和党中央、国务院系列指示，集聚行业顶尖资源，成立峰会专家委员会，研究部署相关工作，为进一步提高峰会影响力和品牌度提供坚强支撑，推动湖南乃至全国北斗事业谱写崭新篇章。
        """
    ]
    questions = [
        "这份文档的主要内容是什么？",
        "文档中提到了哪些关键信息？",
        "这份文档是关于什么主题的？"
    ]
    embeddings = model.encode(chunks, normalize_embeddings=True)
    dimension = embeddings.shape[1]  # 向量维度 512
    logging.info(f"已生成 {len(embeddings)} 个文本向量，每个向量维度为 {dimension}")

    # es创建索引
    index_name = 'test_doc_chunk_0001'
    es_client.create_index(index_name, document_chunk_mapping)

    # 存储索引
    actions = []
    doc_id = '0001'
    for i, chunk in enumerate(chunks):
        # 生成向量ID
        vector_id = generate_vector_id(doc_id, str(i), chunk)
        # 生成向量
        embedding = embeddings[i].tolist()
        es_doc = {
            "_index": index_name,
            "_id": vector_id,
            "_source": {
                "doc_oid": doc_id,
                "chunk_oid": f'10000{str(i)}',
                "chunk_index": i,
                "vector_id": vector_id,
                "content": chunk,
                "emb_512": embedding,
                "questions": questions if questions else [],
                # "metadata": {},
                "created_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        logging.info(f"----生成 {vector_id}")
        actions.append(es_doc)


    # 批量索引
    result = es_client.bulk_index(actions)
    logging.info(f"存储结果: {result}")

def main_test_query():
     '''
     混合搜索：结合全文检索和向量相似度
     '''
     model_path = os.path.join(PROJECT_BASE, 'models/bge-small-zh-v1.5')
     import torch
     device = 'cuda' if torch.cuda.is_available() else 'cpu'
     logging.info(f'使用设备: {device}')
     model = SentenceTransformer(model_path)
     model = model.to(device)
     query_text = '国际峰会专家委员会成员有谁?'
     query_vector =  model.encode([query_text], normalize_embeddings=True)[0].tolist()

     index_name = 'test_doc_chunk_0001'
     top_k = 10

     # 构建混合查询
     query = {
         "size": top_k,

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
         }
     }

     # query = {
     #     "query": {
     #         "script_score": {
     #             "query": {"match_all": {}},
     #             "script": {
     #                 "source": "cosineSimilarity(params.query_vector, 'emb_512') + 1.0",
     #                 "params": {
     #                     "query_vector": query_vector
     #                 }
     #             }
     #         }
     #     },
     #     "size": 10
     # }

     result = es_client.search(index=index_name, query=query)
     logging.info(f'结果 {result}')

     for i, hit in enumerate(result['hits']['hits']):
         logging.info(f"结果 {i + 1}:")
         logging.info(f"  ID: {hit['_id']}")
         logging.info(f"  分数: {hit['_score']}")
         logging.info(f"  内容预览: {hit['_source']['content'][:100]}...")




if __name__ == '__main__':
    # mian_test_save()
    main_test_query()