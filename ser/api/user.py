import logging

from fastapi import APIRouter
from pydantic import BaseModel
from ser.utils.comm import create_response, create_response_error_1004
from ser.utils.db import get_pool_conn
from ser.utils.genid import IDGeneratorFactory

router = APIRouter()

class UserLoginRequest(BaseModel):
    user_identifier: str

@router.post("/user/login")
async def user_login(request: UserLoginRequest):
    """用户登录/创建会话"""
    user_identifier = request.user_identifier
    logging.info(f'用户登录: {user_identifier}')

    try:
        with get_pool_conn() as db:
            t_user = db['t_user']
            # 查询用户
            user = t_user.find_one(user_identifier=user_identifier)
            logging.info(f'用户查询: {user}')
            if not user:
                # 不存在 创建用户
                inserted_pk = t_user.insert({
                    'oid' : IDGeneratorFactory.get_generator().generate_id(),
                    'user_identifier' : user_identifier
                })
                user = t_user.find_one(oid=inserted_pk)
                logging.info(f'插入用户: {user}')
            return create_response(data=user)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return create_response_error_1004()
