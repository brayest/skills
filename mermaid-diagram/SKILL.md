---
name: mermaid-diagram
description: >
  Create high-quality Mermaid.js diagrams for data flows, AWS architecture, service communication,
  and infrastructure visualization. Use this skill whenever the user asks for a diagram, architecture
  visualization, data flow chart, sequence diagram, infrastructure map, system design diagram, or
  anything that should be rendered as Mermaid. Also trigger when the user mentions flowchart,
  architecture diagram, pipeline visualization, ER diagram, state machine diagram, C4 diagram,
  or wants to visualize AWS services, cloud infrastructure, or data pipelines — even if they
  don't explicitly say "Mermaid."
---

# Mermaid Diagram Creation

You create professional, valid Mermaid.js diagrams. Your knowledge base is in `references/mermaid-guide.md` — consult it when you need syntax details, shape references, edge types, or AWS patterns.

## Core Workflow

1. **Clarify the diagram type** — Ask yourself (or the user if ambiguous): Is this a data flow, AWS architecture, service communication, entity relationships, or state transitions? Pick the right Mermaid diagram type:

   | Need | Diagram Type | Syntax Keyword |
   |------|-------------|----------------|
   | Data pipelines, processing flows | Flowchart | `flowchart LR` |
   | AWS infrastructure layout | Architecture | `architecture-beta` |
   | Service-to-service calls | Sequence | `sequenceDiagram` |
   | Software architecture (enterprise) | C4 | `C4Context` / `C4Container` |
   | Database schemas | ER | `erDiagram` |
   | State machines, lifecycles | State | `stateDiagram-v2` |
   | Manual component layout | Block | `block-beta` |

2. **Draft the diagram** using the patterns below.
3. **Validate mentally** — check that all node IDs are consistent, edges connect valid nodes, and subgraphs are properly closed.
4. **Output** — Present the diagram in a fenced mermaid code block with a brief explanation of what it shows.

## Diagram Type Guidelines

### Flowcharts (Data Flows & Pipelines)

Use `flowchart LR` for data pipelines (left-to-right reads naturally). Use `flowchart TD` for hierarchical/tree structures.

**Shape selection matters** — shapes communicate component types at a glance:
- `[(Cylinder)]` — databases (RDS, DynamoDB, pgvector)
- `[Rectangle]` — services, processes (ECS, Lambda, EC2)
- `((Circle))` — events, signals (EventBridge, S3 notifications)
- `{Diamond}` — decisions, routing (ALB rules, conditionals)
- `([Stadium])` — external services, I/O (Azure OpenAI, user input)
- `{{Hexagon}}` — preparation steps, transforms

**Edge types** — match the edge to the relationship:
- `-->` solid arrow: direct data flow
- `-.->` dotted arrow: async/eventual
- `==>` thick arrow: high-volume or critical path
- `--o` circle end: data store write
- `--x` cross end: error/rejection path
- `-- label -->` or `-->|label|` for labeled edges

**Subgraphs** group related components (VPCs, subnets, services):
```
subgraph VPC["VPC 10.0.0.0/16"]
    subgraph pub["Public Subnet"]
        ALB[Application Load Balancer]
    end
    subgraph priv["Private Subnet"]
        ECS[ECS Fargate]
        RDS[(PostgreSQL RDS)]
    end
end
```

Subgraphs can have their own direction: `direction LR` inside the subgraph.

**Styling** — use `classDef` for reusable styles and `style` for one-offs:
```
classDef aws fill:#FF9900,stroke:#232F3E,color:#fff
classDef database fill:#2E73B8,stroke:#1A4B7A,color:#fff
class ECS,Lambda aws
class RDS,DynamoDB database
```

### Architecture Diagrams (architecture-beta)

Purpose-built for cloud infrastructure. Requires Mermaid v11.1.0+.

Four building blocks: **groups** (visual containers), **services** (components), **edges** (connections), **junctions** (routing points).

```
architecture-beta
    group vpc(cloud)[VPC]

    service alb(internet)[ALB] in vpc
    service ecs(server)[ECS Fargate] in vpc
    service rds(database)[RDS PostgreSQL] in vpc

    alb:R --> L:ecs
    ecs:R --> L:rds
```

**Edge routing** uses compass directions (T/B/L/R) on both sides:
- `service1:R --> L:service2` — right side of service1 to left side of service2

**Built-in icons**: `cloud`, `database`, `disk`, `internet`, `server`

**For AWS-specific icons** (Iconify): Use `logos:aws-lambda`, `logos:aws-s3`, etc. These require HTML or mmdc rendering — they won't show in GitHub markdown. Note this limitation when the user's target is markdown.

**Junctions** for fan-out/fan-in patterns:
```
junction junc1 in vpc
alb:R --> L:junc1
junc1:R --> L:ecs1
junc1:R --> L:ecs2
```

### Sequence Diagrams (Service Communication)

Best for showing request/response flows, API calls, and service interactions over time.

```
sequenceDiagram
    participant C as Client
    participant ALB as Load Balancer
    participant API as API Service
    participant DB as Database

    C->>ALB: HTTPS Request
    ALB->>API: Forward to target group
    API->>DB: Query
    DB-->>API: Results
    API-->>ALB: Response
    ALB-->>C: HTTPS Response
```

**Arrow types**:
- `->>` solid with arrowhead (synchronous)
- `-->>` dotted with arrowhead (async response)
- `-x` solid with cross (failure)
- `-)` async fire-and-forget

**Control flow** — `loop`, `alt/else`, `opt`, `par/and`, `critical/option`

**Activation** shows when a service is actively processing. Use the `+`/`-` shorthand on arrows instead of separate activate/deactivate statements — it's more reliable across Mermaid versions and avoids issues inside `alt`/`else` blocks:
```
API->>+DB: Query
DB-->>-API: Results
```

The `+` after `>>` activates the target; `-` before `>>` deactivates the source. This is equivalent to separate activate/deactivate but works correctly inside control flow blocks.

**Important**: Do NOT use separate `activate`/`deactivate` statements inside `alt`, `else`, `opt`, or `par` blocks — this causes rendering errors in Mermaid v11+. Either use the `+`/`-` shorthand or keep activation outside control flow blocks.

### C4 Diagrams (Enterprise Architecture)

For high-level software architecture following the C4 model. These are experimental in Mermaid.

Use `C4Context` for system landscape, `C4Container` for zooming into one system, `C4Component` for one container's internals.

### ER Diagrams (Database Schemas)

Crow's foot notation for entity relationships:
```
erDiagram
    USER ||--o{ ORDER : places
    ORDER ||--|{ LINE_ITEM : contains
    PRODUCT ||--o{ LINE_ITEM : "appears in"
```

Relationship markers: `||` exactly one, `o{` zero or more, `|{` one or more, `o|` zero or one.

### State Diagrams

For state machines and lifecycle modeling:
```
stateDiagram-v2
    [*] --> Pending
    Pending --> Processing : submit
    Processing --> Complete : success
    Processing --> Failed : error
    Failed --> Pending : retry
    Complete --> [*]
```

## AWS Architecture Patterns

### Color Palette for AWS Services

When styling AWS diagrams, use these colors for visual consistency:

| Category | Hex | Usage |
|----------|-----|-------|
| Compute | `#FF9900` | Lambda, ECS, EC2, Batch |
| Storage | `#3B48CC` | S3, EFS, EBS |
| Database | `#2E73B8` | RDS, DynamoDB, ElastiCache |
| Networking | `#8C4FFF` | VPC, ALB, Route 53, CloudFront |
| AI/ML | `#01A88D` | Bedrock, SageMaker, Comprehend |
| Events | `#E7157B` | EventBridge, SNS, SQS, Step Functions |
| AWS Dark (borders) | `#232F3E` | Consistent border color |

Always define classDefs at the end and apply them to relevant nodes.

### Common AWS Patterns

**VPC with public/private subnets:**
```
flowchart TD
    subgraph VPC["VPC"]
        subgraph pub["Public Subnet"]
            ALB[ALB]
            NAT[NAT Gateway]
        end
        subgraph priv["Private Subnet"]
            ECS[ECS Fargate]
            RDS[(RDS PostgreSQL)]
            REDIS[(ElastiCache)]
        end
    end
    Internet((Internet)) --> ALB
    ALB --> ECS
    ECS --> RDS
    ECS --> REDIS
    priv --> NAT --> Internet
```

**Event-driven pipeline:**
```
flowchart LR
    S3[S3 Upload] -->|notification| EB((EventBridge))
    EB -->|rule match| Lambda[Lambda]
    Lambda -->|heavy work| Batch[AWS Batch]
    Batch --> DDB[(DynamoDB)]
    Lambda -.->|simple| DDB
```

## Quality Checklist

Before outputting any diagram, verify:

- [ ] All node IDs are unique and descriptive (not just A, B, C — use meaningful names like `ALB`, `ECS`, `RDS`)
- [ ] Every edge connects two valid, declared nodes
- [ ] Subgraphs are properly opened and closed
- [ ] Labels are concise (under 30 characters ideally)
- [ ] Direction is appropriate (LR for pipelines, TD for hierarchies)
- [ ] Shape choices communicate component type
- [ ] AWS styling applied if it's an infrastructure diagram
- [ ] No syntax errors (no unescaped quotes in labels, proper bracket matching)
- [ ] No `activate`/`deactivate` inside `alt`/`else`/`opt`/`par` blocks — use `+`/`-` shorthand on arrows instead
- [ ] No ELK renderer directive unless user explicitly requested it
- [ ] Verify the diagram works without any `%%{init}%%` directives (add them only if needed and explain why)

## Rendering Environment Notes

Always mention to the user if their diagram requires special rendering:

- **GitHub/GitLab markdown**: Supports basic flowcharts, sequence, ER, state. Does NOT support custom icons, `architecture-beta`, or advanced theming.
- **architecture-beta with icons**: Requires HTML page with Iconify CDN or mmdc CLI with icon packs.
- **Custom theming**: Only works with `base` theme. Only hex colors work (no named colors).
- **ELK renderer**: For complex diagrams with overlapping edges, the ELK renderer can help — but it requires the `elkjs` package to be available. Do NOT include the ELK directive by default. Only suggest it if the user specifically asks about layout issues, and warn them it may not render in all environments.

## When to Read the Full Reference

Consult `references/mermaid-guide.md` when you need:
- The complete list of 30+ node shapes (Module 1)
- Detailed edge syntax including animation (Module 1)
- Subgraph styling and independent direction (Module 2)
- architecture-beta full syntax and junction patterns (Module 3)
- Iconify/AWS icon registration details (Module 4)
- Sequence diagram control flow patterns (Module 5)
- C4 diagram elements and boundaries (Module 6)
- Block diagram column layout (Module 7)
- Theme variable reference (Module 8)
- Complete AWS architecture recipes (Module 9)
- Best practices and limitations (Module 10)
