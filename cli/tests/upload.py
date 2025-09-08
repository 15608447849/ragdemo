import streamlit as st
import requests
from datetime import datetime
import os

st.set_page_config(
    page_title="文件上传客户端",
    page_icon="📁",
    layout="wide"
)

# 页面标题
st.title("📁 文件上传客户端")
st.markdown("---")

# 服务器配置
API_URL = "http://localhost:8000/api/upload"


# 检查服务器状态
def check_server_status():
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        return response.status_code == 200
    except:
        return False


# 侧边栏
with st.sidebar:
    st.header("支持的文件格式")
    st.markdown("""
    - 📄 PDF (.pdf)
    - 📝 Word (.doc, .docx)
    - 🎨 PowerPoint (.ppt, .pptx)
    - 📋 Markdown (.md)
    - 📝 Text (.txt)
    """)


# 文件上传区域
st.subheader("选择要上传的文件")
uploaded_file = st.file_uploader(
    "拖放文件或点击选择",
    type=["pdf", "doc", "docx", "ppt", "pptx", "md", "txt"],
    help="支持多选文件"
)

if uploaded_file:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.info(f"**文件名:** {uploaded_file.name}")
    with col2:
        file_size = len(uploaded_file.getvalue()) / 1024
        st.info(f"**大小:** {file_size:.1f} KB")

    # 上传按钮
    if st.button("🚀 开始上传", type="primary", use_container_width=True):
        try:
            # 显示进度
            with st.spinner("上传中..."):
                # 准备文件数据
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

                # 发送请求
                response = requests.post(API_URL, files=files)

                if response.status_code == 200:
                    result = response.json()
                    st.success("✅ 上传成功！")

                    # 显示结果详情
                    with st.expander("查看上传详情", expanded=True):
                        st.json(result)

                    st.balloons()  # 庆祝动画
                else:
                    error_msg = response.json().get("detail", "未知错误")
                    st.error(f"❌ 上传失败: {error_msg}")

        except Exception as e:
            st.error(f"❌ 上传错误: {str(e)}")






# 使用说明
with st.expander("使用说明", expanded=False):
    st.markdown("""
    1. **选择文件**: 点击"选择文件"或拖放文件到上传区域
    3. **查看结果**: 上传完成后查看结果详情

    **注意事项**:
    - 确保文件服务器正在运行
    - 支持的文件格式: PDF, Word, PowerPoint, Markdown, Text
    """)
# 页脚
st.markdown("---")
st.caption(f"© 文件上传客户端 | 最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# streamlit run upload.py