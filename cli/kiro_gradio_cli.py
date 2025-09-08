import gradio as gr
import requests
import json
from datetime import datetime
import os
import time

# 全局配置
API_BASE_URL = "http://localhost:8000/api"

# 全局状态
class AppState:
    def __init__(self):
        self.user_identifier = None
        self.session_id = None
        self.current_session_id = None
        self.expanded_chunks = set()

app_state = AppState()

# 工具函数
def convert_numpy_types(obj):
    """递归转换numpy类型为Python原生类型"""
    import numpy as np
    
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

def api_request(endpoint, method="GET", data=None, files=None):
    """统一的API请求函数"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {}
    if app_state.session_id:
        headers['X-Session-ID'] = str(app_state.session_id)
    
    # 转换numpy类型为JSON可序列化的类型
    if data is not None:
        data = convert_numpy_types(data)
    
    try:
        if method == "GET":
            response = requests.get(url, params=data, headers=headers)
        elif method == "POST":
            if files:
                response = requests.post(url, data=data, files=files, headers=headers)
            else:
                response = requests.post(url, json=data, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, json=data, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=data, headers=headers)
        resp_json = response.json()
        print(f'resp_json {resp_json}')
        return resp_json
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"code": "1001", "data": {"error": str(e)}}

def format_response_message(result):
    """格式化API响应消息"""
    if 'code' in result:
        if result["code"] == "0":
            return "✅ 操作成功", True
        else:
            return f"❌ 操作失败: {result.get('data', {})}", False
    return f"❌ 操作失败: {result}", False

# 登录功能
def login_user(user_identifier):
    """用户登录"""
    if not user_identifier:
        return (
            gr.update(value="❌ 请输入邮箱或手机号", visible=True), 
            gr.update(visible=True), 
            gr.update(visible=False)
        )
    
    result = api_request("/user/login", "POST", {"user_identifier": user_identifier})
    message, success = format_response_message(result)
    
    if success:
        app_state.user_identifier = user_identifier
        app_state.session_id = result["data"]["oid"]
        return (
            gr.update(value=f"✅ 登录成功！欢迎 {user_identifier}", visible=True), 
            gr.update(visible=False), 
            gr.update(visible=True)
        )
    else:
        return (
            gr.update(value=message, visible=True), 
            gr.update(visible=True), 
            gr.update(visible=False)
        )

def logout_user():
    """用户登出"""
    app_state.user_identifier = None
    app_state.session_id = None
    app_state.current_session_id = None
    app_state.expanded_chunks.clear()
    return (
        gr.update(value="👋 已安全退出，感谢使用！", visible=True), 
        gr.update(visible=True), 
        gr.update(visible=False)
    )

# 文档管理功能
def upload_document(file):
    """上传文档"""
    if not file or not app_state.user_identifier:
        return "❌ 请先登录并选择文件"
    
    try:
        with open(file.name, 'rb') as f:
            files = {"file": (os.path.basename(file.name), f.read())}
        data = {"user_identifier": app_state.user_identifier}
        result = api_request("/document/upload", "POST", data, files)
        
        message, success = format_response_message(result)
        if success:
            return f"{message}\n📄 文件信息: {json.dumps(result['data'], indent=2, ensure_ascii=False)}"
        return message
    except Exception as e:
        return f"❌ 上传失败: {str(e)}"

def get_document_list():
    """获取文档列表 - 返回表格数据"""
    if not app_state.user_identifier:
        return [], []
    
    result = api_request("/document/list", "GET", {"page": 1, "page_size": 20})
    
    if result.get("code") == "0":
        documents = result["data"]["documents"]
        if not documents:
            return [], []
        
        # 返回文档选择列表和表格数据
        doc_choices = []
        table_data = []
        
        for doc in documents:
            status_map = {0: "🔄 未分片", 1: "⏳ 分片中", 2: "✅ 已完成"}
            status = status_map.get(doc['chunk_status'], "❓ 未知")
            
            # 用于下拉选择的格式
            doc_choices.append(f"{doc['doc_name']} (ID: {doc['oid']})")
            
            # 操作按钮：只有未分片状态(0)才显示分片按钮
            action_button = "🚀 开始分片" if doc['chunk_status'] == 0 else "-"
            
            # 表格数据：[文档名, 大小, 分片数, 状态, 操作, 文档ID(隐藏)]
            table_data.append([
                doc['doc_name'],
                f"{doc['doc_size']/1024:.1f} KB",
                str(doc['chunk_count']),
                status,
                action_button,
                doc['oid']  # 隐藏列，用于获取文档ID
            ])
        
        return doc_choices, table_data
    else:
        return [], []

def handle_table_action(table_data, evt: gr.SelectData):
    """处理表格中的操作按钮点击"""
    # 检查table_data是否为空或无效
    if table_data is None or (hasattr(table_data, 'empty') and table_data.empty) or len(table_data) == 0:
        return "❌ 无效的操作"
    
    # 检查索引是否有效
    if evt.index[0] >= len(table_data):
        return "❌ 无效的操作"
    
    # 检查是否点击的是操作列（第5列，索引为4）
    if evt.index[1] != 4:
        return ""  # 不是操作列，不处理
    
    # 获取行数据 - 处理DataFrame和list两种情况
    if hasattr(table_data, 'iloc'):
        # pandas DataFrame
        row_data = table_data.iloc[evt.index[0]].tolist()
    else:
        # 普通list
        row_data = table_data[evt.index[0]]
    
    action_text = row_data[4]
    
    # 只处理分片按钮点击
    if action_text == "🚀 开始分片":
        doc_id = row_data[5]  # 获取文档ID
        doc_name = row_data[0]
        
        # 执行分片操作
        result = start_document_chunking(doc_id)
        
        # 返回弹窗消息
        if "✅" in result:
            return f"✅ 分片操作成功启动！\n\n📄 文档：{doc_name}\n🆔 ID：{doc_id}\n\n请稍后刷新列表查看分片进度。"
        else:
            return f"❌ 分片操作失败！\n\n📄 文档：{doc_name}\n🆔 ID：{doc_id}\n\n错误信息：{result}"
    
    return ""

def start_chunking_from_table(table_data, evt: gr.SelectData):
    """从表格中开始分片操作"""
    if not table_data or evt.index[0] >= len(table_data):
        return "❌ 无效的选择"
    
    # 获取选中行的文档ID（最后一列）
    doc_id = table_data[evt.index[0]][4]
    result = start_document_chunking(doc_id)
    return result

def start_document_chunking(doc_id):
    """开始文档分片"""
    if not doc_id or not app_state.user_identifier:
        return "❌ 请输入文档ID"
    
    result = api_request("/document/chunk", "POST", {"doc_id": doc_id})
    message, _ = format_response_message(result)
    return message

def get_document_chunks_by_selection(selected_doc):
    """根据选择的文档获取分片详情"""
    if not selected_doc or not app_state.user_identifier:
        return "❌ 请选择文档"
    
    # 从选择的文档字符串中提取文档ID
    try:
        doc_id = selected_doc.split("ID: ")[1].rstrip(")")
    except:
        return "❌ 无法解析文档ID"
    
    result = api_request("/document/chunks", "GET", {"doc_id": doc_id, "page": 1, "page_size": 100})
    
    if result.get("code") == "0":
        chunks = result["data"]["chunks"]
        total_chunks = result["data"]["total"]
        
        if not chunks:
            return "📄 该文档暂无分片数据"
        
        chunk_info = [f"📄 **分片详情** (共 {total_chunks} 个分片)\n"]
        
        for i, chunk in enumerate(chunks, 1):
            content_preview = chunk['chunk_content'][:300] + "..." if len(chunk['chunk_content']) > 300 else chunk['chunk_content']
            chunk_info.append(
                f"**📋 分片 {chunk['chunk_index']}**\n"
                f"大小: {chunk['chunk_size']} 字符\n"
                f"内容:\n{content_preview}\n"
                f"{'='*50}"
            )
        
        return "\n\n".join(chunk_info)
    else:
        message, _ = format_response_message(result)
        return message

def get_document_chunks(doc_id):
    """获取文档分片详情"""
    if not doc_id or not app_state.user_identifier:
        return "❌ 请输入文档ID"
    
    result = api_request("/document/chunks", "GET", {"doc_id": doc_id, "page": 1, "page_size": 50})
    
    if result.get("code") == "0":
        chunks = result["data"]["chunks"]
        total_chunks = result["data"]["total"]
        
        if not chunks:
            return "📄 暂无分片数据"
        
        chunk_info = [f"📄 分片详情 (共 {total_chunks} 个分片)\n"]
        
        for chunk in chunks[:10]:  # 限制显示前10个分片
            content_preview = chunk['chunk_content'][:200] + "..." if len(chunk['chunk_content']) > 200 else chunk['chunk_content']
            chunk_info.append(
                f"**分片 {chunk['chunk_index']}**\n"
                f"大小: {chunk['chunk_size']} 字符\n"
                f"内容预览: {content_preview}\n"
            )
        
        if total_chunks > 10:
            chunk_info.append(f"\n... 还有 {total_chunks - 10} 个分片未显示")
        
        return "\n".join(chunk_info)
    else:
        message, _ = format_response_message(result)
        return message



# 聊天功能
def chat_with_ai(message, history):
    """与AI聊天"""
    if not message or not app_state.user_identifier:
        return history + [["我", "❌ 请先登录"]], ""
    
    # 发送消息到API
    result = api_request("/chat/send", "POST", {
        "user_identifier": app_state.user_identifier,
        "message": message
    })
    
    if result.get("code") == "0":
        ai_response = result["data"]["ai_response"]
        response_time = result["data"].get("response_time", 0)
        related_docs = result["data"].get("related_docs", "")
        
        # 构建紧凑的回复格式
        response_parts = []
        
        # 主要回答
        response_parts.append(ai_response)
        
        # 添加相关文档信息（紧凑格式）
        if related_docs and related_docs.strip():
            doc_lines = related_docs.strip().split('\n')
            valid_docs = [line.strip() for line in doc_lines if line.strip()]
            
            if valid_docs:
                response_parts.append("\n📚 **相关文档:**")
                # 只显示前2个文档片段，每个最多100字符
                for i, doc in enumerate(valid_docs[:2]):
                    preview = doc[:100] + "..." if len(doc) > 100 else doc
                    response_parts.append(f"• {preview}")
                
                if len(valid_docs) > 2:
                    response_parts.append(f"• *还有 {len(valid_docs) - 2} 个相关片段*")
        
        # 添加响应时间（紧凑格式）
        if response_time > 0:
            response_parts.append(f"\n⚡ {response_time}ms")
        
        full_response = "\n".join(response_parts)
        
        # 更新对话历史
        history.append([message, full_response])
        
        return history, ""
    else:
        error_msg = f"❌ 发送失败: {result.get('data', {})}"
        history.append([message, error_msg])
        return history, ""

def get_chat_history():
    """获取聊天历史"""
    if not app_state.user_identifier:
        return []
    
    result = api_request("/chat/history", "GET", {
        "user_identifier": app_state.user_identifier
    })
    
    if result.get("code") == "0":
        chat_data = result["data"]
        if not chat_data:
            return []
        
        # 转换聊天历史格式为Gradio Chatbot格式
        history = []
        for i in range(0, len(chat_data), 2):
            if i + 1 < len(chat_data):
                user_msg = chat_data[i]
                ai_msg = chat_data[i + 1]
                
                if user_msg.get("role") == "user" and ai_msg.get("role") == "assistant":
                    # 保持历史记录的简洁格式
                    user_content = user_msg["content"]
                    ai_content = ai_msg["content"]
                    
                    history.append([user_content, ai_content])
        
        return history
    else:
        return []

# 自定义CSS样式
custom_css = """
/* 全局样式 - 自适应浏览器宽度 */
.gradio-container {
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 1rem !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* 主内容区域自适应 */
.main-content {
    width: 100% !important;
    max-width: none !important;
    margin: 0 auto !important;
    padding: 0 !important;
}

/* 登录区域居中但不限制最大宽度 */
.login-container {
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
}

.login-card {
    width: 100% !important;
    max-width: 500px !important;
    margin: 0 auto !important;
}

/* 标题样式 */
.main-title {
    text-align: center;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5rem !important;
    font-weight: 700 !important;
    margin-bottom: 2rem !important;
    letter-spacing: -0.02em;
}

/* 登录卡片样式 */
.login-card {
    background: white;
    border-radius: 16px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
    padding: 2rem !important;
    border: 1px solid #f0f0f0 !important;
}

/* 按钮样式优化 */
.gradio-button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
    border: none !important;
    height: 44px !important;
}

.gradio-button.primary {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
}

.gradio-button.primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3) !important;
}

.gradio-button.secondary {
    background: #f8f9fa !important;
    color: #495057 !important;
    border: 1px solid #e9ecef !important;
}

.gradio-button.secondary:hover {
    background: #e9ecef !important;
}

/* 输入框样式 */
.gradio-textbox input, .gradio-textbox textarea {
    border-radius: 8px !important;
    border: 1px solid #e9ecef !important;
    padding: 12px 16px !important;
    font-size: 14px !important;
    transition: all 0.2s ease !important;
}

.gradio-textbox input:focus, .gradio-textbox textarea:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

/* 标签页样式 */
.gradio-tabs .tab-nav {
    border-bottom: 2px solid #f8f9fa !important;
    margin-bottom: 1.5rem !important;
}

.gradio-tabs .tab-nav button {
    border-radius: 8px 8px 0 0 !important;
    font-weight: 500 !important;
    padding: 12px 24px !important;
    margin-right: 4px !important;
    border: none !important;
    background: transparent !important;
    color: #6c757d !important;
}

.gradio-tabs .tab-nav button.selected {
    background: white !important;
    color: #667eea !important;
    border-bottom: 2px solid #667eea !important;
}

/* 卡片容器样式 */
.content-card {
    background: white;
    border-radius: 12px !important;
    padding: 1.5rem !important;
    border: 1px solid #f0f0f0 !important;
    margin-bottom: 1rem !important;
}

/* 聊天界面样式 */
.chatbot-container {
    border-radius: 12px !important;
    border: 1px solid #e9ecef !important;
    overflow: hidden !important;
}

/* 聊天消息紧凑样式 */
.chatbot .message {
    margin: 4px 0 !important;
    padding: 8px 12px !important;
    line-height: 1.4 !important;
}

.chatbot .message.user {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border-radius: 18px 18px 4px 18px !important;
    margin-left: 20% !important;
    margin-right: 8px !important;
}

.chatbot .message.bot {
    background: #f8f9fa !important;
    color: #495057 !important;
    border-radius: 18px 18px 18px 4px !important;
    margin-right: 20% !important;
    margin-left: 8px !important;
    border: 1px solid #e9ecef !important;
}

/* 聊天气泡内容样式 */
.chatbot .message-content {
    font-size: 14px !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* 时间戳和元信息样式 */
.chat-meta {
    font-size: 11px !important;
    color: #6c757d !important;
    margin-top: 4px !important;
    opacity: 0.8 !important;
}

/* 文档片段样式 */
.doc-snippet {
    background: rgba(255, 255, 255, 0.1) !important;
    border-left: 3px solid #28a745 !important;
    padding: 6px 8px !important;
    margin: 6px 0 !important;
    border-radius: 4px !important;
    font-size: 12px !important;
    line-height: 1.3 !important;
}

/* 响应时间标签 */
.response-time {
    display: inline-block !important;
    background: #17a2b8 !important;
    color: white !important;
    padding: 2px 6px !important;
    border-radius: 10px !important;
    font-size: 10px !important;
    margin-top: 4px !important;
}

/* 文件上传区域样式 */
.file-upload {
    border: 2px dashed #e9ecef !important;
    border-radius: 12px !important;
    padding: 2rem !important;
    text-align: center !important;
    background: #f8f9fa !important;
    transition: all 0.2s ease !important;
}

.file-upload:hover {
    border-color: #667eea !important;
    background: #f0f4ff !important;
}

/* 下拉选择器样式 */
.gradio-dropdown {
    border-radius: 8px !important;
}

/* 响应式设计 - 全宽度适配 */
@media (max-width: 1200px) {
    .gradio-container {
        padding: 0 1rem !important;
    }
}

@media (max-width: 768px) {
    .gradio-container {
        padding: 0 0.5rem !important;
    }
    
    .main-title {
        font-size: 2rem !important;
    }
    
    .login-card {
        padding: 1.5rem !important;
        margin: 0 0.5rem !important;
    }
    
    .content-card {
        padding: 1rem !important;
        margin-bottom: 0.5rem !important;
    }
}

@media (max-width: 480px) {
    .gradio-container {
        padding: 0 0.25rem !important;
    }
    
    .main-title {
        font-size: 1.5rem !important;
    }
    
    .login-card {
        padding: 1rem !important;
        margin: 0 0.25rem !important;
    }
    
    .content-card {
        padding: 0.75rem !important;
    }
}

/* 确保所有组件都能自适应宽度 */
.gradio-row, .gradio-column, .gradio-group {
    width: 100% !important;
}

/* 标签页容器自适应 */
.gradio-tabs {
    width: 100% !important;
}

/* 聊天界面自适应 */
.chatbot-container {
    width: 100% !important;
}

/* 状态指示器 */
.status-success {
    color: #28a745 !important;
    background: #d4edda !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    border: 1px solid #c3e6cb !important;
}

.status-error {
    color: #dc3545 !important;
    background: #f8d7da !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    border: 1px solid #f5c6cb !important;
}

/* 图标样式 */
.icon {
    display: inline-block;
    margin-right: 8px;
    font-size: 1.1em;
}

/* 表格样式 */
.document-table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 1rem 0 !important;
}

.document-table th {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    padding: 12px 16px !important;
    text-align: left !important;
    font-weight: 600 !important;
    border: none !important;
}

.document-table td {
    padding: 12px 16px !important;
    border-bottom: 1px solid #e9ecef !important;
    vertical-align: middle !important;
}

.document-table tr:hover {
    background-color: #f8f9fa !important;
    cursor: pointer !important;
}

.document-table tr:nth-child(even) {
    background-color: #ffffff !important;
}

.document-table tr:nth-child(odd) {
    background-color: #fafbfc !important;
}

/* 表格按钮样式 */
.table-button {
    padding: 6px 12px !important;
    font-size: 12px !important;
    border-radius: 6px !important;
    border: none !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}

.table-button.chunk {
    background: #28a745 !important;
    color: white !important;
}

.table-button.chunk:hover {
    background: #218838 !important;
    transform: translateY(-1px) !important;
}

.table-button.view {
    background: #17a2b8 !important;
    color: white !important;
}

.table-button.view:hover {
    background: #138496 !important;
    transform: translateY(-1px) !important;
}
"""

# 创建Gradio界面
def create_gradio_app():
    with gr.Blocks(
        title="RAG知识库应用", 
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="gray",
            neutral_hue="gray",
            font=gr.themes.GoogleFont("Inter")
        ),
        css=custom_css
    ) as app:
        # 主标题
        gr.HTML("""
            <div class="main-title">
                🤖 RAG 智能知识库
            </div>
        """)
        
        # 登录区域
        with gr.Row(elem_classes=["login-container"]):
            with gr.Group(visible=True, elem_classes=["login-card"]) as login_area:
                gr.HTML("""
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <h2 style="color: #495057; font-weight: 600; margin: 0;">
                            <span class="icon">👤</span>用户登录
                        </h2>
                        <p style="color: #6c757d; margin: 0.5rem 0 0 0; font-size: 14px;">
                            请输入您的邮箱或手机号码登录系统
                        </p>
                    </div>
                """)
                
                with gr.Row():
                    user_input = gr.Textbox(
                        label="",
                        placeholder="📧 example@email.com 或 📱 13800138000",
                        scale=3,
                        container=False,
                        value="793065165@qq.com"
                    )
                    login_btn = gr.Button(
                        "🚀 立即登录", 
                        variant="primary", 
                        scale=1,
                        size="lg"
                    )
                
                login_status = gr.Textbox(
                    label="", 
                    interactive=False, 
                    visible=False,
                    container=False
                )
        
        # 主应用区域
        with gr.Group(visible=False, elem_classes=["main-content"]) as main_area:
            # 顶部导航栏
            with gr.Row(elem_classes=["content-card"]):
                with gr.Column(scale=4):
                    gr.HTML("""
                        <div style="display: flex; align-items: center;">
                            <span style="font-size: 1.5rem; margin-right: 12px;">📋</span>
                            <div>
                                <h3 style="margin: 0; color: #495057; font-weight: 600;">智能知识库管理</h3>
                                <p style="margin: 0; color: #6c757d; font-size: 14px;">上传文档、管理知识库、智能问答</p>
                            </div>
                        </div>
                    """)
                with gr.Column(scale=1):
                    logout_btn = gr.Button(
                        "🚪 退出登录", 
                        variant="secondary",
                        size="sm"
                    )
            
            with gr.Tabs(selected=0) as tabs:
                # 文档上传标签页
                with gr.Tab("📄 文档上传", elem_id="upload-tab"):
                    with gr.Column(elem_classes=["content-card"]):
                        gr.HTML("""
                            <div style="text-align: center; margin-bottom: 1.5rem;">
                                <h3 style="color: #495057; font-weight: 600; margin-bottom: 0.5rem;">
                                    📤 上传知识文档
                                </h3>
                                <p style="color: #6c757d; margin: 0; font-size: 14px;">
                                    支持 PDF、Word、文本等多种格式，为AI提供知识来源
                                </p>
                            </div>
                        """)
                        
                        file_upload = gr.File(
                            label="",
                            file_types=[".pdf", ".doc", ".docx", ".txt", ".md"],
                            elem_classes=["file-upload"],
                            container=False
                        )
                        
                        with gr.Row():
                            gr.Column(scale=1)  # 占位
                            upload_btn = gr.Button(
                                "🚀 开始上传", 
                                variant="primary",
                                size="lg",
                                scale=2
                            )
                            gr.Column(scale=1)  # 占位
                        
                        upload_result = gr.Textbox(
                            label="📋 上传状态", 
                            lines=4, 
                            interactive=False,
                            visible=False
                        )
                
                # 文档管理标签页
                with gr.Tab("📋 文档管理", elem_id="manage-tab"):
                    with gr.Column():
                        # 文档列表卡片
                        with gr.Group(elem_classes=["content-card"]):
                            with gr.Row():
                                gr.HTML("""
                                    <div>
                                        <h3 style="margin: 0; color: #495057; font-weight: 600;">
                                            📚 文档库管理
                                        </h3>
                                        <p style="margin: 0.5rem 0 0 0; color: #6c757d; font-size: 14px;">
                                            点击表格行可选择文档，双击文档名可开始分片
                                        </p>
                                    </div>
                                """)
                                refresh_docs_btn = gr.Button(
                                    "🔄 刷新列表", 
                                    variant="secondary",
                                    size="sm"
                                )
                            
                            # 文档表格
                            doc_table = gr.Dataframe(
                                headers=["📄 文档名", "📊 大小", "🔢 分片数", "📋 状态", "⚙️ 操作", "🆔 ID"],
                                datatype=["str", "str", "str", "str", "str", "str"],
                                col_count=(6, "fixed"),
                                row_count=(10, "dynamic"),
                                interactive=True,
                                wrap=True,
                                elem_classes=["document-table"]
                            )
                        
                        # 操作消息显示区域
                        with gr.Group(visible=False, elem_classes=["content-card"]) as message_area:
                            with gr.Row():
                                operation_message = gr.Textbox(
                                    label="📢 操作结果",
                                    lines=4,
                                    interactive=False,
                                    container=False,
                                    scale=4
                                )
                                close_message_btn = gr.Button(
                                    "❌ 关闭",
                                    variant="secondary",
                                    size="sm",
                                    scale=1
                                )
                        
                        # 操作说明
                        with gr.Row():
                            with gr.Group(elem_classes=["content-card"]):
                                gr.HTML("""
                                    <div style="text-align: center; padding: 1rem;">
                                        <h4 style="margin: 0 0 0.5rem 0; color: #495057; font-weight: 600;">
                                            📋 操作说明
                                        </h4>
                                        <p style="margin: 0; color: #6c757d; font-size: 14px;">
                                            • 点击表格中的 <strong>🚀 开始分片</strong> 按钮对文档进行分片<br>
                                            • 只有 <strong>🔄 未分片</strong> 状态的文档可以进行分片操作<br>
                                            • 分片完成后会自动刷新列表显示最新状态
                                        </p>
                                    </div>
                                """)
                        
                        # 分片详情查看区域
                        with gr.Group(elem_classes=["content-card"]):
                            gr.HTML("""
                                <h4 style="margin: 0 0 1rem 0; color: #495057; font-weight: 600;">
                                    👁️ 分片详情查看
                                </h4>
                            """)
                            
                            with gr.Row():
                                doc_selector = gr.Dropdown(
                                    label="选择文档查看分片详情",
                                    choices=[],
                                    value=None,
                                    interactive=True,
                                    allow_custom_value=False,
                                    container=False,
                                    scale=3
                                )
                                view_chunks_btn = gr.Button(
                                    "📄 查看详情", 
                                    variant="primary",
                                    scale=1
                                )
                        
                        # 分片详情显示
                        chunk_details = gr.Textbox(
                            label="📄 分片详情", 
                            lines=12, 
                            interactive=False,
                            visible=False
                        )
                
                # 智能问答标签页
                with gr.Tab("🤖 智能问答", elem_id="chat-tab"):
                    with gr.Column():
                        # 聊天标题卡片
                        with gr.Group(elem_classes=["content-card"]):
                            with gr.Row():
                                gr.HTML("""
                                    <div>
                                        <h3 style="margin: 0 0 0.5rem 0; color: #495057; font-weight: 600;">
                                            💬 AI 智能助手
                                        </h3>
                                        <p style="margin: 0; color: #6c757d; font-size: 14px;">
                                            基于您上传的文档进行智能问答，获得精准答案和相关文档片段
                                        </p>
                                    </div>
                                """)
                                with gr.Column(scale=1):
                                    load_history_btn = gr.Button(
                                        "📜 加载历史", 
                                        variant="secondary",
                                        size="sm"
                                    )
                        
                        # 聊天界面
                        chatbot = gr.Chatbot(
                            label="",
                            height=420,
                            avatar_images=["👤", "🤖"],
                            bubble_full_width=False,
                            elem_classes=["chatbot-container"],
                            container=False,
                            show_copy_button=True,
                            show_share_button=False,
                            layout="panel"
                        )
                        
                        # 输入区域
                        with gr.Group(elem_classes=["content-card"]):
                            gr.HTML("""
                                <div style="margin-bottom: 0.5rem;">
                                    <small style="color: #6c757d;">
                                        � 提示送：AI会根据您上传的文档内容进行回答，并显示相关文档片段和响应时间
                                    </small>
                                </div>
                            """)
                            
                            with gr.Row():
                                msg_input = gr.Textbox(
                                    label="",
                                    placeholder="💭 输入问题，基于文档智能回答...",
                                    scale=5,
                                    lines=1,
                                    container=False,
                                    max_lines=2
                                )
                                with gr.Column(scale=1):
                                    send_btn = gr.Button(
                                        "📤 发送", 
                                        variant="primary",
                                        size="lg"
                                    )
                                    clear_btn = gr.Button(
                                        "🗑️ 清空", 
                                        variant="secondary",
                                        size="sm"
                                    )
        
        # 事件绑定
        login_btn.click(
            login_user,
            inputs=[user_input],
            outputs=[login_status, login_area, main_area]
        )
        
        logout_btn.click(
            logout_user,
            outputs=[login_status, login_area, main_area]
        )
        
        # 文档上传事件
        def upload_and_refresh(file):
            upload_result = upload_document(file)
            # 如果上传成功，同时刷新文档列表
            if "✅" in upload_result:
                doc_choices, table_data = get_document_list()
                return (
                    gr.update(value=upload_result, visible=True), 
                    gr.update(choices=doc_choices, value=None), 
                    table_data
                )
            else:
                return (
                    gr.update(value=upload_result, visible=True), 
                    gr.update(), 
                    []
                )
        
        upload_btn.click(
            upload_and_refresh,
            inputs=[file_upload],
            outputs=[upload_result, doc_selector, doc_table]
        )
        
        # 文档管理事件
        def refresh_document_list():
            doc_choices, table_data = get_document_list()
            return (
                gr.update(choices=doc_choices, value=None), 
                table_data
            )
        
        def handle_view_chunks(selected_doc):
            """查看分片详情"""
            result = get_document_chunks_by_selection(selected_doc)
            return gr.update(value=result, visible=True)
        
        # 绑定事件
        refresh_docs_btn.click(
            refresh_document_list,
            outputs=[doc_selector, doc_table]
        )
        

        
        # 表格点击事件 - 处理分片按钮点击
        def handle_table_click_with_message(table_data, evt: gr.SelectData):
            message = handle_table_action(table_data, evt)
            if message:
                # 显示消息并自动刷新表格
                doc_choices, updated_table_data = get_document_list()
                return (
                    message,
                    gr.update(visible=True),  # 显示消息区域
                    updated_table_data,
                    gr.update(choices=doc_choices, value=None)
                )
            return "", gr.update(visible=False), table_data, gr.update()
        
        def close_message():
            """关闭消息显示"""
            return gr.update(visible=False)
        
        doc_table.select(
            handle_table_click_with_message,
            inputs=[doc_table],
            outputs=[operation_message, message_area, doc_table, doc_selector]
        )
        
        close_message_btn.click(
            close_message,
            outputs=[message_area]
        )
        
        view_chunks_btn.click(
            handle_view_chunks,
            inputs=[doc_selector],
            outputs=[chunk_details]
        )
        
        # 聊天事件
        def clear_chat():
            """清空当前对话"""
            return []
        
        def load_chat_history():
            """加载聊天历史"""
            history = get_chat_history()
            return history
        
        # 加载历史记录
        load_history_btn.click(
            load_chat_history,
            outputs=[chatbot]
        )
        
        # 发送消息
        send_btn.click(
            chat_with_ai,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        )
        
        # 回车发送消息
        msg_input.submit(
            chat_with_ai,
            inputs=[msg_input, chatbot],
            outputs=[chatbot, msg_input]
        )
        
        # 清空对话（仅清空界面，不影响服务器历史）
        clear_btn.click(
            clear_chat,
            outputs=[chatbot]
        )
    
    return app

if __name__ == "__main__":
    app = create_gradio_app()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        debug=True
    )