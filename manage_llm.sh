#!/bin/bash

case "$1" in
    start)
        echo "🚀 启动Ollama服务..."
        ollama serve &
        echo $! > ollama.pid
        sleep 5
        echo "📥 检查DeepSeek-R1模型..."
        ollama list | grep deepseek-r1 || {
            echo "正在拉取DeepSeek-R1模型..."
            ollama pull deepseek-r1:latest
        }
        ;;
    stop)
        echo "🛑 停止Ollama服务..."
        pkill -f "ollama"
        rm -f ollama.pid
        ;;
    status)
        if pgrep -f "ollama" > /dev/null; then
            echo "✅ Ollama服务运行中"
            ollama list
        else
            echo "❌ Ollama服务未运行"
        fi
        ;;
    *)
        echo "用法: $0 {start|stop|status}"
        ;;
esac