#!/bin/bash
# test_db_start.sh: 独立测试 PostgreSQL 启动与连接逻辑

set -euo pipefail

LOG_PREFIX="[DB-TEST]"
DB_USER="postgres"
DB_PASS="postgres"
DB_NAME="ai_paas"
DB_HOST="localhost"
DB_PORT="5432"

log_info() { echo -e "\033[0;32m$LOG_PREFIX\033[0m $1"; }
log_warn() { echo -e "\033[1;33m$LOG_PREFIX\033[0m $1"; }
log_error() { echo -e "\033[0;31m$LOG_PREFIX\033[0m $1"; }

echo "=== 开始测试 PostgreSQL 启动逻辑 ==="

# 步骤 1: 检查 Docker 容器
log_info "1. 检查 Docker 容器..."
docker_container=$(docker ps -a --format '{{.Names}}' | grep -i postgres | head -n 1)
if [[ -n "$docker_container" ]]; then
  log_info "   发现 Docker 容器: $docker_container"
  if docker ps --format '{{.Names}}' | grep -q "^${docker_container}$"; then
    log_info "   状态: 运行中"
  else
    log_info "   状态: 已停止，尝试启动..."
    docker start "$docker_container"
    sleep 3
  fi
else
  log_info "   未发现 Docker 容器，跳过 Docker 逻辑。"
fi

# 步骤 2: 直接测试连接 (核心逻辑)
log_info "2. 测试数据库连接 (用户:$DB_USER, 库:$DB_NAME)..."

# 构造 psql 命令
PSQL_CMD="PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c 'SELECT 1'"

# 执行测试 (带 5 秒超时)
if timeout 5 bash -c "$PSQL_CMD" >/dev/null 2>&1; then
  log_info "✅ 连接成功！数据库已就绪。"
  # 额外显示表数量
  TABLE_COUNT=$(PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d $DB_NAME -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
  log_info "   公共 Schema 下表数量: $TABLE_COUNT"
  exit 0
else
  log_warn "⚠️ 直接连接失败。尝试启动原生服务..."
  
  # 步骤 3: 尝试启动原生服务
  log_info "3. 尝试启动原生 PostgreSQL 服务..."
  if sudo service postgresql start 2>/dev/null; then
    log_info "   服务启动命令执行成功。"
  elif sudo pg_ctlcluster 15 main start 2>/dev/null; then
    log_info "   pg_ctlcluster 启动成功。"
  else
    log_warn "   自动启动命令失败，可能需要手动干预。"
  fi
  
  sleep 3
  
  # 再次测试
  log_info "4. 再次测试连接..."
  if timeout 5 bash -c "$PSQL_CMD" >/dev/null 2>&1; then
    log_info "✅ 启动后连接成功！"
    exit 0
  else
    log_error "❌ 最终连接失败。请手动检查:"
    echo "   1. service postgresql status"
    echo "   2. sudo tail -n 20 /var/log/postgresql/*.log"
    echo "   3. netstat -tlnp | grep 5432"
    exit 1
  fi
fi
