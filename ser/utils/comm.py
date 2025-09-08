import hashlib
from datetime import datetime


def create_response(code="0", data=None):
    """创建统一响应格式"""
    return {"code": code, "data": data or {}}

def create_response_error_1002(data="用户不存在"):
    return create_response('1002', data)
def create_response_error_1003(data="文档上传错误"):
    return create_response('1003', data)

def create_response_error_1004( data="数据库操作错误"):
    return create_response('1004', data)


def generate_vector_id( doc_id: str, chunk_id: str, content: str) -> str:
    """生成向量ID的hash值"""
    hash_input = f"{doc_id}_{chunk_id}_{content}"
    return hashlib.md5(hash_input.encode('utf-8')).hexdigest()

def get_current_time():
    """获取当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

