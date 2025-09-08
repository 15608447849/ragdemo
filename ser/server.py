import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')  # 如果需要保存到文件
    ]
)


from utils.conf import get_config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from utils.comm import create_response


# 加载配置文件
get_config("SERVICE_CONF",)
HOST_IP = get_config('api', {}).get("host", "127.0.0.1")
HOST_PORT = get_config('api', {}).get("http_port")


app = FastAPI(
    title="rag",
    description="api",
    version="1.0.0",
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入路由

from api.user import router as user
app.include_router(user, prefix="/api", tags=["documents"])
logging.info("add router: user")


from api.doc import router as doc
app.include_router(doc, prefix="/api", tags=["documents"])
logging.info("add router: doc")

from api.chunk import router as chuk
app.include_router(chuk, prefix="/api", tags=["documents"])
logging.info("add router: chuk")


from api.chat import router as chat
app.include_router(chat, prefix="/api", tags=["documents"])
logging.info("add router: chat")


@app.get("/")
async def root():
    formatted_time =  datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    return create_response(data=f'API Server is running, {formatted_time}')





if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST_IP, port=HOST_PORT)
