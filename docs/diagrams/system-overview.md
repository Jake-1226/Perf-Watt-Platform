# System Architecture Diagrams

**Author:** Manu Nicholas Jacob  
**Email:** ManuNicholas.Jacob@dell.com  
**Last Updated:** March 4, 2026

## High-Level System Overview

```mermaid
graph TB
    subgraph "Operator's Machine"
        UI[Browser<br/>React Frontend]
        API[FastAPI Backend<br/>Python 3.12]
        WS[WebSocket Server]
        STATIC[Static File Server]
        DB[(Platform DB<br/>SQLite)]
        RUNDB[(Per-Run DB<br/>SQLite)]
    end
    
    subgraph "Remote Server"
        SSH[SSH Connection<br/>paramiko]
        AGENT[Benchmark Agent<br/>bench_agent.sh]
        OS[OS Metrics<br/>/proc/stat, free, ps]
        NVME[NVMe Drives<br/>8x 3.5TB data drives]
        STRESS[stress-ng<br/>CPU workload]
        FIO[FIO<br/>Storage I/O]
    end
    
    subgraph "Dell iDRAC"
        IDRAC[iDRAC BMC<br/>SSH → racadm → rootshell]
        THM[thmtest -g s<br/>Power/thermal sensors]
        POWER[Power Sensors<br/>AC, CPU, DIMM, Storage, Fan]
        TEMP[Thermal Sensors<br/>Inlet, Exhaust, CPU]
    end
    
    UI -->|HTTP/WebSocket| API
    API --> STATIC
    API --> WS
    API --> DB
    API --> RUNDB
    API -->|SSH commands| SSH
    SSH --> AGENT
    AGENT --> OS
    AGENT --> NVME
    AGENT --> STRESS
    AGENT --> FIO
    API -->|SSH interactive| IDRAC
    IDRAC --> THM
    THM --> POWER
    THM --> TEMP
    
    classDef frontend fill:#e1f5fe
    classDef backend fill:#f3e5f5
    classDef remote fill:#e8f5e8
    classDef idrac fill:#fff3e0
    
    class UI frontend
    class API,WS,STATIC,DB,RUNDB backend
    class SSH,AGENT,OS,NVME,STRESS,FIO remote
    class IDRAC,THM,POWER,TEMP idrac
```

## Data Flow Architecture

```mermaid
flowchart TD
    subgraph "Telemetry Collection"
        IN[InboundCollector<br/>2s interval]
        OUT[OutboundCollector<br/>5s interval]
        STORE[(Telemetry DB<br/>per-run)]
        BROADCAST[WebSocket<br/>2s broadcast]
    end
    
    subgraph "OS Metrics Sources"
        PROC[/proc/stat]
        FREE[free -m]
        LOAD[/proc/loadavg]
        PS[ps command]
    end
    
    subgraph "iDRAC Power Sources"
        THMTEST[thmtest -g s]
        AC[SYS_PWR_INPUT_AC]
        CPU[CPU_PWR_ALL]
        DIMM[DIMM_PWR_ALL]
        STORAGE[STORAGE_PWR]
        FAN[FAN_PWR_MAIN]
        THERMAL[Thermal sensors]
    end
    
    PROC --> IN
    FREE --> IN
    LOAD --> IN
    PS --> IN
    
    THMTEST --> OUT
    AC --> OUT
    CPU --> OUT
    DIMM --> OUT
    STORAGE --> OUT
    FAN --> OUT
    THERMAL --> OUT
    
    IN --> STORE
    OUT --> STORE
    IN --> BROADCAST
    OUT --> BROADCAST
    
    classDef collector fill:#e3f2fd
    classDef source fill:#e8f5e8
    classDef storage fill:#f1f8e9
    classDef ws fill:#fff8e1
    
    class IN,OUT collector
    class PROC,FREE,LOAD,PS,THMTEST,AC,CPU,DIMM,STORAGE,FAN,THERMAL source
    class STORE storage
    class BROADCAST ws
```

## Benchmark Execution Flow

```mermaid
sequenceDiagram
    participant UI as Browser UI
    participant API as FastAPI Backend
    participant SSH as SSHManager
    participant Agent as bench_agent.sh
    participant Stress as stress-ng
    participant FIO as fio
    participant Inbound as InboundCollector
    participant Outbound as OutboundCollector
    participant DB as Telemetry DB
    
    UI->>API: POST /api/test/start
    API->>SSH: SFTP upload bench_agent.sh
    API->>Agent: bash bench_agent.sh install_deps
    API->>Agent: bash bench_agent.sh setup_hpl
    
    Note over API,DB: Start telemetry collectors
    API->>Inbound: start() (2s interval)
    API->>Outbound: start() (5s interval)
    
    loop Each Phase
        API->>Agent: bash bench_agent.sh run_<benchmark>
        Agent->>Stress: stress-ng --cpu <cores>
        Agent->>FIO: fio <config>
        
        Note over Inbound,DB: Collect OS metrics
        Inbound->>DB: store_os_metrics()
        
        Note over Outbound,DB: Collect power metrics
        Outbound->>DB: store_power_metrics()
        
        Note over API,UI: Broadcast telemetry
        API->>UI: WebSocket {telemetry}
        
        Note over Agent,API: Stream logs
        Agent->>API: stdout/stderr
        API->>UI: WebSocket {log}
    end
    
    API->>Agent: kill benchmark processes
    API->>Inbound: stop()
    API->>Outbound: stop()
    API->>UI: WebSocket {test_complete}
    UI->>API: POST /api/report/generate
```

## Database Schema Overview

```mermaid
erDiagram
    PLATFORM_DB {
        string name PK
        string created_at
        string updated_at
        string os_ip
        string os_user
        string os_pass
        string idrac_ip
        string idrac_user
        string idrac_pass
        string notes
    }
    
    SANITY_RESULTS {
        int id PK
        int config_id FK
        string checked_at
        text os_sysinfo
        text idrac_sysinfo
        text idrac_power
        text capabilities
        string status
    }
    
    TEST_RUNS {
        int id PK
        string run_id UK
        int config_id FK
        string started_at
        string finished_at
        string status
        int phase_duration
        int rest_duration
        text phases
        int total_cores
        string fio_targets
        string current_phase
        text os_sysinfo
        text idrac_sysinfo
        text summary
        string notes
    }
    
    TELEMETRY_DB {
        int id PK
        string timestamp
        real epoch
        string phase
        real cpu_pct
        real mem_pct
        real mem_used_mb
        real mem_total_mb
        real load_1m
        real load_5m
        real load_15m
        real disk_read_kbs
        real disk_write_kbs
        real net_rx_kbs
        real net_tx_kbs
        int process_count
        text top_processes
    }
    
    POWER_METRICS {
        int id PK
        string timestamp
        real epoch
        string phase
        real sys_input_ac_w
        real cpu_power_w
        real dimm_power_w
        real storage_power_w
        real fan_power_w
        real inlet_temp_c
        real exhaust_temp_c
        real cpu_temp_c
        text raw_sensors
    }
    
    BENCHMARK_EVENTS {
        int id PK
        string timestamp
        real epoch
        string phase
        string event_type
        string benchmark
        string message
        text data
    }
    
    SYSTEM_INFO {
        int id PK
        string collected_at
        string source
        string key
        string value
    }
    
    PLATFORM_DB ||--o{ SANITY_RESULTS : "has"
    PLATFORM_DB ||--o{ TEST_RUNS : "has"
```

## Component Interaction Map

```mermaid
graph LR
    subgraph "Frontend Layer"
        HOME[Home Panel]
        CONNECT[Connect Panel]
        SANITY[Sanity Panel]
        CONFIG[Config Panel]
        DASH[Dashboard Panel]
        REPORT[Report Panel]
    end
    
    subgraph "API Layer"
        REST[REST API]
        WS[WebSocket]
        STATIC[Static Server]
    end
    
    subgraph "Service Layer"
        SSHMGR[SSHManager]
        ORCH[BenchmarkOrchestrator]
        INCOL[InboundCollector]
        OUTCOL[OutboundCollector]
        CONFIGDB[Config DB]
        REPORTS[Report Generator]
    end
    
    subgraph "Data Layer"
        PLATFORM[(platform.db)]
        TELEMETRY[(telemetry.db)]
        FILES[Report Files]
    end
    
    subgraph "Remote Systems"
        OS[Remote Server OS]
        IDRAC[Dell iDRAC]
    end
    
    HOME --> REST
    CONNECT --> REST
    SANITY --> REST
    CONFIG --> REST
    DASH --> REST
    DASH --> WS
    REPORT --> REST
    
    REST --> SSHMGR
    REST --> CONFIGDB
    REST --> REPORTS
    WS --> ORCH
    WS --> INCOL
    WS --> OUTCOL
    
    SSHMGR --> OS
    SSHMGR --> IDRAC
    ORCH --> SSHMGR
    INCOL --> SSHMGR
    OUTCOL --> SSHMGR
    
    CONFIGDB --> PLATFORM
    INCOL --> TELEMETRY
    OUTCOL --> TELEMETRY
    REPORTS --> FILES
    
    classDef frontend fill:#e1f5fe
    classDef api fill:#f3e5f5
    classDef service fill:#e8f5e8
    classDef data fill:#f1f8e9
    classDef remote fill:#fff3e0
    
    class HOME,CONNECT,SANITY,CONFIG,DASH,REPORT frontend
    class REST,WS,STATIC api
    class SSHMGR,ORCH,INCOL,OUTCOL,CONFIGDB,REPORTS service
    class PLATFORM,TELEMETRY,FILES data
    class OS,IDRAC remote
```
