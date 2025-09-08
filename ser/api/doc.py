
from fastapi import APIRouter,Request, UploadFile, File, HTTPException, status
from pathlib import Path
import hashlib
import logging
from datetime import datetime
from ser.utils.comm import create_response_error_1003, create_response, create_response_error_1002, \
    create_response_error_1004
from ser.utils.db import get_pool_conn
from ser.utils.genid import IDGeneratorFactory
from ser.utils.minio_cli import minio_client

router = APIRouter()


# 支持的文件类型
SUPPORTED_EXTENSIONS = {
    '.md': 'text/markdown',
    '.txt': 'text/plain',
    '.pdf': 'application/pdf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
}

SUPPORTED_MIME_TYPES = list(SUPPORTED_EXTENSIONS.values())

def get_file_extension(filename: str) -> str:
    """获取文件扩展名"""
    return Path(filename).suffix.lower()
def is_supported_file(file: UploadFile) -> bool:
    """检查文件类型是否支持"""
    extension = get_file_extension(file.filename)
    return extension in SUPPORTED_EXTENSIONS



def save_file_to_local(file_content: bytes, filename: str) -> str:
    """保存文件到磁盘 弃用"""
    UPLOAD_DIR = Path("files")
    UPLOAD_DIR.mkdir(exist_ok=True, parents=True)
    logging.info(f'UPLOAD_DIR = {UPLOAD_DIR}')

    # 生成唯一文件名（时间戳+哈希）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_hash = hashlib.md5(file_content).hexdigest()
    extension = get_file_extension(filename)
    new_filename = f"{timestamp}_{file_hash}{extension}"
    file_path = UPLOAD_DIR / new_filename
    # 保存文件
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)
    return new_filename





@router.post("/document/upload", summary="上传文档文件")
async def upload_document(request: Request,file: UploadFile = File(...)):
    """
    上传支持的文档文件格式：
    - PDF (.pdf)
    - Word (.doc, .docx)
    - PowerPoint (.ppt, .pptx)
    - Markdown (.md)
    - Text (.txt)
    """
    upload_user_oid = request.headers.get('X-Session-ID')
    if not upload_user_oid:
        return create_response_error_1002(data="请先登录")

    if not is_supported_file(file):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型。支持的类型: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )

    try:
        # 读取文件内容
        content = await file.read()
        # 文件MD5
        file_md5 = hashlib.md5(content).hexdigest()
        # 信息存入数据库
        with get_pool_conn() as db:
            t_document = db['t_document']
            # 查询t_document MD5是否已存在
            dbinfo = t_document.find_one(file_hash=file_md5)
            if dbinfo:
                return create_response_error_1003(data=f"文件已存在,MD5:{file_md5}")

        # 文件大小
        file_size = len(content)
        # 生成文档ID
        doc_oid = IDGeneratorFactory.get_generator().generate_id()

        # 获取文件扩展名和 MIME 类型
        extension = get_file_extension(file.filename)
        mime_type = SUPPORTED_EXTENSIONS.get(extension)

        # 使用 MinIO 上传文件
        object_name = minio_client.upload_file(
            prev=doc_oid,
            file_content=content,
            filename=file.filename,
            content_type=mime_type
        )

        # 生成文件访问 URL
        file_url = minio_client.get_public_url(object_name)

        # 存入数据库
        with get_pool_conn() as db:
            t_document = db['t_document']
            inserted_pk = t_document.insert(
                {
                'oid': doc_oid,
                'doc_name': file.filename,
                'doc_size': file_size,
                'file_path': object_name,
                'file_hash': file_md5,
                'mime_type': mime_type,
                'upload_user_oid': upload_user_oid
                }
            )
            logging.info(f"文档{file.filename}已存入数据库,ID: {inserted_pk} url: {file_url}")
            return create_response(
                data={
                    "file_url": file_url,
                    "file_name": file.filename,
                    "object_name": object_name,
                    "file_size": file_size,
                    "file_type": mime_type,
                    "file_md5" : file_md5,
                    "upload_time": datetime.now().isoformat()
                }
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return create_response_error_1003()


@router.get("/document/list")
async def upload_document(page: int = 1,page_size: int = 10):
    """获取文档列表"""
    try:
        logging.info("获取文档列表")
        with get_pool_conn() as db:

            # 查询总记录数
            count_query = f"""SELECT COUNT(*) as total FROM t_document d"""
            count_result = list(db.query(count_query))
            total = count_result[0]['total'] if count_result else 0
            # 计算偏移量
            offset = (page - 1) * page_size
            # 查询数据
            query = f'''SELECT 
                               u.user_identifier,
                               d.oid,
                               d.doc_name,
                               d.doc_size,
                               d.file_path,
                               d.file_hash,
                               d.mime_type,
                               d.chunk_count,
                               d.chunk_status,
                               d.upload_user_oid,
                               d.crt,
                               d.upt
                           FROM t_document d
                           LEFT JOIN t_user u ON d.upload_user_oid = u.oid
                           ORDER BY d.crt DESC
                           LIMIT :limit OFFSET :offset
               '''

            result = db.query(query, {"limit": page_size, "offset": offset})
            documents = list(result)
            return create_response(
                data={
                    "documents": documents,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return create_response_error_1004()


@router.get("/document/chunks")
async def get_document_chunks(doc_id: int, page: int = 1, page_size: int = 10):
    """获取文档分片列表"""
    try:
        logging.info(f"获取文档分片列表 {doc_id}")
        with get_pool_conn() as db:

            # 查询总记录数
            count_query = f"""SELECT COUNT(*) as total FROM t_document_chunk d where d.doc_oid=:doc_oid"""
            count_result = list(db.query(count_query, {"doc_oid": doc_id}))
            total = count_result[0]['total'] if count_result else 0
            # 计算偏移量
            offset = (page - 1) * page_size
            # 查询数据
            query = f'''SELECT 
                            d.oid chunk_id,
                            d.doc_oid doc_id,
                            d.chunk_content chunk_content,
                            d.chunk_index chunk_index,
                            d.chunk_size chunk_size
                           FROM t_document_chunk d where d.doc_oid=:doc_oid
                           ORDER BY d.chunk_index ASC
                           LIMIT :limit OFFSET :offset
               '''

            result = db.query(query, {"doc_oid": doc_id, "limit": page_size, "offset": offset})
            documents = list(result)
            return create_response(
                data={
                    "chunks": documents,
                    "total": total,
                    "page": page,
                    "page_size": page_size
                }
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return create_response_error_1004()

