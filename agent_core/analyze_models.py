import subprocess
import json
import re

# 获取模型列表
result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行

deepseek_models = []
for line in lines:
    if 'deepseek' in line.lower():
        parts = re.split(r'\s+', line.strip())
        if len(parts) >= 4:
            model_info = {
                'name': parts[0],
                'tag': parts[1] if ':' in parts[1] else 'latest',
                'digest': parts[2],
                'size': parts[3],
                'created': ' '.join(parts[4:]) if len(parts) > 4 else 'unknown'
            }
            deepseek_models.append(model_info)

print("找到的DeepSeek模型:")
for i, model in enumerate(deepseek_models, 1):
    print(f"{i}. {model['name']}:{model['tag']}")
    print(f"   Digest: {model['digest']}")
    print(f"   大小: {model['size']}")
    print(f"   创建时间: {model['created']}")
    print()

# 按digest分组
digest_groups = {}
for model in deepseek_models:
    if model['digest'] not in digest_groups:
        digest_groups[model['digest']] = []
    digest_groups[model['digest']].append(model)

print("按Digest分组的模型:")
for digest, models in digest_groups.items():
    print(f"Digest: {digest}")
    for model in models:
        print(f"  - {model['name']}:{model['tag']}")
    print()
