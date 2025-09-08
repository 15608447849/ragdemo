import logging
import re
import os
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Any, Optional

class SmartMarkdownSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

    def extract_markdown_structure(self, content: str) -> List[Dict[str, Any]]:
        """
        提取 Markdown 结构：标题和对应的内容块
        """
        # 正则表达式匹配标题和内容
        # 匹配 ## 二级标题、### 三级标题等小标题
        pattern = r'(^#{2,6} .+?)(?=^#{1,6} |\Z)'
        matches = re.findall(pattern, content, flags=re.MULTILINE | re.DOTALL)

        sections = []
        for match in matches:
            lines = match.strip().split('\n')
            if not lines:
                continue

            # 第一个行是标题
            header = lines[0].strip()
            # 剩余行是内容
            section_content = '\n'.join(lines[1:]).strip()

            if section_content:
                sections.append({
                    'header': header,
                    'content': section_content,
                    'full_content': match.strip()
                })

        return sections

    def preserve_images_and_links(self, text: str) -> List[str]:
        """
        保护图片链接和特殊格式不被截断
        """
        # 匹配图片链接 ![](path/to/image.jpg)
        image_pattern = r'!\[.*?\]\(.*?\)'
        # 匹配普通链接 [text](url)
        link_pattern = r'\[.*?\]\(.*?\)'
        # 匹配代码块 ```code```
        code_pattern = r'```.*?```'

        # 找到所有需要保护的元素
        protected_elements = []
        for pattern in [image_pattern, link_pattern, code_pattern]:
            protected_elements.extend(re.findall(pattern, text, flags=re.DOTALL))

        # 临时替换保护元素
        placeholder_map = {}
        for i, element in enumerate(protected_elements):
            placeholder = f"__PROTECTED_{i}__"
            placeholder_map[placeholder] = element
            text = text.replace(element, placeholder)

        return text, placeholder_map

    def restore_protected_elements(self, text: str, placeholder_map: Dict[str, str]) -> str:
        """
        恢复被保护的元素
        """
        for placeholder, element in placeholder_map.items():
            text = text.replace(placeholder, element)
        return text

    def split_within_section(self, section_content: str, header: str, source: str) -> List[Document]:
        """
        在单个小标题section内进行智能分块
        """
        chunks = []

        # 先保护图片和链接
        protected_content, placeholder_map = self.preserve_images_and_links(section_content)

        # 使用标准分块器
        temp_docs = [Document(page_content=protected_content)]
        split_chunks = self.text_splitter.split_documents(temp_docs)

        # 恢复被保护的元素并创建最终chunks
        for chunk in split_chunks:
            restored_content = self.restore_protected_elements(chunk.page_content, placeholder_map)

            # 确保内容不为空
            if restored_content.strip():
                chunks.append(Document(
                    page_content=f"{header}\n{restored_content}",
                    metadata={"source": source, "header": header}
                ))

        return chunks

    def split_markdown_document(self, file_path: str) -> List[Document]:
        """
        主分块函数
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取文档结构
        sections = self.extract_markdown_structure(content)

        all_chunks = []

        for section in sections:
            header = section['header']
            section_content = section['content']

            # 对小标题下的内容进行分块
            section_chunks = self.split_within_section(section_content, header, file_path)
            all_chunks.extend(section_chunks)

        # 处理没有小标题的文本
        self._process_untitled_content(content, sections, file_path, all_chunks)

        logging.info(f"文件 {os.path.basename(file_path)} 分块完成: {len(all_chunks)} 个块")
        return all_chunks

    def _process_untitled_content(self, content: str, sections: List[Dict], file_path: str, all_chunks: List[Document]):
        """
        处理没有小标题的文本内容
        """
        # 获取所有已处理的内容
        processed_content = "".join([section['full_content'] for section in sections])

        # 找出未处理的内容
        remaining_content = content.replace(processed_content, "").strip()

        if remaining_content:
            # 保护特殊元素
            protected_content, placeholder_map = self.preserve_images_and_links(remaining_content)

            # 分块
            temp_docs = [Document(page_content=protected_content)]
            split_chunks = self.text_splitter.split_documents(temp_docs)

            for chunk in split_chunks:
                restored_content = self.restore_protected_elements(chunk.page_content, placeholder_map)
                if restored_content.strip():
                    all_chunks.append(Document(
                        page_content=restored_content,
                        metadata={"source": file_path, "header": "无标题"}
                    ))

class MarkdownImageProcessor:

    def extract_local_image_paths(self, markdown_content: str, base_dir: str = "") -> List[str]:
        """
        从 Markdown 内容中提取本地图片路径

        Args:
            markdown_content: Markdown 内容
            base_dir: 基础目录路径

        Returns:
            本地图片路径列表
        """
        # 匹配 Markdown 图片语法 ![](path/to/image.jpg)
        pattern = r'!\[.*?\]\((.*?)\)'
        image_paths = re.findall(pattern, markdown_content)

        # 过滤掉已经是 HTTP 的链接
        local_images = []
        for path in image_paths:
            if not (path.startswith('http://') or path.startswith('https://') or path.startswith('data:')):
                # 处理相对路径
                if base_dir and not os.path.isabs(path):
                    full_path = os.path.join(base_dir, path)
                else:
                    full_path = path

                # 规范化路径
                full_path = os.path.normpath(full_path)
                if os.path.exists(full_path):
                    local_images.append(full_path)
                else:
                    logging.info(f"警告: 图片文件不存在: {full_path}")

        return local_images

    def replace_local_images_with_urls(
            self,
            markdown_content: str,
            image_mapping: Dict[str, str],
            base_dir: str = ""
    ) -> str:
        """
        将本地图片链接替换为 HTTP URL

        Args:
            markdown_content: 原始 Markdown 内容
            image_mapping: 本地路径到URL的映射
            base_dir: 基础目录路径

        Returns:
            处理后的 Markdown 内容
        """

        def replace_match(match):
            alt_text = match.group(1)  # alt文本
            local_path = match.group(2)  # 图片路径

            # 如果是HTTP链接或data URI，保持不变
            if (local_path.startswith('http://') or
                    local_path.startswith('https://') or
                    local_path.startswith('data:')):
                return match.group(0)

            # 处理相对路径
            if base_dir and not os.path.isabs(local_path):
                full_path = os.path.join(base_dir, local_path)
            else:
                full_path = local_path

            full_path = os.path.normpath(full_path)

            # 查找对应的URL
            if full_path in image_mapping and image_mapping[full_path]:
                return f"![{alt_text}]({image_mapping[full_path]})"
            else:
                logging.info(f"警告: 未找到图片 {full_path} 的URL映射")
                return match.group(0)

        # 使用正则表达式替换
        pattern = r'!\[(.*?)\]\((.*?)\)'
        return re.sub(pattern, replace_match, markdown_content)

    def process_markdown_file(
            self,
            input_file: str,
            output_file: Optional[str] = None,
            upload_images: bool = True
    ) -> Dict:
        """
        处理整个 Markdown 文件

        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径 (None则覆盖原文件)
            upload_images: 是否上传图片

        Returns:
            处理结果信息
        """
        base_dir = os.path.dirname(input_file)

        # 读取文件内容
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取本地图片路径
        local_images = self.extract_local_image_paths(content, base_dir)
        logging.info(f"找到 {len(local_images)} 个本地图片")

        # 上传图片并获取URL映射
        image_mapping = {}
        if upload_images and local_images:
            image_mapping = self.uploader.upload_multiple_images(local_images, base_dir)

        # 替换图片链接
        processed_content = self.replace_local_images_with_urls(content, image_mapping, base_dir)

        # 写入输出文件
        output_path = output_file or input_file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(processed_content)

        return {
            "processed_file": output_path,
            "images_uploaded": len([v for v in image_mapping.values() if v]),
            "image_mapping": image_mapping
        }

def mdfile_img_replace(mdfs,base_dir):
    with open(mdfs, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    result_content = markdown_content
    # 匹配 Markdown 图片语法 ![](path/to/image.jpg)
    pattern = r'!\[.*?\]\((.*?)\)'
    image_paths = re.findall(pattern, markdown_content)
    for path in image_paths:
        # 只替换本地路径
        if not (path.startswith('http://') or path.startswith('https://') or path.startswith('data:')):
            new_path =  f"{base_dir}/{path}".replace("\\", "/")
            new_path = re.sub(r'/+', '/', new_path)
            # 替换图片路径
            result_content = re.sub(r'!\[.*?\]\(' + re.escape(path) + r'\)',
                   f'![]({new_path})',
                   result_content)
            logging.info(f"replace {path} to {new_path}")
    # 覆盖文件
    with open(mdfs, 'w', encoding='utf-8') as f:
        f.write(result_content)
    return result_content

if __name__ == '__main__':
    file_path=r'D:\myproj\ragdemo\ser\temp\1\ocr\1.md'
    splitter = SmartMarkdownSplitter(512, 10)
    chunks = splitter.split_markdown_document(file_path)
    for index,chunk in enumerate(chunks):
        logging.info(index,"#"*20)
        logging.info(chunk.page_content)