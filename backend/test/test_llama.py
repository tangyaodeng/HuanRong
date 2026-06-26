from llama_cpp import Llama

# 1. 加载模型
# 将路径替换为你之前下载的GGUF文件路径
model_path = r"D:\py-learn\HuanRong\models\Qwen\Qwen2___5-7B-Instruct-GGUF\qwen2.5-7b-instruct-q4_k_m.gguf"

llm = Llama(
    model_path=model_path,
    n_ctx=2048,         # 上下文长度，可根据需要调整
    n_gpu_layers=-1,    # -1 表示将所有层加载到GPU，充分利用你的6GB显存
    verbose=False       # 不输出详细日志
)

# 2. 测试对话
messages = [
    {"role": "system", "content": "你是一个工业上位机助手，回答需简洁准确。"},
    {"role": "user", "content": "请用一句话解释什么是Modbus协议。"}
]

# 3. 获取并打印模型回复
response = llm.create_chat_completion(messages=messages, max_tokens=512)
print(response['choices'][0]['message']['content'])