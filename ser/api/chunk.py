import datetime
import hashlib
import logging
import os
import ast

from fastapi import APIRouter
from ser.utils.comm import create_response_error_1003, create_response
from ser.utils.db import get_pool_conn

from ser.utils.comm import generate_vector_id
from ser.utils.elasticsearch_cli import es_client
from ser.utils.genid import IDGeneratorFactory

from ser.utils.md_chunk import  mdfile_img_replace, SmartMarkdownSplitter
from ser.utils.mineru_pdf_pause import do_parse

from ser.utils.minio_cli import minio_client

from ser.utils.model_cli import embed, llm


router = APIRouter()

index_name = 'rag_demo_es_document_index'

# 创建文档分片索引，支持全文和向量混合检索
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
            "doc_oid": {"type": "keyword", "index": True},  # 文档ID
            "chunk_oid": {"type": "keyword"},  # 分片ID
            "chunk_index": {"type": "integer", "index": True},  # 分片序号
            "vector_id": {"type": "keyword", "index": True},  # 向量ID (hash)
            "content": {"type": "text", "analyzer": "whitespace", "similarity": "scripted_sim"},  # 分片文本内容
            "emb_512": {
                "type": "dense_vector",
                "dims": 512,  # bge-small-zh-v1.5 维度
                "index": True,
                "similarity": "cosine"
            },
            "questions": {
                "type": "text",
                "analyzer": "standard",

            },
            "metadata": {"type": "object"},  # 元数据
            "created_at": {"type": "date",
                           "store": True,
                           "format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||yyyy-MM-dd_HH:mm:ss"
                           }
        }
    }
}

# 创建es索引
es_client.create_index(index_name, document_chunk_mapping)

def do_chunk_pdf(doc_name,file_path,):
    '''
    0 获取minoio的数据
    1 pdf转换成md
    2 存储md文件及md图片
    3 返回切片文本
    '''
    fbytes = minio_client.download_file(file_path)
    mdfs, imgdir, imgprev = do_parse(doc_name, fbytes)

    # 图片资源上传
    image_url_list = minio_client.upload_directory(imgdir, imgprev)
    # 替换md内容的url
    mdfile_img_replace(mdfs,minio_client.get_public_url_prev())
    # md文件上传
    md_oss_name = f'md/{os.path.basename(mdfs)}'
    minio_client.upload_file_spec_path(mdfs, md_oss_name)
    # md文件分片
    splitter = SmartMarkdownSplitter(512, 10)
    chunks = splitter.split_markdown_document(mdfs)
    return chunks , image_url_list


def create_mysql_chunk_metadata(document_oid, chunks):
    chunks_dbs = []
    for index, chunk in enumerate(chunks):
        oid = str(IDGeneratorFactory.get_generator().generate_id())
        doc_oid = document_oid
        chunk_index = index + 1
        chunk_content = chunk.page_content
        content_hash = hashlib.md5(chunk_content.encode('utf-8')).hexdigest()
        chunk_size = len(chunk_content)
        vector_id = generate_vector_id(doc_oid, oid, chunk_content)
        chunks_dbs.append({
            'oid': oid,
            'doc_oid': doc_oid,
            'chunk_index': chunk_index,
            'chunk_content': chunk_content,
            'content_hash': content_hash,
            'chunk_size': chunk_size,
            'vector_id': vector_id
        })
    return chunks_dbs

def llm_create_questions(text):
    '''llm构建模拟问题'''
    messages = [
        {"role": "user", "content": f'#文本片段'
                                    f'\n{text}'
                                    f'\n\n请根据以上内容,模拟提出最多3个问题'
                                    f'\n请以标准JSON数组格式输出,例如：[\"问题1\", \"问题2\", \"问题3\"]'}
    ]
    return ast.literal_eval(llm(messages))


def sava_elasticsearch_index(chunks_dbs):
    # 存储索引
    actions = []
    for b in chunks_dbs:
        # 文本转向量
        content = b['chunk_content']
        embedding = embed([content])[0].tolist()
        questions = llm_create_questions(content)
        logging.info(f"chunk={content}\n{questions}")
        es_doc = {
            "_index": index_name,
            "_id": b['vector_id'],
            "_source": {
                "doc_oid": b['doc_oid'],
                "chunk_oid": b['oid'],
                "chunk_index": b['chunk_index'],
                "vector_id": b['vector_id'],
                "content": content,
                "emb_512": embedding,
                "questions": questions if questions else [],
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        actions.append(es_doc)
        logging.info(f"{index_name} 生成 {b['vector_id']}")

    result = es_client.bulk_index(actions)
    logging.info(f"ES 存储结果: {result}")


def save_mysql(chunks_dbs):
    with get_pool_conn() as db:
        t_document_chunk = db['t_document_chunk']
        for b in chunks_dbs:
            inserted_pk = t_document_chunk.insert( b )
        logging.info(f'插入分片: {inserted_pk}')


def update_chunk_state(document_oid, chunk_count,chunk_status):
    with get_pool_conn() as db:
        t_document = db['t_document']
        updated = t_document.update(
            chunk_count=chunk_count,
            chunk_status=chunk_status,
            where={'oid': document_oid}
        )
        logging.info(f'更新文档分片状态: document_oid={document_oid},'
                     f' chunk_count={chunk_count},'
                     f' chunk_status={chunk_status},'
                     f' updated={updated}')


@router.post("/document/chunk")
async def start_document_chunk(request: dict):
    """开始文档分片"""
    doc_oid = request.get("doc_id")
    logging.info(f"文档分片 {doc_oid}")
    try:
        with get_pool_conn() as db:
            t_document = db['t_document']
            # 查询t_document MD5是否已存在
            info = t_document.find_one(oid=doc_oid)
            logging.info(f'文档分片 info={info}')
            if not info:
                return create_response_error_1003('文档不存在')

            # 文档分片
            mine_type = info['mime_type']
            doc_name = info['doc_name']
            file_path = info['file_path']
            if mine_type == 'application/pdf':
                document_oid = info['oid']
                chunks , image_url_list = do_chunk_pdf(doc_name,file_path)
                # 创建mysql分片数据表 图片数据表
                chunks_dbs = create_mysql_chunk_metadata(document_oid,chunks)
                # 文本embd->存储elasticsearch
                sava_elasticsearch_index(chunks_dbs)
                # 存入mysql元素据
                save_mysql(chunks_dbs)
                # 修改文档状态表
                update_chunk_state(document_oid,len(chunks),2)

            else : raise Exception('不支持的文档类型')

            return create_response(data={
                "task_id": f"chunk_task_{doc_oid}",
                "status": "completed"
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return create_response_error_1003(f'文档分片异常{e}')

