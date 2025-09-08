# Copyright (c) Opendatalab. All rights reserved.
import copy
import json
import os
from pathlib import Path

from loguru import logger

from mineru.cli.common import convert_pdf_bytes_to_bytes_by_pypdfium2, prepare_env, read_fn
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.utils.enum_class import MakeMode
from mineru.backend.pipeline.pipeline_analyze import doc_analyze as pipeline_doc_analyze
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import union_make as pipeline_union_make
from mineru.backend.pipeline.model_json_to_middle_json import result_to_middle_json as pipeline_result_to_middle_json


PROJECT_BASE = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                os.pardir
            )
)

os.environ['MINERU_MODEL_SOURCE'] = "modelscope"
os.environ['MODELSCOPE_CACHE'] =   os.path.join(PROJECT_BASE, 'modelscope')

output_dir = os.path.join(PROJECT_BASE, 'temp')

def do_parse(
        pdf_file_name:str,
        pdf_bytes:bytes,
        parse_method='ocr'
):
    pdf_file_name = str(Path(pdf_file_name).stem)

    # 预处理 PDF 字节
    new_pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(pdf_bytes, 0, None)
    # 调用 pipeline 模式进行文档分析
    infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = pipeline_doc_analyze([new_pdf_bytes],
                                                                                                 ['ch'],
                                                                                                 parse_method=parse_method,
                                                                                                 formula_enable=True,
                                                                                                 table_enable=True)
    # 遍历每个解析结果
    for idx, model_list in enumerate(infer_results):
        # 保存原始模型输出
        model_json = copy.deepcopy(model_list)
        # logging.info(model_json)
        # 准备输出环境（创建目录等）
        local_image_dir, local_md_dir = prepare_env(output_dir, pdf_file_name, parse_method)
        # 创建文件写入器
        image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(local_md_dir)
        # 获取相关数据
        images_list = all_image_lists[idx]
        pdf_doc = all_pdf_docs[idx]
        _lang = lang_list[idx]
        _ocr_enable = ocr_enabled_list[idx]
        middle_json = pipeline_result_to_middle_json(model_list, images_list, pdf_doc, image_writer, _lang, _ocr_enable,True)
        pdf_info = middle_json["pdf_info"]
        image_dir = str(os.path.basename(local_image_dir))
        md_content_str = pipeline_union_make(pdf_info, MakeMode.MM_MD, image_dir)

        md_writer.write_string(f"{pdf_file_name}.md",md_content_str)
        md_file_path = os.path.join(local_md_dir, f"{pdf_file_name}.md")
        return md_file_path,local_image_dir,image_dir







if __name__ == '__main__':

    pdf = '1.pdf'
    do_parse(pdf, read_fn(pdf))

