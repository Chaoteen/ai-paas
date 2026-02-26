#!/bin/bash
# 测试原生 PostgreSQL (跳过 Docker)
set -euo pipefail

DB_USER="postgres"
DB_PASS="postgres"
DB_NAME="ai_paas"
DB_HOST="localhost"
DB_PORT="5432"
log_info() { echo -e "\033[0;32m[DB-NATIVE]\033[0m $1"; }
log_warn() { echo -e "\033[1;33m[DB-NATIVE]\033[0m $1"; }
log_error() { echo -e "\033[0;31m[DB-NATIVE]\033[0m $1"; }

echo "=== 测试原生 PostgreSQL 连接 ==="

# 1. 检查端口 (使用 Bash 内置 TCP 功能，不依赖 nc)
log_info "1. 检查端口 $DB_PORT..."
if (echo >/dev/tcp/$DB_HOST/$DB_PORT) 2>/dev/null; then
    log_info "   ✅ 端口已开放"
else
    log_warn "   ⚠️ 端口未开放，尝试启动服务..."
    sudo service postgresql start 2>/dev/null || true
    sleep 3
    if ! (echo >/dev/tcp/$DB_HOST/$DB_PORT) 2>/dev/null; then
        log_error "   ❌ 启动失败，端口仍不可达"
        exit 1
    fi
fi

# 2. 测试连接
log_info "2. 测试数据库连接..."
CMD="PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'SELECT 1'"

if timeout 5 bash -c "$CMD" >/dev/null 2>&1; then
    log_info "✅ 连接成功！"
    COUNT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
    log_info "   表数量: $COUNT"
else
    log_error "❌ 连接失败"
    exit 1
fi
