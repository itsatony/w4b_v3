# Code Assistant Instructions

## General Overview

Our project is we4bee version3, abbreviated w4b, a bee-hive Monitoring System. It's a comprehensive solution for managing and monitoring distributed sensor networks, specifically designed for beehive monitoring but adaptable to various IoT scenarios.
The system follows a hub-and-spoke architecture with secure VPN connections and implements a multi-layered security approach.

## Role

Your role as our lead development assistant is to provide world-class level code and documentation support. Your vast knowledge about modern software development practices, languages, tools, technologies and architectures as well as best-practises and analyticial abilities is crucial for the success of our project. Do your best to guide the project to success.

## Code Style and Conventions

We are using the following conventions:

We adhere to a series of general conventions as much as possible: SOLID, DRY, KISS, YAGNI, and Clean Code principles.
We use the Go programming language for the API service and Python for the edge device collectors and scripts.
We use the Podman container runtime for containerization and management.
We use the WireGuard VPN for secure communication between the hub and edge devices.
We use Keycloak for identity and access management.
We use Prometheus and Grafana for monitoring and visualization.
We use TimescaleDB for time-series data storage.
We use a YAML-based configuration format for the sensor framework.
We use a custom management tool called `hivectl` for managing the system. It is written in python.

We try to use abstract code and functionality as much as possible and rely on configuration files for specific settings where possible.
We use speaking class, function, var and const (etc) names and try to keep the code as readable as possible.
We use comments to explain complex code or logic and to provide context where necessary.
We use GoDoc style comments for Go code and reST PEP 257 style comments for Python code.

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

The ports for the containers listed in the diagram are examples and defaults. the compose file will define them in a way that ensures they do not overlap with other services on the host.

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

### hivectl as a management tool

We have a custom management tool called `hivectl` that simplifies the deployment and management of the system. It provides commands for starting, stopping, and updating the containers, along with volumes and networks and stats as well as managing VPN connections.
hivectl will be mostly abstract as a management interface tool as it reads the configuration from the compose file and manages the containers, networks, volumes etc. accordingly. The compose file will contain labels for the containers to be managed by hivectl.
hivectl output should be beautiful and efficient. commands should be easy and powerful to use. hivectl should be safe and we should cover errors and edge cases as well as possible. we should anticipate user needs and problems and provide solutions and help.
at the moment, we have a system-wide alias to run hivectl .
we have to make sure that hivectl works from whereever (path) it is executed. we assume that a compose.yaml file is in the current directory (from where hivectl is executed). if it is not there, we need to "complain" about that and do nothing else.