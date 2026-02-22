#!/bin/bash
# AI-PaaS 测试运行脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  AI-PaaS Test Suite Runner    ${NC}"
echo -e "${GREEN}================================${NC}"

# 检查 Python 环境
if ! command -v python &> /dev/null; then
    echo -e "${RED}Error: Python not found${NC}"
    exit 1
fi

# 激活虚拟环境（如果存在）
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif command -v conda &> /dev/null && [ -d "$CONDA_PREFIX" ]; then
    echo -e "${YELLOW}Using conda environment${NC}"
fi

# 安装测试依赖
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -r requirements-test.txt -q

# 检查数据库连接
echo -e "${YELLOW}Checking database connection...${NC}"
if ! psql -h localhost -U postgres -d ai_paas_test -c "SELECT 1" &> /dev/null; then
    echo -e "${RED}Error: Cannot connect to test database${NC}"
    echo "Please ensure PostgreSQL is running and ai_paas_test database exists"
    exit 1
fi

# 运行 Alembic 迁移
echo -e "${YELLOW}Running database migrations...${NC}"
alembic upgrade head

# 运行测试
TEST_TYPE=${1:-all}

case $TEST_TYPE in
    unit)
        echo -e "${GREEN}Running unit tests...${NC}"
        pytest tests/unit/ -v --cov=models --cov-report=html
        ;;
    integration)
        echo -e "${GREEN}Running integration tests...${NC}"
        pytest tests/integration/ -v --cov=models --cov-report=html
        ;;
    abac)
        echo -e "${GREEN}Running ABAC tests...${NC}"
        pytest tests/ -v -m abac --cov=models.abac --cov-report=html
        ;;
    all)
        echo -e "${GREEN}Running all tests...${NC}"
        pytest tests/ -v --cov=models --cov-report=html --cov-report=term-missing
        ;;
    *)
        echo -e "${RED}Unknown test type: $TEST_TYPE${NC}"
        echo "Usage: ./run_tests.sh [unit|integration|abac|all]"
        exit 1
        ;;
esac

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  Tests completed successfully!${NC}"
echo -e "${GREEN}================================${NC}"