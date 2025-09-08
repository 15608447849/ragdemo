import os
import logging
from elasticsearch import Elasticsearch
from .conf import get_config

PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir
            )
)

class ElasticsearchClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ElasticsearchClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 Elasticsearch 客户端"""
        es_config = get_config('elasticsearch', {})

        self.client = Elasticsearch(
            hosts=[es_config.get('host', 'localhost:9200')],
            http_auth=(
                es_config.get('username', ''),
                es_config.get('password', '')
            ) if es_config.get('username') else None,
            verify_certs=False,
            timeout=es_config.get('timeout', 600)
        )

        # 测试连接
        try:
            if self.client.ping():
                logging.info("Elasticsearch 连接成功")
            else:
                logging.info("Elasticsearch 连接失败")
        except Exception as e:
            logging.info(f"Elasticsearch 连接异常: {e}")

    def create_index(self, index_name, mapping=None):
        """创建索引"""
        try:
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(index=index_name, body=mapping or {})
                logging.info(f"索引 {index_name} 创建成功")
            else:
                logging.info(f"索引 {index_name} 已存在")
        except Exception as e:
            logging.info(f"创建索引失败: {e}")
            raise

    def index_document(self, index_name, document, doc_id=None):
        """索引文档"""
        try:
            result = self.client.index(
                index=index_name,
                body=document,
                id=doc_id
            )
            return result
        except Exception as e:
            logging.info(f"索引文档失败: {e}")
            raise

    def bulk_index(self, actions):
        """批量索引文档"""
        try:
            from elasticsearch.helpers import bulk
            result = bulk(self.client, actions)
            return result
        except Exception as e:
            logging.info(f"批量索引失败: {e}")
            # 如果是 BulkIndexError，显示详细错误信息
            if hasattr(e, 'errors'):
                logging.info("详细错误信息:")
                for i, error in enumerate(e.errors):
                    logging.info(f"  文档 {i + 1} 错误: {error}")
            raise

    def search(self, index, query):
        """搜索文档"""
        try:
            result = self.client.search(
                index=index,
                body=query
            )
            return result
        except Exception as e:
            logging.info(f"搜索失败: {e}")
            raise


# 全局实例
es_client = ElasticsearchClient()






