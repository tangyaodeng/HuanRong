from modelscope.hub.file_download import model_file_download

model_path = model_file_download(
    model_id='Qwen/Qwen2.5-7B-Instruct-GGUF',
    file_path='qwen2.5-7b-instruct-q4_k_m.gguf',
    cache_dir='D:\py-learn\HuanRong\models'  # 你自己的存放路径
)
print(f"模型已下载到: {model_path}")