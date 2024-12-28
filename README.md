# w4b_v3 Hive Monitoring System

a sensordata collection system

(Claude3.5sonnet discussion system setup)[https://claude.ai/chat/050c228a-4d85-4138-9469-7529427e008e]

## System Overview

The Hive Monitoring System is a comprehensive solution for managing and monitoring distributed sensor networks, specifically designed for beehive monitoring but adaptable to various IoT scenarios. The system follows a hub-and-spoke architecture with secure VPN connections and implements a multi-layered security approach.

### Core Architecture

```mermaid
graph TB
    subgraph "Central Server [Hub]"
        K[Keycloak]
        API[Go API Service]
        WG[WireGuard VPN]
        TS[(TimescaleDB)]
        G[Grafana]
        P[Prometheus]
        direction TB
        
        K --> API
        API --> WG
        API --> TS
        G --> TS
        G --> P
    end
    
    subgraph "Edge Devices [Spokes]"
        R1[Raspberry Pi]
        R2[Raspberry Pi]
        R3[Raspberry Pi]
        
        subgraph "Edge Components"
            DB[(Local TimescaleDB)]
            COL[Sensor Collector]
            VPN[WireGuard Client]
            MON[Node Exporter]
        end
        
        R1 --> VPN
        R2 --> VPN
        R3 --> VPN
    end
    
    WG -.-> VPN

    subgraph "User Access"
        U1[System Admin]
        U2[Hive Admin]
        U3[User]
        
        U1 --> API
        U2 --> API
        U3 --> API
    end
```

### Security Layers

```mermaid
graph TB
    subgraph "Authentication & Authorization"
        K[Keycloak]
        RBAC[Role-Based Access]
        MFA[Multi-Factor Auth]
    end
    
    subgraph "Network Security"
        VPN[WireGuard VPN]
        FW[Firewall Rules]
        TLS[TLS/SSL]
    end
    
    subgraph "Data Security"
        ENC[Data Encryption]
        BAK[Automated Backups]
        AUD[Audit Logging]
    end
    
    K --> RBAC
    RBAC --> VPN
    VPN --> ENC
    ENC --> BAK
    RBAC --> AUD
```

### Data Flow

```mermaid
sequenceDiagram
    participant S as Sensors
    participant R as Raspberry Pi
    participant DB as Local TimescaleDB
    participant VPN as VPN Tunnel
    participant C as Central Server
    participant U as Users

    S->>R: Raw Sensor Data
    R->>R: Process & Validate
    R->>DB: Store Local Data
    R->>VPN: Establish Connection
    DB->>C: Sync Data via VPN
    C->>C: Aggregate & Analyze
    U->>C: Request Data
    C->>U: Return Visualizations
```

## Server Architecture

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

## New Hive Setup

The hive onboarding process involves several coordinated steps:

1. Hive Definition Phase:
   - System admin creates new hive entry via web interface
   - Provides basic metadata (location, contact info, timezone)
   - Assigns unique hive ID (format: "hive_XXXXX")
   - Defines sensor configuration and requirements
   - Sets up hive-specific admin account

2. Security Setup Phase:
   - System generates unique VPN credentials
   - Creates SSH keypair for secure access
   - Generates database credentials
   - Configures firewall rules specific to this hive
   - Creates Keycloak roles and permissions

3. Image Generation Phase:
   - Pulls base Raspberry Pi OS image
   - Injects VPN, SSH, and database configurations
   - Configures sensor collector with provided settings
   - Sets up monitoring and logging
   - Configures automatic updates and maintenance

4. Administration Setup:
   - Creates hive-specific admin in Keycloak
   - Assigns appropriate roles and permissions
   - Sets up monitoring dashboards
   - Configures alert rules and notifications

5. Deployment Package Creation:
   - Generates the customized OS image
   - Creates deployment documentation
   - Packages configuration backup
   - Generates QR codes for easy mobile access

6. Verification & Activation:
   - System validates all generated configurations
   - Tests VPN connectivity settings
   - Verifies database access
   - Checks monitoring configuration
   - Prepares activation checklist

This diagram shows the complete flow from initial request to deployment-ready package. Each subgraph represents a major phase in the onboarding process, with clear dependencies and data flow between steps.

```mermaid
flowchart TB
    subgraph "1. Initial Request"
        A[System Admin] -->|Creates| B[New Hive Request]
        B -->|Provides| C[Hive Metadata]
        C -->|Includes| D[Location/Contact/Sensors]
    end

    subgraph "2. Security Generation"
        E[Security Service]
        C -->|Triggers| E
        E -->|Generates| F[VPN Credentials]
        E -->|Creates| G[SSH Keys]
        E -->|Sets up| H[DB Credentials]
    end

    subgraph "3. Identity Setup"
        I[Keycloak Service]
        C -->|Triggers| I
        I -->|Creates| J[Hive Admin Account]
        I -->|Assigns| K[Roles & Permissions]
    end

    subgraph "4. Image Creation"
        L[Image Generator]
        F --> L
        G --> L
        H --> L
        L -->|Customizes| M[Base OS Image]
        M -->|Configures| N[System Services]
        N -->|Sets up| O[Monitoring]
        O -->|Enables| P[Auto Updates]
    end

    subgraph "5. Deployment Package"
        Q[Package Creator]
        M --> Q
        Q -->|Generates| R[OS Image]
        Q -->|Creates| S[Documentation]
        Q -->|Produces| T[QR Codes]
        Q -->|Backs up| U[Configurations]
    end

    subgraph "6. Verification"
        V[Validation Service]
        R --> V
        V -->|Tests| W[VPN Connectivity]
        V -->|Verifies| X[DB Access]
        V -->|Checks| Y[Monitoring]
        V -->|Produces| Z[Activation Package]
    end

    Z -->|Ready for| AA[Deployment]
    AA -->|Assigned to| J
```

## Data Management

### Local Storage

- Short-term sensor data storage
- System health metrics
- Configuration data
- Local logs and diagnostics

### Central Storage

- Long-term data aggregation
- Cross-hive analytics
- System-wide monitoring
- Audit logs and security events

## Monitoring & Diagnostics

### Edge Monitoring

- Sensor health and status
- System resources (CPU, memory, disk)
- Network connectivity
- Service status
- Data collection metrics

### Central Monitoring

- Fleet-wide system health
- Data collection statistics
- Security events
- Performance metrics
- User activity

## Development & Maintenance

### Version Control

Single Git repository with structured layout:

```
/
├── docs/
├── server/
│   ├── api/
│   ├── monitoring/
│   └── deployment/
├── edge/
│   ├── collector/
│   ├── sensors/
│   └── monitoring/
├── deployment/
│   ├── server/
│   └── edge/
└── tools/
```

### Continuous Integration

- Automated testing
- Image building
- Security scanning
- Documentation generation

This system is designed to be:

- **Scalable**: Supporting hundreds of edge devices
- **Secure**: Multi-layered security approach
- **Maintainable**: Well-documented and modular
- **Reliable**: Robust data collection and storage
- **Extensible**: Pluggable sensor framework