# Claude Code Skills

A collection of production-grade [Claude Code skills](https://docs.anthropic.com/en/docs/claude-code/skills) that encode specialized knowledge, workflows, and patterns for building AI-powered platforms and infrastructure.

Skills are modular packages that extend Claude Code with domain expertise — think of them as onboarding guides that transform a general-purpose agent into a specialized one. Each skill follows a progressive disclosure design: metadata is always loaded (~100 words), the SKILL.md body loads when triggered (<5k words), and reference files load on demand.

## Skills

### Core Platform

| Skill | Purpose | Use When |
|-------|---------|----------|
| [python-coding](python-coding/) | Production Python patterns — Clean Architecture, async/await, Pydantic, structured logging, code organization | Starting a Python service, implementing async patterns, setting up domain models, configuring logging/tracing |
| [opensearch-llamaindex-rag](opensearch-llamaindex-rag/) | Hybrid RAG with OpenSearch (BM25 + KNN) and LlamaIndex — dual-service architecture, HNSW indexing, post-processing pipelines | Building RAG pipelines, implementing hybrid search, designing chunking strategies, tuning retrieval accuracy |
| [docling-ray](docling-ray/) | Document extraction combining Docling (PDF/DOCX/PPTX parsing) with Ray (GPU-accelerated parallel processing) | Building parallel document extraction services, optimizing OCR workloads, integrating Docling with async APIs |
| [decoupling-events](decoupling-events/) | Event-driven architecture — Kafka/MSK for inter-service streaming, SQS FIFO for intra-service task distribution | Designing microservice communication, implementing producer-consumer pipelines, setting up SQS fan-out |
| [llm-observability](llm-observability/) | LLM tracing and evaluation — span instrumentation, 9-metric evaluation framework, Datadog LLM Observability | Adding observability to LLM pipelines, implementing evaluation metrics, setting up distributed tracing |

### Infrastructure & Operations

| Skill | Purpose | Use When |
|-------|---------|----------|
| [local-development](local-development/) | Docker Compose dev environment — API + UI + DB orchestration, one-command setup, AWS credential handling | Scaffolding new projects, adding Docker Compose, configuring local AWS integration, setting up migrations |
| [vault-kubernetes](vault-kubernetes/) | HashiCorp Vault + K8s secret management — service account auth, `hvac` client, Helm chart configuration | Adding Vault to K8s services, implementing VaultSecretManager, debugging auth failures |
| [beam2-cert-manager](beam2-cert-manager/) | SSL/TLS certificate renewal workflow — CSR generation, Vault secret updates, field preservation | Renewing client certificates (Corteva, Anthem, Deloitte, etc.) stored in HashiCorp Vault |

### Specialized

| Skill | Purpose | Use When |
|-------|---------|----------|
| [learning-design](learning-design/) | Cognitive science learning systems — ZPD, Bloom's taxonomy, scaffolding, spaced repetition, module-based architecture | Designing progressive learning platforms, building educational tools, validating curricula |
| [skill-creator](skill-creator/) | Meta skill for building new skills — anatomy, progressive disclosure, 6-step creation process | Creating or updating Claude Code skills |

## Architecture Overview

The core skills map to a document processing and intelligent extraction platform:

```
                                    ┌─────────────────────┐
                                    │   python-coding     │
                                    │   (all services)    │
                                    └─────────────────────┘

  Documents ──▶ [docling-ray] ──▶ [decoupling-events] ──▶ [opensearch-llamaindex-rag]
                 Docling + Ray      Kafka (inter-service)    Hybrid Search (BM25 + KNN)
                 GPU extraction     SQS (intra-service)      LlamaIndex orchestration
                                         │                          │
                                         └──────────┬───────────────┘
                                                    │
                                         ┌──────────▼──────────┐
                                         │  llm-observability  │
                                         │  Tracing + Eval     │
                                         └─────────────────────┘

  Infrastructure:
    [local-development]     Docker Compose dev environment
    [vault-kubernetes]      Secrets management in K8s
    [beam2-cert-manager]    Client certificate renewals
```

## Skill Structure

Each skill follows a consistent layout:

```
skill-name/
├── SKILL.md              # Entry point — metadata, triggers, workflows, decision trees
└── references/           # Deep-dive docs loaded on demand
    ├── 01-topic.md
    ├── 02-topic.md
    └── ...
```

Some skills also include:
- `scripts/` — Executable automation (validation, scaffolding)
- `assets/` — Templates and files used in output (Dockerfiles, configs)

## Shared Principles

All skills enforce these patterns:

- **Fail fast, fail loud** — No silent failures, no default fallbacks. Errors surface immediately with structured logging.
- **No AWS access keys** — Local dev uses `~/.aws` profile mounts. Cloud uses IAM Roles. No exceptions.
- **Observable by default** — Structured JSON logging, distributed tracing, trace-log correlation.
- **Type safety** — Pydantic models at system boundaries, comprehensive type hints.
- **Async first** — Non-blocking I/O for all network operations.
- **Configuration via environment** — 12-factor app compliance, Pydantic Settings validation at startup.

## Installation

Skills are installed into Claude Code's configuration. Each skill directory can be registered as a skill source following the [Claude Code skills documentation](https://docs.anthropic.com/en/docs/claude-code/skills).

## Creating New Skills

Use the `skill-creator` skill to build new ones:

```bash
# Scaffold a new skill
skill-creator/scripts/init_skill.py my-new-skill --path ./

# Validate and package
skill-creator/scripts/package_skill.py ./my-new-skill
```
