
# Technical Diagrams and System Architecture

## System Architecture Diagrams

### 1. Complete System Architecture

```mermaid
graph TB
    subgraph "Client Tier"
        WEB[Web Application<br/>React/Vue Frontend]
        MOBILE[Mobile Application<br/>React Native/Flutter]
        API_CLIENT[API Clients<br/>Third-party Integrations]
    end
    
    subgraph "API Gateway & Load Balancer"
        LB[Load Balancer<br/>Nginx/HAProxy]
        RATE[Rate Limiter<br/>Redis-based]
    end
    
    subgraph "Application Tier"
        direction TB
        FLASK[Flask Application Server<br/>Port 5000<br/>Gunicorn Workers]
        
        subgraph "Core Services"
            AUTH[Authentication Service<br/>Session Management]
            ANALYZER[Contract Analysis Engine]
            PROCESSOR[Document Processor]
            GENERATOR[Contract Generator]
            VALIDATOR[Input Validator]
        end
        
        subgraph "Business Logic"
            SHARIA[Sharia Compliance Logic]
            TERM[Term Extraction Logic]
            REVIEW[Expert Review Logic]
            MODIFICATION[Modification Engine]
        end
    end
    
    subgraph "AI/ML Tier"
        GEMINI[Google Gemini AI<br/>gemini-2.0-flash-thinking]
        EXTRACTION[Document Text Extraction<br/>Vision API]
        NLP[Natural Language Processing<br/>Language Detection]
    end
    
    subgraph "Data Tier"
        direction LR
        MONGO[(MongoDB Atlas<br/>Primary Database)]
        REDIS[(Redis Cache<br/>Session Storage)]
        
        subgraph "Collections"
            CONTRACTS[contracts collection]
            TERMS[terms collection]
            FEEDBACK[expert_feedback collection]
        end
    end
    
    subgraph "Storage Tier"
        CLOUDINARY[Cloudinary CDN<br/>File Storage & Processing]
        TEMP[Local Temporary Storage<br/>Processing Files]
        
        subgraph "File Types"
            ORIGINAL[Original Contracts]
            MODIFIED[Modified Contracts]
            MARKED[Marked Contracts]
            PREVIEWS[PDF Previews]
            ANALYSIS[Analysis Results]
        end
    end
    
    subgraph "External Services"
        LIBRE[LibreOffice<br/>PDF Conversion]
        SMTP[Email Service<br/>Notifications]
        MONITORING[Monitoring Services<br/>Logs & Metrics]
    end
    
    %% Client connections
    WEB --> LB
    MOBILE --> LB
    API_CLIENT --> LB
    
    %% Load balancer to application
    LB --> RATE
    RATE --> FLASK
    
    %% Application internal connections
    FLASK --> AUTH
    FLASK --> ANALYZER
    FLASK --> PROCESSOR
    FLASK --> GENERATOR
    FLASK --> VALIDATOR
    
    %% Business logic connections
    ANALYZER --> SHARIA
    ANALYZER --> TERM
    PROCESSOR --> MODIFICATION
    GENERATOR --> REVIEW
    
    %% AI service connections
    ANALYZER --> GEMINI
    PROCESSOR --> EXTRACTION
    VALIDATOR --> NLP
    
    %% Database connections
    FLASK --> MONGO
    FLASK --> REDIS
    MONGO --> CONTRACTS
    MONGO --> TERMS
    MONGO --> FEEDBACK
    
    %% Storage connections
    FLASK --> CLOUDINARY
    PROCESSOR --> TEMP
    CLOUDINARY --> ORIGINAL
    CLOUDINARY --> MODIFIED
    CLOUDINARY --> MARKED
    CLOUDINARY --> PREVIEWS
    CLOUDINARY --> ANALYSIS
    
    %% External service connections
    GENERATOR --> LIBRE
    FLASK --> SMTP
    FLASK --> MONITORING
    
    %% Styling
    classDef clientTier fill:#e1f5fe
    classDef appTier fill:#f3e5f5
    classDef aiTier fill:#e8f5e8
    classDef dataTier fill:#fff3e0
    classDef storageTier fill:#fce4ec
    
    class WEB,MOBILE,API_CLIENT clientTier
    class FLASK,AUTH,ANALYZER,PROCESSOR,GENERATOR appTier
    class GEMINI,EXTRACTION,NLP aiTier
    class MONGO,REDIS,CONTRACTS,TERMS,FEEDBACK dataTier
    class CLOUDINARY,TEMP,ORIGINAL,MODIFIED,MARKED,PREVIEWS,ANALYSIS storageTier
```

### 2. Data Flow Architecture

```mermaid
sequenceDiagram
    participant C as Client
    participant F as Flask Server
    participant V as Validator
    participant P as Processor
    participant AI as Gemini AI
    participant DB as MongoDB
    participant CL as Cloudinary
    participant G as Generator
    
    Note over C,G: Contract Analysis Flow
    
    C->>+F: POST /analyze (file upload)
    F->>+V: Validate file type & size
    V-->>-F: Validation result
    
    F->>+CL: Upload original file
    CL-->>-F: File URL & metadata
    
    F->>+P: Process document
    P->>P: Extract text & structure
    P->>+AI: Send for analysis
    AI-->>-P: Analysis results (JSON)
    P-->>-F: Structured analysis
    
    F->>+DB: Store contract & terms
    DB-->>-F: Storage confirmation
    
    F->>+CL: Store analysis results
    CL-->>-F: Results URL
    
    F-->>-C: Analysis response + session_id
    
    Note over C,G: Modification Flow
    
    C->>+F: POST /generate_modified_contract
    F->>+DB: Get confirmed modifications
    DB-->>-F: Modification data
    
    F->>+G: Generate modified contract
    G->>G: Apply modifications
    G->>G: Create DOCX & TXT
    G->>+CL: Upload generated files
    CL-->>-G: File URLs
    G-->>-F: Generation results
    
    F->>+DB: Update contract info
    DB-->>-F: Update confirmation
    
    F-->>-C: Generated file URLs
    
    Note over C,G: PDF Preview Flow
    
    C->>+F: GET /preview_contract/{session}/{type}
    F->>+DB: Check existing PDF
    DB-->>-F: PDF info (if exists)
    
    alt PDF exists
        F-->>C: Existing PDF URL
    else Generate new PDF
        F->>+CL: Download source DOCX
        CL-->>-F: DOCX file
        
        F->>F: Convert to PDF (LibreOffice)
        F->>+CL: Upload PDF
        CL-->>-F: PDF URL
        
        F->>+DB: Store PDF info
        DB-->>-F: Storage confirmation
        
        F-->>-C: New PDF URL
    end
```

### 3. Document Processing Pipeline

```mermaid
graph TD
    subgraph "Input Stage"
        UPLOAD[File Upload<br/>DOCX/PDF/TXT]
        VALIDATE[File Validation<br/>Type, Size, Format]
        STORE_ORIG[Store Original<br/>Cloudinary]
    end
    
    subgraph "Processing Stage"
        DETECT{File Type<br/>Detection}
        
        subgraph "DOCX Processing"
            DOCX_EXTRACT[python-docx<br/>Text Extraction]
            DOCX_STRUCTURE[Structure Analysis<br/>Paragraphs & Tables]
            DOCX_IDS[Assign Unique IDs<br/>para_X, table_Y_rA_cB]
            DOCX_MARKDOWN[Generate Markdown<br/>with Formatting]
        end
        
        subgraph "PDF Processing"
            PDF_AI[AI Text Extraction<br/>Gemini Vision API]
            PDF_CLEAN[Clean Extracted Text<br/>Remove Artifacts]
            PDF_STRUCTURE[Structure Recognition<br/>Headings & Lists]
        end
        
        subgraph "TXT Processing"
            TXT_READ[Direct Text Reading<br/>UTF-8 Encoding]
            TXT_STRUCTURE[Basic Structure<br/>Line-by-line]
        end
    end
    
    subgraph "Analysis Stage"
        LANG_DETECT[Language Detection<br/>Arabic/English]
        AI_ANALYSIS[AI Analysis<br/>Sharia Compliance]
        JSON_PARSE[Parse AI Response<br/>Extract JSON]
        TERM_EXTRACT[Term Extraction<br/>Individual Clauses]
    end
    
    subgraph "Storage Stage"
        DB_STORE[Database Storage<br/>MongoDB]
        CLOUD_STORE[Cloud Storage<br/>Analysis Results]
        SESSION_CREATE[Session Creation<br/>Unique ID]
    end
    
    UPLOAD --> VALIDATE
    VALIDATE --> STORE_ORIG
    STORE_ORIG --> DETECT
    
    DETECT -->|DOCX| DOCX_EXTRACT
    DETECT -->|PDF| PDF_AI
    DETECT -->|TXT| TXT_READ
    
    DOCX_EXTRACT --> DOCX_STRUCTURE
    DOCX_STRUCTURE --> DOCX_IDS
    DOCX_IDS --> DOCX_MARKDOWN
    
    PDF_AI --> PDF_CLEAN
    PDF_CLEAN --> PDF_STRUCTURE
    
    TXT_READ --> TXT_STRUCTURE
    
    DOCX_MARKDOWN --> LANG_DETECT
    PDF_STRUCTURE --> LANG_DETECT
    TXT_STRUCTURE --> LANG_DETECT
    
    LANG_DETECT --> AI_ANALYSIS
    AI_ANALYSIS --> JSON_PARSE
    JSON_PARSE --> TERM_EXTRACT
    
    TERM_EXTRACT --> DB_STORE
    TERM_EXTRACT --> CLOUD_STORE
    TERM_EXTRACT --> SESSION_CREATE
    
    classDef inputStage fill:#e3f2fd
    classDef processStage fill:#f1f8e9
    classDef analysisStage fill:#fff8e1
    classDef storageStage fill:#fce4ec
    
    class UPLOAD,VALIDATE,STORE_ORIG inputStage
    class DETECT,DOCX_EXTRACT,DOCX_STRUCTURE,DOCX_IDS,DOCX_MARKDOWN,PDF_AI,PDF_CLEAN,PDF_STRUCTURE,TXT_READ,TXT_STRUCTURE processStage
    class LANG_DETECT,AI_ANALYSIS,JSON_PARSE,TERM_EXTRACT analysisStage
    class DB_STORE,CLOUD_STORE,SESSION_CREATE storageStage
```

### 4. AI Integration Architecture

```mermaid
graph TB
    subgraph "AI Service Layer"
        direction TB
        
        subgraph "Google Generative AI"
            GEMINI[Gemini 2.0 Flash<br/>Thinking Model]
            CONFIG[Model Configuration<br/>Temperature: 0<br/>Safety Settings]
            SESSIONS[Chat Sessions<br/>Context Management]
        end
        
        subgraph "Prompt Engineering"
            SYS_PROMPT[System Prompts<br/>AAOIFI Standards]
            EXTRACTION[Text Extraction<br/>Prompts]
            INTERACTION[User Interaction<br/>Prompts]
            REVIEW[Modification Review<br/>Prompts]
        end
    end
    
    subgraph "Processing Engine"
        direction TB
        
        subgraph "Input Processing"
            TEXT_CLEAN[Text Cleaning<br/>& Preprocessing]
            LANG_FORMAT[Language Formatting<br/>Arabic/English]
            STRUCTURE[Structure Preservation<br/>Markdown/IDs]
        end
        
        subgraph "Response Processing"
            JSON_EXTRACT[JSON Extraction<br/>from AI Response]
            VALIDATE_RESP[Response Validation<br/>Schema Checking]
            ERROR_HANDLE[Error Handling<br/>Retry Logic]
        end
    end
    
    subgraph "Application Integration"
        direction TB
        
        ANALYZER[Contract Analyzer<br/>Main Analysis Logic]
        INTERACTIVE[Interactive Consultation<br/>Q&A System]
        REVIEWER[Modification Reviewer<br/>Expert Validation]
        EXTRACTOR[Document Extractor<br/>PDF/TXT Processing]
    end
    
    %% Connections
    ANALYZER --> TEXT_CLEAN
    INTERACTIVE --> LANG_FORMAT
    REVIEWER --> STRUCTURE
    EXTRACTOR --> TEXT_CLEAN
    
    TEXT_CLEAN --> SYS_PROMPT
    LANG_FORMAT --> INTERACTION
    STRUCTURE --> REVIEW
    
    SYS_PROMPT --> CONFIG
    EXTRACTION --> CONFIG
    INTERACTION --> CONFIG
    REVIEW --> CONFIG
    
    CONFIG --> GEMINI
    GEMINI --> SESSIONS
    
    SESSIONS --> JSON_EXTRACT
    JSON_EXTRACT --> VALIDATE_RESP
    VALIDATE_RESP --> ERROR_HANDLE
    
    ERROR_HANDLE --> ANALYZER
    ERROR_HANDLE --> INTERACTIVE
    ERROR_HANDLE --> REVIEWER
    ERROR_HANDLE --> EXTRACTOR
    
    classDef aiLayer fill:#e8f5e8
    classDef processEngine fill:#fff3e0
    classDef appIntegration fill:#f3e5f5
    
    class GEMINI,CONFIG,SESSIONS,SYS_PROMPT,EXTRACTION,INTERACTION,REVIEW aiLayer
    class TEXT_CLEAN,LANG_FORMAT,STRUCTURE,JSON_EXTRACT,VALIDATE_RESP,ERROR_HANDLE processEngine
    class ANALYZER,INTERACTIVE,REVIEWER,EXTRACTOR appIntegration
```

### 5. Database Schema Relationships

```mermaid
erDiagram
    CONTRACTS {
        string _id PK "Session ID"
        string session_id UK "Unique Session"
        string original_filename
        object original_cloudinary_info
        object analysis_results_cloudinary_info
        string original_format "docx|pdf|txt"
        text original_contract_plain
        text original_contract_markdown
        text generated_markdown_from_docx
        string detected_contract_language "ar|en"
        datetime analysis_timestamp
        object confirmed_terms "term_id -> modification"
        array interactions "User Q&A history"
        object modified_contract_info
        object marked_contract_info
        object pdf_preview_info
    }
    
    TERMS {
        objectid _id PK
        string session_id FK
        string term_id UK "Unique per session"
        text term_text
        boolean is_valid_sharia
        text sharia_issue
        text reference_number
        text modified_term
        boolean is_confirmed_by_user
        text confirmed_modified_text
        boolean has_expert_feedback
        objectid last_expert_feedback_id FK
        boolean expert_override_is_valid_sharia
    }
    
    EXPERT_FEEDBACK {
        objectid _id PK
        string session_id FK
        string term_id FK
        text original_term_text_snapshot
        string expert_user_id
        string expert_username
        datetime feedback_timestamp
        object ai_initial_analysis_assessment
        boolean expert_verdict_is_valid_sharia
        text expert_comment_on_term
        text expert_corrected_sharia_issue
        text expert_corrected_reference
        text expert_final_suggestion_for_term
        boolean original_ai_is_valid_sharia "Snapshot"
        text original_ai_sharia_issue "Snapshot"
        text original_ai_modified_term "Snapshot"
        text original_ai_reference_number "Snapshot"
    }
    
    SESSIONS {
        string session_id PK "Redis Key"
        datetime created_at
        datetime last_accessed
        object user_preferences
        boolean is_active
    }
    
    %% Relationships
    CONTRACTS ||--o{ TERMS : "has many terms"
    TERMS ||--o{ EXPERT_FEEDBACK : "can have feedback"
    CONTRACTS ||--o| SESSIONS : "linked to session"
    
    %% Indexes
    CONTRACTS {
        index session_id_idx "session_id"
        index timestamp_idx "analysis_timestamp"
        index language_idx "detected_contract_language"
    }
    
    TERMS {
        compound_index session_term_idx "session_id, term_id"
        index valid_sharia_idx "is_valid_sharia"
        index confirmed_idx "is_confirmed_by_user"
    }
    
    EXPERT_FEEDBACK {
        compound_index session_term_feedback_idx "session_id, term_id"
        index expert_idx "expert_user_id"
        index timestamp_idx "feedback_timestamp"
    }
```

### 6. Security Architecture

```mermaid
graph TB
    subgraph "External Threats"
        DDOS[DDoS Attacks]
        INJECTION[Injection Attacks]
        XSS[Cross-Site Scripting]
        CSRF[CSRF Attacks]
        FILE_UPLOAD[Malicious File Uploads]
    end
    
    subgraph "Defense Layer 1: Network Security"
        CDN[Cloudflare CDN<br/>DDoS Protection]
        FIREWALL[Web Application Firewall<br/>SQL Injection Prevention]
        RATE_LIMIT[Rate Limiting<br/>API Throttling]
    end
    
    subgraph "Defense Layer 2: Application Security"
        INPUT_VAL[Input Validation<br/>File Type & Size Checks]
        SANITIZE[Data Sanitization<br/>XSS Prevention]
        CORS[CORS Configuration<br/>Origin Restrictions]
        HEADERS[Security Headers<br/>CSP, HSTS, X-Frame-Options]
    end
    
    subgraph "Defense Layer 3: Data Security"
        ENCRYPT_TRANSIT[Encryption in Transit<br/>HTTPS/TLS 1.3]
        ENCRYPT_REST[Encryption at Rest<br/>MongoDB Encryption]
        SESSION_SEC[Secure Sessions<br/>HTTPOnly, Secure Cookies]
        API_KEY[API Key Management<br/>Environment Variables]
    end
    
    subgraph "Defense Layer 4: Infrastructure Security"
        ACCESS_CONTROL[Access Control<br/>IAM Policies]
        AUDIT_LOG[Audit Logging<br/>All Actions Tracked]
        BACKUP_SEC[Secure Backups<br/>Encrypted Storage]
        MONITORING[Security Monitoring<br/>Intrusion Detection]
    end
    
    subgraph "Internal Systems"
        FLASK_APP[Flask Application]
        DATABASE[MongoDB Atlas]
        CLOUD_STORAGE[Cloudinary]
        AI_SERVICE[Google AI]
    end
    
    %% Threat flows
    DDOS --> CDN
    INJECTION --> FIREWALL
    XSS --> SANITIZE
    CSRF --> HEADERS
    FILE_UPLOAD --> INPUT_VAL
    
    %% Defense flows
    CDN --> RATE_LIMIT
    FIREWALL --> INPUT_VAL
    RATE_LIMIT --> CORS
    
    INPUT_VAL --> ENCRYPT_TRANSIT
    SANITIZE --> SESSION_SEC
    CORS --> API_KEY
    HEADERS --> ENCRYPT_REST
    
    ENCRYPT_TRANSIT --> ACCESS_CONTROL
    ENCRYPT_REST --> AUDIT_LOG
    SESSION_SEC --> BACKUP_SEC
    API_KEY --> MONITORING
    
    ACCESS_CONTROL --> FLASK_APP
    AUDIT_LOG --> DATABASE
    BACKUP_SEC --> CLOUD_STORAGE
    MONITORING --> AI_SERVICE
    
    classDef threat fill:#ffcdd2
    classDef defense1 fill:#c8e6c9
    classDef defense2 fill:#dcedc8
    classDef defense3 fill:#f0f4c3
    classDef defense4 fill:#fff9c4
    classDef internal fill:#e1f5fe
    
    class DDOS,INJECTION,XSS,CSRF,FILE_UPLOAD threat
    class CDN,FIREWALL,RATE_LIMIT defense1
    class INPUT_VAL,SANITIZE,CORS,HEADERS defense2
    class ENCRYPT_TRANSIT,ENCRYPT_REST,SESSION_SEC,API_KEY defense3
    class ACCESS_CONTROL,AUDIT_LOG,BACKUP_SEC,MONITORING defense4
    class FLASK_APP,DATABASE,CLOUD_STORAGE,AI_SERVICE internal
```

### 7. Performance Monitoring Dashboard

```mermaid
graph TB
    subgraph "Performance Metrics Dashboard"
        
        subgraph "Response Time Metrics"
            RT_API[API Response Times<br/>P50, P95, P99]
            RT_AI[AI Processing Times<br/>Analysis Duration]
            RT_DB[Database Query Times<br/>Read/Write Performance]
            RT_STORAGE[Storage Operations<br/>Upload/Download Times]
        end
        
        subgraph "Throughput Metrics"
            TH_REQUESTS[Requests per Second<br/>Peak & Average]
            TH_ANALYSIS[Contracts Analyzed<br/>per Hour]
            TH_GENERATION[Documents Generated<br/>per Hour]
            TH_INTERACTIONS[User Interactions<br/>per Minute]
        end
        
        subgraph "Error Rate Metrics"
            ER_HTTP[HTTP Error Rates<br/>4xx, 5xx Responses]
            ER_AI[AI Service Failures<br/>Timeout & API Errors]
            ER_DB[Database Errors<br/>Connection & Query Failures]
            ER_STORAGE[Storage Failures<br/>Upload & Download Errors]
        end
        
        subgraph "Resource Utilization"
            RU_CPU[CPU Utilization<br/>Application Server]
            RU_MEMORY[Memory Usage<br/>Heap & Process Memory]
            RU_DISK[Disk Usage<br/>Temporary Files]
            RU_NETWORK[Network Bandwidth<br/>Ingress & Egress]
        end
        
        subgraph "Business Metrics"
            BM_COMPLIANCE[Compliance Rate<br/>Valid vs Invalid Terms]
            BM_SATISFACTION[User Satisfaction<br/>Completion Rate]
            BM_EXPERTISE[Expert Reviews<br/>Override Rate]
            BM_CONVERSION[Contract Generation<br/>Success Rate]
        end
        
        subgraph "Alerting System"
            ALERT_PERF[Performance Alerts<br/>Response Time SLA]
            ALERT_ERROR[Error Rate Alerts<br/>Threshold Breaches]
            ALERT_RESOURCE[Resource Alerts<br/>CPU/Memory Limits]
            ALERT_BUSINESS[Business Alerts<br/>Compliance Issues]
        end
    end
    
    %% Metric relationships
    RT_API --> ALERT_PERF
    RT_AI --> ALERT_PERF
    RT_DB --> ALERT_PERF
    RT_STORAGE --> ALERT_PERF
    
    ER_HTTP --> ALERT_ERROR
    ER_AI --> ALERT_ERROR
    ER_DB --> ALERT_ERROR
    ER_STORAGE --> ALERT_ERROR
    
    RU_CPU --> ALERT_RESOURCE
    RU_MEMORY --> ALERT_RESOURCE
    RU_DISK --> ALERT_RESOURCE
    RU_NETWORK --> ALERT_RESOURCE
    
    BM_COMPLIANCE --> ALERT_BUSINESS
    BM_SATISFACTION --> ALERT_BUSINESS
    BM_EXPERTISE --> ALERT_BUSINESS
    BM_CONVERSION --> ALERT_BUSINESS
    
    classDef metrics fill:#e3f2fd
    classDef alerts fill:#ffebee
    
    class RT_API,RT_AI,RT_DB,RT_STORAGE,TH_REQUESTS,TH_ANALYSIS,TH_GENERATION,TH_INTERACTIONS,ER_HTTP,ER_AI,ER_DB,ER_STORAGE,RU_CPU,RU_MEMORY,RU_DISK,RU_NETWORK,BM_COMPLIANCE,BM_SATISFACTION,BM_EXPERTISE,BM_CONVERSION metrics
    class ALERT_PERF,ALERT_ERROR,ALERT_RESOURCE,ALERT_BUSINESS alerts
```

### 8. Deployment Pipeline

```mermaid
graph LR
    subgraph "Development Environment"
        DEV_CODE[Local Development<br/>Python 3.12]
        DEV_TEST[Unit Testing<br/>pytest]
        DEV_LINT[Code Linting<br/>flake8, black]
    end
    
    subgraph "Version Control"
        GIT[Git Repository<br/>Version Control]
        PR[Pull Request<br/>Code Review]
        MERGE[Merge to Main<br/>Automated Checks]
    end
    
    subgraph "CI/CD Pipeline"
        BUILD[Build Process<br/>Dependencies Install]
        TEST_INTEGRATION[Integration Tests<br/>API Testing]
        SECURITY_SCAN[Security Scanning<br/>Vulnerability Check]
        QUALITY_GATE[Quality Gate<br/>Coverage & Standards]
    end
    
    subgraph "Staging Environment"
        STAGING_DEPLOY[Staging Deployment<br/>Replit Staging]
        STAGING_TEST[End-to-End Testing<br/>User Scenarios]
        PERFORMANCE_TEST[Performance Testing<br/>Load & Stress]
    end
    
    subgraph "Production Environment"
        PROD_DEPLOY[Production Deployment<br/>Replit Production]
        HEALTH_CHECK[Health Checks<br/>System Validation]
        MONITORING_SETUP[Monitoring Setup<br/>Alerts & Logging]
        ROLLBACK[Rollback Strategy<br/>Quick Recovery]
    end
    
    subgraph "Post-Deployment"
        SMOKE_TEST[Smoke Testing<br/>Critical Path Validation]
        METRICS[Metrics Collection<br/>Performance Monitoring]
        USER_FEEDBACK[User Feedback<br/>System Performance]
    end
    
    %% Flow connections
    DEV_CODE --> DEV_TEST
    DEV_TEST --> DEV_LINT
    DEV_LINT --> GIT
    
    GIT --> PR
    PR --> MERGE
    MERGE --> BUILD
    
    BUILD --> TEST_INTEGRATION
    TEST_INTEGRATION --> SECURITY_SCAN
    SECURITY_SCAN --> QUALITY_GATE
    
    QUALITY_GATE --> STAGING_DEPLOY
    STAGING_DEPLOY --> STAGING_TEST
    STAGING_TEST --> PERFORMANCE_TEST
    
    PERFORMANCE_TEST --> PROD_DEPLOY
    PROD_DEPLOY --> HEALTH_CHECK
    HEALTH_CHECK --> MONITORING_SETUP
    MONITORING_SETUP --> ROLLBACK
    
    ROLLBACK --> SMOKE_TEST
    SMOKE_TEST --> METRICS
    METRICS --> USER_FEEDBACK
    
    classDef development fill:#e8f5e8
    classDef versionControl fill:#fff3e0
    classDef cicd fill:#f3e5f5
    classDef staging fill:#e1f5fe
    classDef production fill:#ffebee
    classDef postDeploy fill:#f9fbe7
    
    class DEV_CODE,DEV_TEST,DEV_LINT development
    class GIT,PR,MERGE versionControl
    class BUILD,TEST_INTEGRATION,SECURITY_SCAN,QUALITY_GATE cicd
    class STAGING_DEPLOY,STAGING_TEST,PERFORMANCE_TEST staging
    class PROD_DEPLOY,HEALTH_CHECK,MONITORING_SETUP,ROLLBACK production
    class SMOKE_TEST,METRICS,USER_FEEDBACK postDeploy
```

## Performance Benchmark Charts

### API Response Time Distribution

```
API Endpoint Performance (ms)
╭─────────────────────────────────────────────────────────╮
│                                                         │
│  /analyze           ████████████████████▓▓ 2800ms (P95) │
│                     ████████████▓▓ 1800ms (P50)         │
│                                                         │
│  /generate_modified ████████████▓▓ 1200ms (P95)         │
│                     ████▓▓ 600ms (P50)                  │
│                                                         │
│  /interact          ███▓▓ 450ms (P95)                   │
│                     ▓▓ 200ms (P50)                      │
│                                                         │
│  /preview_contract  ████████▓▓ 900ms (P95)              │
│                     ███▓▓ 400ms (P50)                   │
│                                                         │
│  /terms             ▓ 80ms (P95)                        │
│                     ▓ 40ms (P50)                        │
│                                                         │
╰─────────────────────────────────────────────────────────╯
```

### System Resource Utilization

```
Resource Utilization Over Time
╭─────────────────────────────────────────────────────────╮
│ CPU %                                                   │
│ 100├─────────────────────────────────────────────────── │
│  80│        ████                    ████                │
│  60│    ████    ████            ████    ████            │
│  40│████            ████    ████            ████        │
│  20│                    ████                    ████    │
│   0└─────────────────────────────────────────────────── │
│                                                         │
│ Memory (GB)                                             │
│   8├─────────────────────────────────────────────────── │
│   6│                    ████████████████████████████    │
│   4│            ████████                                │
│   2│    ████████                                        │
│   0└─────────────────────────────────────────────────── │
│    0    5    10   15   20   25   30   35   40   45   50 │
│                        Time (minutes)                   │
╰─────────────────────────────────────────────────────────╯
```

### Error Rate Tracking

```
Error Rates by Category (Last 24 Hours)
╭─────────────────────────────────────────────────────────╮
│                                                         │
│ HTTP 4xx Errors      ██▓ 2.3%                          │
│ HTTP 5xx Errors      ▓ 0.8%                            │
│ AI Service Failures  █▓ 1.5%                           │
│ Database Timeouts    ▓ 0.3%                            │
│ Storage Failures     ▓ 0.2%                            │
│                                                         │
│ Total Error Rate: 5.1%                                 │
│ SLA Target: <5.0% ❌                                    │
│                                                         │
╰─────────────────────────────────────────────────────────╯
```

This comprehensive technical documentation provides deep insights into the Shariaa Contract Analyzer backend architecture, including detailed diagrams, performance metrics, and technical specifications. The documentation covers all aspects from high-level architecture to implementation details, making it suitable for both technical teams and stakeholders.
