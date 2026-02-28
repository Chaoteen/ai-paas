#!/bin/bash
# run_ai_platform_v4.sh: 全栈总控脚本 (模块化架构 - 已修复版)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info() { echo -e "\033[1;32m[MASTER]\033[0m $1"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

# 检查子脚本是否存在
check_scripts() {
  local scripts=("start_infra.sh" "start_containers.sh" "start_core_services.sh" "start_frontend.sh")
  for script in "${scripts[@]}"; do
    if [[ ! -f "$SCRIPT_DIR/$script" ]]; then
      log_error "缺少子脚本: $script"
      exit 1
    fi
    chmod +x "$SCRIPT_DIR/$script"
  done
}

case "${1:-start}" in
  start)
    log_info "🚀 开始启动 AI PaaS V4 (模块化)..."
    check_scripts
    
    log_info "[1/4] 启动基础设施 (Ollama, Redis, OPA)..."
    "$SCRIPT_DIR/start_infra.sh" start
    
    log_info "[2/4] 启动容器应用 (DB, PromptFlow, Flowise)..."
    "$SCRIPT_DIR/start_containers.sh" start
    
    log_info "[3/4] 启动核心服务 (Python Microservices)..."
    "$SCRIPT_DIR/start_core_services.sh" start
    
    log_info "[4/4] 检查前端..."
    "$SCRIPT_DIR/start_frontend.sh" start
    
    log_info "🎉 全栈启动完成!"
    log_info "📊 访问 Flowise: http://localhost:3000 (或您的 WSL IP)"
    log_info "📚 API 文档: http://localhost:8000/docs"
    log_info "💡 运行 './run_ai_platform_v4.sh status' 查看状态"
    ;;
    
  stop)
    log_info "🛑 开始停止所有服务..."
    check_scripts || true
    
    "$SCRIPT_DIR/start_frontend.sh" stop || true
    "$SCRIPT_DIR/start_core_services.sh" stop || true
    "$SCRIPT_DIR/start_containers.sh" stop || true
    "$SCRIPT_DIR/start_infra.sh" stop || true
    
    log_info "✅ 所有服务已停止"
    ;;
    
  restart)
    log_info "🔄 重启所有服务..."
    "$0" stop
    sleep 3
    "$0" start
    ;;
    
  status)
    echo "=== 📊 AI PaaS V4 状态 ==="
    
    echo "--- 基础设施 ---"
    if pgrep -f "ollama serve" > /dev/null; then echo "✅ Ollama"; else echo "❌ Ollama"; fi
    docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "redis|opa" || echo "⚠️ Redis/OPA 容器未运行"
    
    echo "--- 容器应用 ---"
    # 检查关键容器
    docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null | grep -E "postgres|promptflow|flowise" || echo "⚠️ 应用容器未运行"
    
    echo "--- 核心服务 (Python) ---"
    # 【关键修复】检测正确的进程名
    if pgrep -f "uvicorn main:app" > /dev/null; then 
      PID=$(pgrep -f "uvicorn main:app")
      echo "✅ API Gateway (Port 8000) [PID: $PID]"
    else 
      echo "❌ API Gateway (Port 8000)"; 
    fi
    
    if pgrep -f "start_agent_system.py" > /dev/null; then 
      echo "✅ AgentSystem (Async Worker)"
    else 
      echo "❌ AgentSystem (Async Worker)"; 
    fi
    
    # 可选：检查其他微服务如果存在
    # if pgrep -f "run_bus.py" > /dev/null; then echo "✅ RedisBus"; else echo "❌ RedisBus"; fi
    ;;
    
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac