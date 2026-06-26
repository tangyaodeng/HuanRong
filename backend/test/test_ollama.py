import ollama

# 测试与 Ollama 的连接及基本问答
response = ollama.chat(
    model='qwen3:4b',
    messages=[{'role': 'user', 'content': '制冷原理'}]
)

print("✅ Ollama 调用成功！")
print("回复内容：", response['message']['content'])