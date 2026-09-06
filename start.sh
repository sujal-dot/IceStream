#!/usr/bin/env bash
# ==============================================================================
# IceStream - Real-Time Lakehouse Observability & Self-Healing Data Pipeline
# ==============================================================================
# Production-grade Root Startup & Service Control Script
# Usage:
#   ./start.sh          Start infrastructure, pipeline, backend & frontend
#   ./start.sh --status  Check real-time status of all services without starting
#   ./start.sh --logs    Tail infrastructure logs from Docker Compose
#   ./start.sh --stop    Safely stop application and infrastructure (preserves data)
# ==============================================================================

set -Eeuo pipefail

# 1. Project Root Directory Resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

LOGS_DIR="${SCRIPT_DIR}/logs"
mkdir -p "${LOGS_DIR}"

BACKEND_PID_FILE="${SCRIPT_DIR}/.backend.pid"
FRONTEND_PID_FILE="${SCRIPT_DIR}/.frontend.pid"

# Colors for terminal formatting
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Error trap handler
trap_error() {
    local exit_code=$?
    local line_no=$1
    echo -e "\n${RED}[ERROR] Startup failed at line ${line_no} with exit code ${exit_code}.${NC}"
    echo -e "${YELLOW}Diagnostics:${NC}"
    echo -e "  Run 'docker compose ps' to check infrastructure."
    echo -e "  Run './start.sh --logs' to view container logs."
    echo -e "  Check backend log at '${LOGS_DIR}/backend.log'."
    echo -e "  Check frontend log at '${LOGS_DIR}/frontend.log'."
    exit "${exit_code}"
}
trap 'trap_error ${LINENO}' ERR

# Determine Python Executable
PYTHON_EXEC="python3"
if [ -f "${SCRIPT_DIR}/.venv/bin/python" ]; then
    PYTHON_EXEC="${SCRIPT_DIR}/.venv/bin/python"
fi

# ==============================================================================
# Helper Functions
# ==============================================================================

check_tool() {
    local cmd=$1
    local name=$2
    if ! command -v "${cmd}" &>/dev/null; then
        echo -e "${RED}[ERROR] Required dependency '${name}' (${cmd}) is not installed or not in PATH.${NC}" >&2
        return 1
    fi
    return 0
}

is_port_listening() {
    local port=$1
    if command -v lsof &>/dev/null; then
        lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1
    elif command -v nc &>/dev/null; then
        nc -z localhost "${port}" >/dev/null 2>&1
    else
        bash -c "echo > /dev/tcp/localhost/${port}" >/dev/null 2>&1
    fi
}

show_logs() {
    echo -e "${CYAN}Tailing Docker Compose infrastructure logs (Press Ctrl+C to exit)...${NC}\n"
    exec docker compose logs -f --tail=100
}

stop_services() {
    echo -e "========================================"
    echo -e "        STOPPING ICESTREAM"
    echo -e "========================================"
    echo ""

    # 1. Stop Frontend Process
    if [ -f "${FRONTEND_PID_FILE}" ]; then
        local fpid
        fpid=$(cat "${FRONTEND_PID_FILE}" 2>/dev/null || echo "")
        if [ -n "${fpid}" ] && kill -0 "${fpid}" 2>/dev/null; then
            echo -n "Stopping Frontend (PID ${fpid})... "
            kill "${fpid}" 2>/dev/null || true
            sleep 1
            echo -e "${GREEN}Stopped${NC}"
        fi
        rm -f "${FRONTEND_PID_FILE}"
    fi

    # Kill any leftover vite processes on 5173
    if is_port_listening 5173; then
        echo -n "Cleaning up port 5173 process... "
        pkill -f "vite" 2>/dev/null || true
        echo -e "${GREEN}Cleaned${NC}"
    fi

    # 2. Stop Backend Process
    if [ -f "${BACKEND_PID_FILE}" ]; then
        local bpid
        bpid=$(cat "${BACKEND_PID_FILE}" 2>/dev/null || echo "")
        if [ -n "${bpid}" ] && kill -0 "${bpid}" 2>/dev/null; then
            echo -n "Stopping Backend (PID ${bpid})... "
            kill "${bpid}" 2>/dev/null || true
            sleep 1
            echo -e "${GREEN}Stopped${NC}"
        fi
        rm -f "${BACKEND_PID_FILE}"
    fi

    # Kill any leftover uvicorn processes on 8000
    if is_port_listening 8000; then
        echo -n "Cleaning up port 8000 process... "
        pkill -f "uvicorn backend.app:app" 2>/dev/null || true
        echo -e "${GREEN}Cleaned${NC}"
    fi

    # 3. Stop Docker Containers safely without removing volumes
    echo "Stopping Docker Compose infrastructure containers..."
    docker compose stop

    echo ""
    echo -e "${GREEN}IceStream services stopped successfully. (All data & volumes preserved)${NC}"
    exit 0
}

show_status() {
    echo -e "========================================"
    echo -e "        ICESTREAM SERVICE STATUS"
    echo -e "========================================"
    echo ""

    printf "%-22s %-12s %s\n" "SERVICE" "STATUS" "ENDPOINT"
    echo "--------------------------------------------------------"

    # Infrastructure status checks
    check_service_status() {
        local name=$1
        local check_cmd=$2
        local endpoint=$3
        trap '' ERR
        set +e
        eval "${check_cmd}" >/dev/null 2>&1
        local res=$?
        set -e
        trap 'trap_error ${LINENO}' ERR
        if [ ${res} -eq 0 ]; then
            printf "%-22s ${GREEN}%-12s${NC} %s\n" "${name}" "HEALTHY" "${endpoint}"
        else
            printf "%-22s ${RED}%-12s${NC} %s\n" "${name}" "DOWN" "${endpoint}"
        fi
    }

    check_service_status "Kafka Broker" "docker exec icestream-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092" "localhost:9092"
    check_service_status "Flink JobManager" "curl -sf http://localhost:8081/v1/overview" "http://localhost:8081"
    check_service_status "MinIO S3" "curl -sf http://localhost:9000/minio/health/live" "http://localhost:9000 (Console: :9001)"
    check_service_status "Iceberg REST" "curl -sf http://localhost:8181/v1/config" "http://localhost:8181"
    check_service_status "PostgreSQL" "docker exec icestream-postgres pg_isready -U icestream_user -d icestream_db" "localhost:5432"
    check_service_status "Prometheus" "curl -sf http://localhost:9090/-/healthy" "http://localhost:9090"
    check_service_status "Grafana" "curl -sf http://localhost:3000/api/health" "http://localhost:3000"

    echo ""
    echo "Application:"
    check_service_status "FastAPI Backend" "curl -sf http://localhost:8000/health" "http://localhost:8000"
    check_service_status "React Frontend" "curl -sf http://localhost:5173" "http://localhost:5173"

    echo ""
    echo "Pipeline Jobs:"
    trap '' ERR
    set +e
    local active_job
    active_job=$(curl -s "http://localhost:8081/jobs/overview" 2>/dev/null | ${PYTHON_EXEC} -c "
import sys, json
try:
    data = json.load(sys.stdin)
    jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING' and ('checkout_events' in j.get('name', '') or 'icestream' in j.get('name', ''))]
    print(jobs[0]['name'] if jobs else '')
except Exception:
    print('')
" || echo "")
    set -e
    trap 'trap_error ${LINENO}' ERR

    if [ -n "${active_job}" ]; then
        printf "%-22s ${GREEN}%-12s${NC} %s\n" "Flink Streaming Job" "RUNNING" "${active_job}"
    else
        printf "%-22s ${YELLOW}%-12s${NC} %s\n" "Flink Streaming Job" "STOPPED" "None active"
    fi

    echo -e "\n========================================"
    exit 0
}

# Parse Command Line Options
if [ $# -gt 0 ]; then
    case "$1" in
        --status)
            show_status
            ;;
        --logs)
            show_logs
            ;;
        --stop)
            stop_services
            ;;
        --help|-h)
            echo "Usage: ./start.sh [--status | --logs | --stop]"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: ./start.sh [--status | --logs | --stop]"
            exit 1
            ;;
    esac
fi

# ==============================================================================
# MAIN STARTUP SEQUENCE
# ==============================================================================

echo -e "${CYAN}"
echo "========================================"
echo "        ICESTREAM PIPELINE STARTUP"
echo "========================================"
echo -e "${NC}"

# [1/7] Environment Check
echo -e "${BLUE}[1/7] Checking dependencies...${NC}"
MISSING_DEPS=0
check_tool "docker" "Docker" || MISSING_DEPS=1
check_tool "python3" "Python 3" || MISSING_DEPS=1
check_tool "node" "Node.js" || MISSING_DEPS=1
check_tool "npm" "npm" || MISSING_DEPS=1

if ! docker compose version &>/dev/null; then
    echo -e "${RED}[ERROR] 'docker compose' plugin is required.${NC}" >&2
    MISSING_DEPS=1
fi

if [ ${MISSING_DEPS} -ne 0 ]; then
    echo -e "${RED}[ERROR] Startup aborted due to missing dependencies.${NC}" >&2
    exit 1
fi
echo -e "${GREEN}✓ Dependencies verified.${NC}\n"

# [2/7] Environment File Check
echo -e "${BLUE}[2/7] Loading environment configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${RED}.env not found.${NC}"
        echo -e "${YELLOW}Please create .env from .env.example before starting IceStream:${NC}"
        echo -e "  cp .env.example .env"
        exit 1
    else
        echo -e "${RED}[ERROR] Neither .env nor .env.example found in project root.${NC}"
        exit 1
    fi
fi

set -a
source .env
set +a
echo -e "${GREEN}✓ Environment variables loaded from .env.${NC}\n"

# [3/7] Starting Infrastructure via Docker Compose
echo -e "${BLUE}[3/7] Starting infrastructure services (Docker Compose)...${NC}"
docker compose up -d
echo -e "${GREEN}✓ Containers launched.${NC}\n"

# [4/7] Waiting for Infrastructure Services Readiness
echo -e "${BLUE}[4/7] Waiting for infrastructure readiness...${NC}"

wait_for_condition() {
    local name=$1
    local check_cmd=$2
    local timeout_secs=${3:-60}
    local elapsed=0

    echo -n "  Waiting for ${name}... "
    trap '' ERR
    set +e
    while true; do
        eval "${check_cmd}" >/dev/null 2>&1
        local res=$?
        if [ ${res} -eq 0 ]; then
            set -e
            trap 'trap_error ${LINENO}' ERR
            echo -e "${GREEN}✓ Ready${NC}"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        if [ ${elapsed} -ge ${timeout_secs} ]; then
            set -e
            trap 'trap_error ${LINENO}' ERR
            echo -e "${RED}FAILED (timeout after ${timeout_secs}s)${NC}"
            return 1
        fi
    done
    set -e
    trap 'trap_error ${LINENO}' ERR
}

wait_for_condition "Kafka" "docker exec icestream-kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092" 45
wait_for_condition "MinIO Object Storage" "curl -sf http://localhost:9000/minio/health/live" 30
wait_for_condition "Iceberg REST Catalog" "curl -sf http://localhost:8181/v1/config" 30
wait_for_condition "PostgreSQL Database" "docker exec icestream-postgres pg_isready -U ${POSTGRES_USER:-icestream_user} -d ${POSTGRES_DB:-icestream_db}" 30
wait_for_condition "Flink JobManager" "curl -sf http://localhost:8081/v1/overview" 45
wait_for_condition "Prometheus" "curl -sf http://localhost:9090/-/healthy" 30
wait_for_condition "Grafana" "curl -sf http://localhost:3000/api/health" 30

echo -e "${GREEN}✓ All 7 infrastructure services are healthy.${NC}\n"

# [5/7] Initializing Storage, Catalog & Flink Pipeline
echo -e "${BLUE}[5/7] Initializing storage, catalog & Flink streaming pipeline...${NC}"

trap '' ERR
set +e
# 1. Topics
bash scripts/kafka/create_topics.sh >/dev/null 2>&1 || true

# 2. MinIO Buckets
bash scripts/minio/init_buckets.sh >/dev/null 2>&1 || true

# 3. Iceberg Catalog & Tables
PYTHONPATH="${SCRIPT_DIR}" ${PYTHON_EXEC} scripts/iceberg/init_catalog.py >/dev/null 2>&1 || true

# 4. Flink Streaming Job Check & Submission
ACTIVE_JOB_ID=$(curl -s "http://localhost:8081/jobs/overview" 2>/dev/null | ${PYTHON_EXEC} -c "
import sys, json
try:
    data = json.load(sys.stdin)
    jobs = [j for j in data.get('jobs', []) if j.get('state') == 'RUNNING' and ('checkout_events' in j.get('name', '') or 'icestream' in j.get('name', ''))]
    if jobs:
        print(jobs[0]['jid'])
except Exception:
    print('')
" || echo "")

if [ -z "${ACTIVE_JOB_ID}" ]; then
    echo "  Submitting Flink Bronze streaming pipeline job..."
    docker exec -i icestream-flink-jobmanager /opt/flink/bin/sql-client.sh < "${SCRIPT_DIR}/flink/jobs/kafka_to_iceberg.sql" >/dev/null 2>&1 || true
    sleep 3
fi
set -e
trap 'trap_error ${LINENO}' ERR

wait_for_condition "Flink Streaming Job" "curl -s http://localhost:8081/jobs/overview | grep -q 'RUNNING'" 30
echo -e "${GREEN}✓ Storage and streaming pipeline initialized.${NC}\n"

# [6/7] Starting Application Layer (FastAPI Backend & React Frontend)
echo -e "${BLUE}[6/7] Starting application services...${NC}"

# FastAPI Backend
trap '' ERR
set +e
BACKEND_RUNNING=0
if is_port_listening 8000 && curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    BACKEND_RUNNING=1
fi
set -e
trap 'trap_error ${LINENO}' ERR

if [ ${BACKEND_RUNNING} -eq 1 ]; then
    echo -e "  FastAPI Backend: ${GREEN}Already running on http://localhost:8000${NC}"
else
    echo "  Starting FastAPI Backend on http://localhost:8000..."
    PYTHONPATH="${SCRIPT_DIR}" nohup ${PYTHON_EXEC} -u -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 > "${LOGS_DIR}/backend.log" 2>&1 &
    echo $! > "${BACKEND_PID_FILE}"
    wait_for_condition "FastAPI Backend" "curl -sf http://localhost:8000/health" 30
fi

# React Frontend
trap '' ERR
set +e
FRONTEND_RUNNING=0
if is_port_listening 5173 && curl -sf http://localhost:5173 >/dev/null 2>&1; then
    FRONTEND_RUNNING=1
fi
set -e
trap 'trap_error ${LINENO}' ERR

if [ ${FRONTEND_RUNNING} -eq 1 ]; then
    echo -e "  React Frontend: ${GREEN}Already running on http://localhost:5173${NC}"
else
    echo "  Starting React Frontend on http://localhost:5173..."
    (cd "${SCRIPT_DIR}/frontend" && nohup npm run dev -- --port 5173 > "${LOGS_DIR}/frontend.log" 2>&1 & echo $! > "${FRONTEND_PID_FILE}")
    wait_for_condition "React Frontend" "curl -sf http://localhost:5173" 30
fi

echo -e "${GREEN}✓ Application services operational.${NC}\n"

# [7/7] Final System Verification
echo -e "${BLUE}[7/7] Running final system verification...${NC}"

HEALTH_STATUS=$(curl -s http://localhost:8000/health 2>/dev/null || echo "")

if [[ "${HEALTH_STATUS}" != *"\"status\":\"ok\""* ]]; then
    echo -e "${RED}[ERROR] Backend health check failed.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ System verification complete.${NC}\n"

# ==============================================================================
# READY SUMMARY
# ==============================================================================

echo -e "${CYAN}========================================"
echo "        ICESTREAM IS READY"
echo "========================================"
echo -e "${NC}"

echo -e "Infrastructure:"
echo -e "  Kafka Broker     ${GREEN}✓${NC} (localhost:9092)"
echo -e "  Flink JobManager ${GREEN}✓${NC} (http://localhost:8081)"
echo -e "  MinIO S3 Store   ${GREEN}✓${NC} (http://localhost:9000 | Console: :9001)"
echo -e "  Iceberg Catalog  ${GREEN}✓${NC} (http://localhost:8181)"
echo -e "  PostgreSQL DB    ${GREEN}✓${NC} (localhost:5432)"
echo -e "  Prometheus       ${GREEN}✓${NC} (http://localhost:9090)"
echo -e "  Grafana          ${GREEN}✓${NC} (http://localhost:3000)"

echo -e "\nApplication:"
echo -e "  Backend API      ${GREEN}✓${NC} http://localhost:8000"
echo -e "  React Dashboard  ${GREEN}✓${NC} http://localhost:5173"
echo -e "  Streaming Job    ${GREEN}✓${NC} RUNNING"

echo -e "\nUseful Endpoints:"
echo -e "  Dashboard UI:    http://localhost:5173"
echo -e "  API Docs:        http://localhost:8000/docs"
echo -e "  Grafana:         http://localhost:3000 (admin/admin)"
echo -e "  Flink Dashboard: http://localhost:8081"
echo -e "  MinIO Console:   http://localhost:9001 (icestream_minio/icestream_minio_secret)"

echo -e "\nEvent Generator (Run in separate terminal to simulate telemetry):"
echo -e "  ${YELLOW}PYTHONPATH=. .venv/bin/python generator/main.py --rate 1000 --error-rate 0.2 --metrics-port 8002${NC}"

echo -e "\nManagement Commands:"
echo -e "  Check status:    ./start.sh --status"
echo -e "  View logs:       ./start.sh --logs"
echo -e "  Stop system:     ./start.sh --stop"

echo -e "\n${CYAN}========================================${NC}\n"
