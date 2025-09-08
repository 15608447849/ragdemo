import json
import logging
from fastapi import APIRouter
import redis
from typing import List, Dict, Any

from ser.utils.conf import get_config

router = APIRouter()


# Redis 客户端配置
class RedisClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 Redis 客户端"""
        redis_config = get_config('redis', {})  # 从配置文件获取 Redis 配置

        self.client = redis.Redis(
            host=redis_config.get('host', 'localhost'),
            port=redis_config.get('port', 6379),
            db=redis_config.get('db', 0),
            password=redis_config.get('password', None),
            decode_responses=True,  # 自动解码响应
            encoding='utf-8'
        )

    def set_list(self, key: str, data_list: List[Dict[str, Any]]) -> bool:
        """
        存储 list<object> 到 Redis
        :param key: 字符串键
        :param data_list: 对象列表
        :return: 是否成功
        """
        try:
            # 将对象列表转换为 JSON 字符串存储
            json_data = json.dumps(data_list, ensure_ascii=False)
            self.client.set(key, json_data)
            return True
        except Exception as e:
            logging.error(f"存储数据到 Redis 失败: {e}")
            return False

    def get_list(self, key: str) -> List[Dict[str, Any]]:
        """
        从 Redis 获取 list<object>
        :param key: 字符串键
        :return: 对象列表
        """
        try:
            json_data = self.client.get(key)
            if json_data:
                return json.loads(json_data)
            return []
        except Exception as e:
            logging.error(f"从 Redis 获取数据失败: {e}")
            return []

    def append_to_list(self, key: str, item: Dict[str, Any]) -> int:
        """
        向列表追加对象
        :param key: 字符串键
        :param item: 要追加的对象
        :return: 列表长度
        """
        try:
            # 获取现有列表
            existing_list = self.get_list(key)
            # 添加新项
            existing_list.append(item)
            # 重新存储
            self.set_list(key, existing_list)
            return len(existing_list)
        except Exception as e:
            logging.error(f"向 Redis 列表追加数据失败: {e}")
            return -1

    def delete_key(self, key: str) -> bool:
        """
        删除指定键
        :param key: 字符串键
        :return: 是否成功
        """
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logging.error(f"从 Redis 删除键失败: {e}")
            return False


# 全局 Redis 客户端实例
redis_client = RedisClient()

if __name__ == '__main__':
    # messages = [
    #     {"role": "system", "content": "你是一个 helpful 的 AI 助手"},
    #     {"role": "user", "content": '请简要介绍一下大型语言模型','timestamp': '2023-05-01 12:00:00'},
    #     {"role": "assistant", "content": '我是一个......xxx模型','timestamp': '2023-05-01 12:00:10'}
    # ]
    #
    # redis_client.set_list(f"chat_history:test", messages)
    print(redis_client.get_list(f"chat_history:test"))
    # [{'role': 'system', 'content': '你是一个 helpful 的 AI 助手'}, {'role': 'user', 'content': '请简要介绍一下大型语言模型', 'timestamp': '2023-05-01 12:00:00'}, {'role': 'assistant', 'content': '我是一个......xxx模型', 'timestamp': '2023-05-01 12:00:10'}]
    # print('无数据> ',redis_client.get_list(f"chat_history:node")) # []
