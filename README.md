# 个人学习rag技术demo 
## 示例
![上传](./images/1.jpg "上传资料")  
![文档](./images/2.jpg "管理文档,文档分片")  
![回复](./images/3.jpg "回复")  
![回复](./images/4.jpg "回复")  

# 环境部署 bash
`conda create -n ragdemo python==3.12 -y`  
`pip install torch==2.7.1+cu126  torchaudio==2.7.1+cu126 torchvision==0.22.1+cu126 -f  https://mirrors.aliyun.com/pytorch-wheels/cu126`  
`pip install pymysql==1.1.1 pydantic==2.11.7 PyYAML==6.0.2 Requests==2.32.5 SQLAlchemy==1.4.54 loguru==0.7.3 -i https://mirrors.aliyun.com/pypi/simple`  
`pip install dataset==1.6.2 redis==6.4.0 minio==7.2.4 elasticsearch==8.11.0 -i https://mirrors.aliyun.com/pypi/simple`  
`pip install fastapi uvicorn[standard] -i  https://pypi.tuna.tsinghua.edu.cn/simple`  
`pip install langchain==0.3.27 -i  https://pypi.tuna.tsinghua.edu.cn/simple`  
`pip install numpy==2.3.2 sentence_transformers==5.1.0 transformers==4.56.0 -i  https://pypi.tuna.tsinghua.edu.cn/simple`  
`pip install gradio==5.44.1 huggingface_hub==0.34.4 -i https://mirrors.aliyun.com/pypi/simple`  
`pip install -U hf-transfer -i https://pypi.tuna.tsinghua.edu.cn/simple`  
`pip install huggingface_hub[hf_xet] -i https://pypi.tuna.tsinghua.edu.cn/simple`  
`pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple`  
`pip install uv -i https://mirrors.aliyun.com/pypi/simple`  
`uv pip install -U "mineru[core]" -i https://mirrors.aliyun.com/pypi/simple`  



# 模型下载
`cd ser/models && python download_model`  

# 启动基础服务
`cd docker`  
`docker compose -f docker-compose-base.yml up -d`







