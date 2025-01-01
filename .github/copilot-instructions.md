
## general overview

Our project is w4b_v3, a bee-hive Monitoring System. It's a comprehensive solution for managing and monitoring distributed sensor networks, specifically designed for beehive monitoring but adaptable to various IoT scenarios.
The system follows a hub-and-spoke architecture with secure VPN connections and implements a multi-layered security approach.

## Server Architecture

we are on ubuntu 22.04

```mermaid
graph TB
    subgraph "External Services"
        SMTP[Google Workspace SMTP]
        GDRIVE[Google Drive Backup]
    end

    subgraph "Reverse Proxy Layer"
        NGINX[NGINX]
    end

    subgraph "Application Layer"
        API[Go API Service]
        KEYCLOAK[Keycloak]
    end

    subgraph "Data Layer"
        TSDB[(TimescaleDB)]
        PGAPP[(PostgreSQL App DB)]
        PGKEY[(PostgreSQL Keycloak)]
        REDIS[(Redis)]
    end

    subgraph "Monitoring"
        PROM[Prometheus]
        GRAF[Grafana]
        ALERT[Alert Manager]
        NODE[Node Exporter]
        BLACK[Blackbox Exporter]
    end

    subgraph "Edge Devices"
        WG[WireGuard VPN]
        SPOKE1[Spoke 1]
        SPOKE2[Spoke 2]
        SPOKE3[Spoke 3]
    end

    NGINX --> API
    NGINX --> KEYCLOAK
    NGINX --> GRAF

    API --> TSDB
    API --> PGAPP
    API --> REDIS
    API --> WG
    API --> PROM

    KEYCLOAK --> PGKEY

    PROM --> NODE
    PROM --> BLACK
    PROM --> ALERT
    GRAF --> PROM

    WG --> SPOKE1
    WG --> SPOKE2
    WG --> SPOKE3

    SPOKE1 -.-> PROM
    SPOKE2 -.-> PROM
    SPOKE3 -.-> PROM

    classDef external fill:#f9f,stroke:#333,stroke-width:4px
    classDef proxy fill:#ff9,stroke:#333,stroke-width:2px
    classDef app fill:#9f9,stroke:#333,stroke-width:2px
    classDef data fill:#99f,stroke:#333,stroke-width:2px
    classDef monitoring fill:#f99,stroke:#333,stroke-width:2px
    
    class SMTP,GDRIVE external
    class NGINX proxy
    class API,KEYCLOAK app
    class TSDB,PGAPP,PGKEY,REDIS data
    class PROM,GRAF,ALERT,NODE,BLACK monitoring
```

## Network Architecture

```mermaid
graph TB
    subgraph "Public Network"
        INET[Internet]
        NGINX[NGINX :443]
    end

    subgraph "Frontend Network"
        KEYWEB[Keycloak Web :8443]
        GRAFWEB[Grafana Web :3000]
        APIWEB[API Gateway :8080]
    end

    subgraph "Application Network"
        API[Go API Service]
        KEY[Keycloak Service]
    end

    subgraph "Database Network"
        TSDB[(TimescaleDB :5432)]
        PGAPP[(PostgreSQL :5432)]
        PGKEY[(Keycloak DB :5432)]
        REDIS[(Redis :6379)]
    end

    subgraph "Monitoring Network"
        PROM[Prometheus :9090]
        ALERT[Alert Manager :9093]
        NODE[Node Exporter :9100]
        BLACK[Blackbox :9115]
    end

    subgraph "VPN Network 10.10.0.0/24"
        WG[WireGuard :51820]
        SPOKE1[Spoke 1]
        SPOKE2[Spoke 2]
    end

    INET --> NGINX
    NGINX --> KEYWEB
    NGINX --> GRAFWEB
    NGINX --> APIWEB

    APIWEB --> API
    KEYWEB --> KEY

    API --> TSDB
    API --> PGAPP
    API --> REDIS
    API --> WG
    API --> PROM

    KEY --> PGKEY

    PROM --> NODE
    PROM --> BLACK
    PROM --> ALERT

    WG --> SPOKE1
    WG --> SPOKE2

    SPOKE1 -.-> PROM
    SPOKE2 -.-> PROM

    classDef public fill:#f96,stroke:#333,stroke-width:4px
    classDef frontend fill:#9f9,stroke:#333,stroke-width:2px
    classDef app fill:#99f,stroke:#333,stroke-width:2px
    classDef data fill:#f9f,stroke:#333,stroke-width:2px
    classDef monitoring fill:#ff9,stroke:#333,stroke-width:2px
    classDef vpn fill:#69f,stroke:#333,stroke-width:2px

    class INET,NGINX public
    class KEYWEB,GRAFWEB,APIWEB frontend
    class API,KEY app
    class TSDB,PGAPP,PGKEY,REDIS data
    class PROM,ALERT,NODE,BLACK monitoring
    class WG,SPOKE1,SPOKE2 vpn
```

## Key Components

### Central Server (Hub)

- **VPN Server**: WireGuard-based secure communication
- **Authentication**: Keycloak-based identity management
- **API Service**: Go-based REST API
- **Monitoring**: Prometheus + Grafana stack
- **Storage**: TimescaleDB for time-series data

### Edge Devices (Spokes)

- **Hardware**: Raspberry Pi (v3/v5)
- **Local Storage**: TimescaleDB instance
- **Data Collection**: Python-based sensor collector
- **Monitoring**: Node exporter for system metrics
- **Security**: WireGuard VPN client, firewall rules

### Sensor Framework

- YAML-based configuration
- Pluggable sensor types
- Automated data collection
- Local buffering and sync
- Health monitoring and diagnostics

## Security Model

### Authentication Layers

1. Keycloak-based identity management
2. Role-based access control (RBAC)
3. VPN-level authentication
4. Service-level access control

### Access Roles

- **System Admin**: Full system access including SSH
- **Hive Admin**: Management of specific hives
- **User**: Data access and visualization
- **Guest**: Read-only public data access

### Network Security

- WireGuard VPN for all communications
- Isolated edge device networks
- Restricted service access
- Automated security updates

## Deployment

All components are containerized using Podman:

```mermaid
graph TB
    subgraph "Server Containers"
        K[Keycloak]
        G[Grafana]
        P[Prometheus]
        A[API Service]
        D[(TimescaleDB)]
    end
    
    subgraph "Edge Containers"
        DB2[(Local TimescaleDB)]
        C[Collector Service]
        M[Monitoring]
    end
```

## Server System Overview

### Components

- **TimescaleDB**: Time-series data storage for sensor readings
- **PostgreSQL**: Application data storage (user preferences, configurations)
- **Keycloak**: Authentication and authorization
- **Prometheus & Grafana**: Monitoring and visualization
- **Redis**: Caching and rate limiting
- **Vector & Loki**: Log aggregation and management
- **WireGuard**: VPN for edge device connectivity
- **Go API Service**: Core application service
- **Alert Manager**: System alerts and notifications

### Architecture

```mermaid
graph TB
    subgraph Internet
        Edge[Edge Devices]
        Users[Users]
    end
    
    subgraph Frontend
        NGINX[NGINX Reverse Proxy]
        Web[Web Interface]
    end
    
    subgraph Core
        API[Go API Service]
        VPN[WireGuard VPN]
        Auth[Keycloak]
    end
    
    subgraph Data
        TS[(TimescaleDB)]
        PG[(PostgreSQL)]
        RD[(Redis)]
    end
    
    subgraph Monitoring
        Prom[Prometheus]
        Graf[Grafana]
        Alert[Alert Manager]
        Vector[Vector]
        Loki[Loki]
    end

    Edge --> VPN
    Users --> NGINX
    NGINX --> Web
    NGINX --> API
    NGINX --> Auth
    NGINX --> Graf
    API --> TS
    API --> PG
    API --> RD
    API --> VPN
    Edge --> Prom
    All --> Vector --> Loki
```

## Container Management

We are using podman for container management. We have podman-compose installed.

