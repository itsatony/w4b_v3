#!/bin/bash
# /server/deployment/scripts/health-check.sh

set -e

# Configuration
TIMEOUT=5
LOG_FILE="/var/log/hive/health-check.log"
METRICS_FILE="/var/log/hive/health-metrics.json"
ALERT_THRESHOLD=3
STATUS_FILE="/var/run/hive/health-status"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging function
log() {
    local level=$1
    shift
    local message="[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*"
    echo -e "$message" >> "$LOG_FILE"
    echo -e "$message"
}

# Initialize directories
mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$STATUS_FILE")"

# Metric collection function
collect_metrics() {
    local service=$1
    local status=$2
    local duration=$3
    
    cat >> "$METRICS_FILE" << EOF
hive_health_check{service="${service}",status="${status}"} ${duration}
EOF
}

# Function to check HTTP endpoints
check_http() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    
    log "INFO" "Checking $name at $url"
    
    local start_time=$(date +%s%N)
    local response=$(curl -sL -w "%{http_code}" -o /dev/null --max-time $TIMEOUT --connect-timeout 2 "$url" 2>/dev/null || echo "FAILED")
    local end_time=$(date +%s%N)
    local duration=$(( (end_time - start_time) / 1000000 ))
    
    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN}✓${NC} $name is healthy (${duration}ms)"
        log "INFO" "$name health check passed in ${duration}ms"
        collect_metrics "$name" "healthy" "$duration"
        return 0
    else
        echo -e "${RED}✗${NC} $name is unhealthy (Response: $response)"
        log "ERROR" "$name health check failed with response $response"
        collect_metrics "$name" "unhealthy" "$duration"
        return 1
    fi
}

# Function to check system resources
check_system_resources() {
    log "INFO" "Checking system resources"
    
    # CPU Load
    local cpu_load=$(awk '{print $1}' /proc/loadavg)
    local cpu_cores=$(nproc)
    local cpu_threshold=$(echo "$cpu_cores * 0.8" | bc)
    
    if (( $(echo "$cpu_load > $cpu_threshold" | bc -l) )); then
        echo -e "${YELLOW}!${NC} High CPU load: $cpu_load"
        log "WARN" "High CPU load: $cpu_load"
        collect_metrics "cpu" "warning" "$cpu_load"
    else
        echo -e "${GREEN}✓${NC} CPU load normal: $cpu_load"
        log "INFO" "CPU load normal: $cpu_load"
        collect_metrics "cpu" "healthy" "$cpu_load"
    fi
    
    # Memory
    local mem_total=$(free | awk '/Mem:/ {print $2}')
    local mem_used=$(free | awk '/Mem:/ {print $3}')
    local mem_percent=$(echo "scale=2; $mem_used/$mem_total * 100" | bc)
    
    if (( $(echo "$mem_percent > 80" | bc -l) )); then
        echo -e "${YELLOW}!${NC} High memory usage: ${mem_percent}%"
        log "WARN" "High memory usage: ${mem_percent}%"
        collect_metrics "memory" "warning" "$mem_percent"
    else
        echo -e "${GREEN}✓${NC} Memory usage normal: ${mem_percent}%"
        log "INFO" "Memory usage normal: ${mem_percent}%"
        collect_metrics "memory" "healthy" "$mem_percent"
    fi
    
    # Disk Space
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$disk_usage" -gt 80 ]; then
        echo -e "${YELLOW}!${NC} High disk usage: ${disk_usage}%"
        log "WARN" "High disk usage: ${disk_usage}%"
        collect_metrics "disk" "warning" "$disk_usage"
    else
        echo -e "${GREEN}✓${NC} Disk usage normal: ${disk_usage}%"
        log "INFO" "Disk usage normal: ${disk_usage}%"
        collect_metrics "disk" "healthy" "$disk_usage"
    fi
}

# Service specific checks
check_services() {
    local failed=0
    
    # TimescaleDB - Using pg_isready instead of HTTP
    if pg_isready -h localhost -p 5432 -t 2 >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} TimescaleDB is healthy"
        log "INFO" "TimescaleDB health check passed"
    else
        echo -e "${RED}✗${NC} TimescaleDB is unhealthy"
        log "ERROR" "TimescaleDB health check failed"
        ((failed+=1))
    fi
    
    # Keycloak - Update to actual health endpoint
    if check_http "Keycloak" "http://localhost:8080/auth/realms/master" 200; then
        ((failed+=0))
    else
        ((failed+=1))
    fi
    
    # Grafana
    if check_http "Grafana" "http://localhost:3000/api/health" 200; then
        ((failed+=0))
    else
        ((failed+=1))
    fi
    
    # Prometheus
    if check_http "Prometheus" "http://localhost:9090/-/healthy" 200; then
        ((failed+=0))
    else
        ((failed+=1))
    fi
    
    # Alert Manager
    if check_http "AlertManager" "http://localhost:9093/-/healthy" 200; then
        ((failed+=0))
    else
        ((failed+=1))
    fi
    
    return $failed
}

# Check VPN connections
check_vpn() {
    log "INFO" "Checking VPN connections"
    
    local connections=$(wg show all endpoints | wc -l)
    log "INFO" "Found $connections active VPN connections"
    collect_metrics "vpn_connections" "info" "$connections"
    
    if [ "$connections" -eq 0 ]; then
        echo -e "${YELLOW}!${NC} No active VPN connections"
        log "WARN" "No active VPN connections"
        return 1
    else
        echo -e "${GREEN}✓${NC} $connections active VPN connections"
        return 0
    fi
}

# Write status file
write_status() {
    local status=$1
    echo "$status" > "$STATUS_FILE"
    chmod 644 "$STATUS_FILE"
}

# Main health check
main() {
    echo "Starting health checks at $(date)"
    log "INFO" "Starting health check run"
    
    local failed=0
    
    # Check system resources
    check_system_resources
    
    # Check services
    check_services
    failed=$((failed + $?))
    
    # Check VPN
    check_vpn
    failed=$((failed + $?))
    
    # Final status
    if [ $failed -eq 0 ]; then
        echo -e "\n${GREEN}All systems healthy${NC}"
        log "INFO" "Health check completed successfully"
        write_status "healthy"
        exit 0
    elif [ $failed -lt $ALERT_THRESHOLD ]; then
        echo -e "\n${YELLOW}Some systems degraded ($failed issues)${NC}"
        log "WARN" "Health check completed with $failed issues"
        write_status "degraded"
        exit 1
    else
        echo -e "\n${RED}System unhealthy ($failed issues)${NC}"
        log "ERROR" "Health check completed with $failed issues"
        write_status "unhealthy"
        exit 2
    fi
}

# Run main function
main "$@"