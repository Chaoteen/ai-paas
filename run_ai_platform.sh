#!/bin/bash

# AI PaaS平台服务管理脚本 - 正确路径版

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

REDIS_PID="$PID_DIR/redis.pid"
LANGGRAPH_PID="$PID_DIR/langgraph.pid"
ROUTER_BRIDGE_PID="$PID_DIR/router_bridge.pid"
AGENT_SYSTEM_PID="$PID_DIR/agent_system.pid"

start_redis() {
    echo "🚀 启动Redis消息总线..."
    cd "$SCRIPT_DIR/agent_core"
    
    # 检查是否已运行
    if pgrep -f "run_bus.py" > /dev/null; then
        echo "✅ Redis消息总线已在运行"
        return 0
    fi
    
    # 直接运行并捕获PID
    python run_bus.py > "$LOG_DIR/redis_bus.log" 2>&1 &
    local pid=$!
    echo $pid > "$REDIS_PID"
    
    # 等待并检查
    sleep 3
    if ps -p $pid > /dev/null; then
        echo "✅ Redis消息总线启动成功 (PID: $pid)"
        return 0
    else
        echo "❌ Redis消息总线启动失败，查看日志: tail -f $LOG_DIR/redis_bus.log"
        return 1
    fi
}

start_langgraph() {
    echo "🚀 启动LangGraph服务..."
    cd "$SCRIPT_DIR"
    
    # 检查是否已运行
    if pgrep -f "langgraph_grpc_server.py" > /dev/null; then
        echo "✅ LangGraph服务已在运行"
        return 0
    fi
    
    python langgraph/langgraph_grpc_server.py > "$LOG_DIR/langgraph.log" 2>&1 &
    local pid=$!
    echo $pid > "$LANGGRAPH_PID"
    
    sleep 5  # LangGraph需要更多时间启动
    if ps -p $pid > /dev/null; then
        echo "✅ LangGraph服务启动成功 (PID: $pid)"
        return 0
    else
        echo "❌ LangGraph服务启动失败，查看日志: tail -f $LOG_DIR/langgraph.log"
        return 1
    fi
}

start_router_bridge() {
    echo "🚀 启动RouterBridge..."
    cd "$SCRIPT_DIR/agent_core"
    
    if pgrep -f "router_bridge.py" > /dev/null; then
        echo "✅ RouterBridge已在运行"
        return 0
    fi
    
    python router_bridge.py > "$LOG_DIR/router_bridge.log" 2>&1 &
    local pid=$!
    echo $pid > "$ROUTER_BRIDGE_PID"
    
    sleep 3
    if ps -p $pid > /dev/null; then
        echo "✅ RouterBridge启动成功 (PID: $pid)"
        return 0
    else
        echo "❌ RouterBridge启动失败,查看日志: tail -f $LOG_DIR/router_bridge.log"
        return 1
    fi
}

start_agent_system() {
    echo "🚀 启动Agent系统..."
    cd "$SCRIPT_DIR/server"
    
    if pgrep -f "start_agent_system.py" > /dev/null; then
        echo "✅ Agent系统已在运行"
        return 0
    fi
    
    python start_agent_system.py > "$LOG_DIR/agent_system.log" 2>&1 &
    local pid=$!
    echo $pid > "$AGENT_SYSTEM_PID"
    
    sleep 3
    if ps -p $pid > /dev/null; then
        echo "✅ Agent系统启动成功 (PID: $pid)"
        return 0
    else
        echo "❌ Agent系统启动失败,查看日志: tail -f $LOG_DIR/agent_system.log"
        return 1
    fi
}

stop_service() {
    local service_name=$1
    local pid_file=$2
    local process_pattern=$3
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "🛑 停止 $service_name (PID: $pid)..."
            kill "$pid"
            sleep 2
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid"
            fi
            rm -f "$pid_file"
            echo "✅ $service_name 已停止"
        else
            echo "⚠️ $service_name 未运行"
            rm -f "$pid_file"
        fi
    else
        # 如果没有PID文件，但进程在运行，也尝试停止
        if pgrep -f "$process_pattern" > /dev/null; then
            echo "🛑 停止 $service_name (无PID文件)..."
            pkill -f "$process_pattern"
            sleep 2
            pkill -9 -f "$process_pattern" 2>/dev/null || true
            echo "✅ $service_name 已停止"
        else
            echo "⚠️ $service_name 未运行"
        fi
    fi
}

status_service() {
    local service_name=$1
    local process_pattern=$2
    
    if pgrep -f "$process_pattern" > /dev/null; then
        local pid=$(pgrep -f "$process_pattern")
        echo "✅ $service_name 正在运行 (PID: $pid)"
    else
        echo "❌ $service_name 未运行"
    fi
}

start_all() {
    echo "🎯 启动AI PaaS平台所有服务..."
    
    # 先检查Redis消息总线
    echo "=== 1. Redis消息总线 ==="
    if ! start_redis; then
        echo "❌ Redis消息总线启动失败，无法继续"
        return 1
    fi
    
    echo "=== 2. LangGraph服务 ==="
    if ! start_langgraph; then
        echo "⚠️ LangGraph服务启动失败，但继续其他服务"
    fi
    
    echo "=== 3. RouterBridge ==="
    if ! start_router_bridge; then
        echo "⚠️ RouterBridge启动失败，但继续其他服务"
    fi
    
    echo "=== 4. Agent系统 ==="
    if ! start_agent_system; then
        echo "⚠️ Agent系统启动失败"
    fi
    
    echo ""
    echo "🎉 启动流程完成!"
    echo ""
    echo "📊 当前服务状态:"
    status_service "Redis消息总线" "run_bus.py"
    status_service "LangGraph服务" "langgraph_grpc_server.py"
    status_service "RouterBridge" "router_bridge.py"
    status_service "Agent系统" "start_agent_system.py"
    echo ""
    echo "🔧 管理命令:"
    echo "  查看状态: $0 status"
    echo "  停止服务: $0 stop"
    echo "  运行测试: $0 test"
}

stop_all() {
    echo "🛑 停止AI PaaS平台所有服务..."
    
    stop_service "Agent系统" "$AGENT_SYSTEM_PID" "start_agent_system.py"
    stop_service "RouterBridge" "$ROUTER_BRIDGE_PID" "router_bridge.py"
    stop_service "LangGraph服务" "$LANGGRAPH_PID" "langgraph_grpc_server.py"
    stop_service "Redis消息总线" "$REDIS_PID" "run_bus.py"
    
    echo "✅ 所有服务已停止"
}

status_all() {
    echo "📊 AI PaaS平台服务状态:"
    status_service "Redis消息总线" "run_bus.py"
    status_service "LangGraph服务" "langgraph_grpc_server.py"
    status_service "RouterBridge" "router_bridge.py"
    status_service "Agent系统" "start_agent_system.py"
}

run_test() {
    echo "🧪 运行集成测试..."
    
    # 检查必要服务是否运行
    if ! pgrep -f "run_bus.py" > /dev/null; then
        echo "❌ Redis消息总线未运行，请先启动服务"
        return 1
    fi
    
    if ! pgrep -f "router_bridge.py" > /dev/null; then
        echo "❌ RouterBridge未运行，请先启动服务"
        return 1
    fi
    
    cd "$SCRIPT_DIR"
    python -c "
import redis
import json
import time
import uuid

print('发送测试任务到AI平台...')
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

test_tasks = [
    {
        'task_id': 'test-analysis-' + uuid.uuid4().hex[:8],
        'content': '请分析市场数据并生成报告',
        'task_type': 'analysis',
        'model': '',
        'timestamp': time.time()
    },
    {
        'task_id': 'test-summary-' + uuid.uuid4().hex[:8], 
        'content': '总结这篇文档的主要内容',
        'task_type': 'summary',
        'model': '',
        'timestamp': time.time()
    }
]

for test_task in test_tasks:
    envelope = {
        'data': test_task,
        'timestamp': time.time(),
        'message_id': str(uuid.uuid4())
    }
    
    r.xadd('agent.tasks.stream', {'message': json.dumps(envelope)})
    print('✅ 发送: ' + test_task['task_id'] + ' - ' + test_task['content'])

print('')
print('📨 测试任务已发送到 agent.tasks.stream')
print('🔍 查看路由结果: tail -f logs/router_bridge.log')
print('   成功标志: 🎯 LangGraph路由决策 → agent.xxx')
"
}

case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        stop_all
        sleep 2
        start_all
        ;;
    status)
        status_all
        ;;
    test)
        run_test
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|test}"
        echo ""
        echo "命令说明:"
        echo "  start    - 启动所有服务"
        echo "  stop     - 停止所有服务" 
        echo "  restart  - 重启所有服务"
        echo "  status   - 查看服务状态"
        echo "  test     - 运行集成测试"
        exit 1
esac
