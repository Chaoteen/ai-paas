#!/bin/bash

echo "🔧 修复proto文件步骤2..."

# 首先在envelope.proto中添加缺失的类型
echo "📝 在envelope.proto中添加缺失类型..."
cat >> envelope.proto << 'ENVELOPE_EOF'

// ========== 缺失类型定义 ==========

// Token使用情况
message TokenUsage {
  int32 prompt_tokens = 1;
  int32 completion_tokens = 2;
  int32 total_tokens = 3;
  double estimated_cost = 4;
}

// 记忆项
message MemoryItem {
  string id = 1;
  string session_id = 2;
  string content = 3;
  string type = 4;
  string timestamp = 5;
  double relevance_score = 6;
  map<string, string> metadata = 7;
}

// 检索文档
message RetrievedDocument {
  string id = 1;
  string content = 2;
  string source = 3;
  double similarity_score = 4;
  map<string, string> metadata = 5;
  repeated string keywords = 6;
}
ENVELOPE_EOF

echo "✅ 已添加缺失类型到envelope.proto"
