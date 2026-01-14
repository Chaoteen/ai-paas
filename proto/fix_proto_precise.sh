#!/bin/bash

echo "🔧 开始精确修复proto文件..."

# 备份所有文件
echo "📦 备份原文件..."
for file in inference.proto langgraph.proto model.proto prompt.proto; do
    if [ -f "$file" ]; then
        cp "$file" "${file}.backup"
        echo "  ✅ 备份 $file"
    fi
done

echo "🔨 精确修复各文件..."

# 修复 inference.proto 第108行
sed -i '108s/rpc GetModelInfo(string) returns (ModelInfo);/rpc GetModelInfo(ai.os.envelope.StringValue) returns (ModelInfo);/' inference.proto

# 修复 langgraph.proto 第114行  
sed -i '114s/rpc GetAgentRoutingConfig(string) returns (AgentRoutingConfig);/rpc GetAgentRoutingConfig(ai.os.envelope.StringValue) returns (AgentRoutingConfig);/' langgraph.proto

# 修复 model.proto 第162行
sed -i '162s/rpc GetModelStatus(string) returns (ModelStatus);/rpc GetModelStatus(ai.os.envelope.StringValue) returns (ModelStatus);/' model.proto

# 修复 prompt.proto 第167行
sed -i '167s/rpc GetTemplateVersions(string) returns (stream PromptVersion);/rpc GetTemplateVersions(ai.os.envelope.StringValue) returns (stream PromptVersion);/' prompt.proto

echo "✅ 精确修复完成！"
