#!/bin/bash
# start_core_services.sh: 启动 Python 核心微服务 (修复版)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LOG_DIR="$PROJECT_ROOT/logs" # 注意：这里原代码可能是 $PROJECT_ROOT，请确认是否笔误，下面已修正为 $PROJECT_ROOT
LOG_DIR="$PROJECT_ROOT/logs"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

log_info() { echo -e "\033[1;36m[CORE-SVC]\033[0m $1"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; }

# 配置项
CONDA_ENV="qwen"

# 【预检查】获取 Conda 基础路径，避免在子 shell 中失败
CONDA_BASE=$(conda info --base 2>/dev/null)
if [[ -z "$CONDA_BASE" ]]; then
    log_error "❌ 无法找到 Conda 安装路径。请确保 Conda 已正确安装并初始化。"
    exit 1
fi
CONDA_INIT_SCRIPT="$CONDA_BASE/etc/profile.d/conda.sh"

case "${1:-start}" in
  start)
    log_info "正在启动核心服务..."

    # ---------------------------------------------------------
    # 1. 启动 AI-PaaS Gateway (FastAPI + Uvicorn)
    # ---------------------------------------------------------
    log_info "启动 API 网关 (Uvicorn on port 8000)..."
    
    # 检查是否已在运行
    if pgrep -f "uvicorn main:app" > /dev/null; then
      log_info "⚠️ 网关已在运行，跳过。"
    else
      # 【关键检查】确认 main.py 存在
      if [[ ! -f "$PROJECT_ROOT/main.py" ]]; then
          log_error "❌ 错误：在 $PROJECT_ROOT 下找不到 main.py 文件！"
          log_error "   当前脚本路径：$SCRIPT_DIR"
          log_error "   推算项目根目录：$PROJECT_ROOT"
          exit 1
      fi

      # 【关键修复】构建启动命令
      # 1. cd 到项目根目录
      # 2. 加载 conda 初始化脚本
      # 3. 激活环境
      # 4. 使用 'python -m uvicorn' 而不是 'uvicorn' (确保使用当前环境的 python)
      START_CMD="cd '$PROJECT_ROOT' && source '$CONDA_INIT_SCRIPT' && conda activate '$CONDA_ENV' && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

      # 后台启动，日志输出到文件
      nohup bash -c "$START_CMD" > "$LOG_DIR/gateway.log" 2>&1 &
      GATEWAY_PID=$!
      
      sleep 3 # 多等待一秒让进程初始化
      
      # 检查进程是否存活
      if ps -p $GATEWAY_PID > /dev/null; then
        log_info "✅ API 网关启动成功 (PID: $GATEWAY_PID)"
        # 二次确认端口监听
        if ! ss -tulpn | grep -q ":8000 "; then
            log_error "⚠️ 警告：进程在运行但端口 8000 未被监听。请检查日志："
            tail -n 20 "$LOG_DIR/gateway.log"
        fi
      else
        log_error "❌ API 网关启动失败！进程已意外退出。"
        log_error "📄 最后 20 行错误日志:"
        tail -n 20 "$LOG_DIR/gateway.log"
        exit 1
      fi
    fi

    # ---------------------------------------------------------
    # 2. 启动 Agent System (异步任务处理器)
    # ---------------------------------------------------------
    AGENT_SCRIPT="$PROJECT_ROOT/services/server/start_agent_system.py"
    if [[ -f "$AGENT_SCRIPT" ]]; then
      log_info "启动 Agent 系统 (异步任务)..."
      if pgrep -f "start_agent_system.py" > /dev/null; then
        log_info "⚠️ Agent 系统已在运行，跳过。"
      else
        # 构建 Agent 启动命令
        AGENT_CMD="cd '$PROJECT_ROOT' && source '$CONDA_INIT_SCRIPT' && conda activate '$CONDA_ENV' && python '$AGENT_SCRIPT'"
        
        nohup bash -c "$AGENT_CMD" > "$LOG_DIR/agent_system.log" 2>&1 &
        AGENT_PID=$!
        
        sleep 2
        if ps -p $AGENT_PID > /dev/null; then
          log_info "✅ Agent 系统启动成功 (PID: $AGENT_PID)"
        else
          log_error "⚠️ Agent 系统启动失败 (非致命，对话功能可用)。"
          log_error "📄 错误日志:"
          tail -n 10 "$LOG_DIR/agent_system.log"
        fi
      fi
    else
      log_info "⚠️ 未找到 Agent 系统脚本 ($AGENT_SCRIPT)，跳过。"
    fi

    log_info "核心服务启动完毕。"
    ;;

  stop)
    log_info "正在停止核心服务..."
    
    # 停止 Uvicorn
    if pgrep -f "uvicorn main:app" > /dev/null; then
        pkill -f "uvicorn main:app"
        log_info "⏹️ API 网关已停止"
    else
        log_info "⚠️ API 网关未运行"
    fi

    # 停止 Agent System
    if pgrep -f "start_agent_system.py" > /dev/null; then
        pkill -f "start_agent_system.py"
        log_info "⏹️ Agent 系统已停止"
    else
        log_info "⚠️ Agent 系统未运行"
    fi
    
    log_info "核心服务已停止。"
    ;;

  *)
    echo "用法: $0 {start|stop}"
    exit 1
    ;;
esac