from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "./Qwen3-4B-Instruct-2507"

# 加载预训练模型的分词器
tokenizer = AutoTokenizer.from_pretrained(model_name)
# Hugging Face提供的自回归语言模型类，适用于文本生成任务
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto", # 自动选择最适合的张量数据类型 （如float16、bfloat16等），以节省内存并提高性能
    device_map="auto" # 自动将模型分配到可用设备
)

# prepare the model input

messages = [
    {"role": "user", "content": '请简要介绍一下大型语言模型'}
]
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False, # 不进行分词，返回处理后的文本字符串而不是token ID
    add_generation_prompt=True, # 添加生成提示，通常是模型用来标识回复开始的特殊标记
)
# 对文本进行分词编码  返回PyTorch张量格式    将数据移动到模型所在的设备（CPU或GPU）
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

# 解包模型输入参数 多生成16384个新token
generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=16384
)

# 获取第一个（也是唯一一个）生成序列 从输入长度之后开始切片，只保留新生成的部分 转换为Python列表
output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()

# 传入生成的token ID列表 跳过特殊token(如EOS结束符等)
content = tokenizer.decode(output_ids, skip_special_tokens=True)

print("content:", content)
