from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="BAAI/bge-small-zh-v1.5",
    endpoint="https://hf-mirror.com",  # 显式指定正确地址
    local_dir="./bge-small-zh-v1.5"
)
snapshot_download(
    repo_id="Qwen/Qwen3-4B-Instruct-2507",
    endpoint="https://hf-mirror.com",  # 显式指定正确地址
    local_dir="./Qwen3-4B-Instruct-2507"
)


