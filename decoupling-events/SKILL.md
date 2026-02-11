---
name: decoupling-events
description: "This skill should be used when building event-driven microservice architectures that use Apache Kafka or AWS MSK for inter-service event streaming and AWS SQS FIFO queues for intra-service task distribution. Provides production-grade guidance on dual-messaging-layer architecture, Kafka producer and consumer configuration with confluent-kafka, SQS FIFO queue task handlers, message envelope design, partition key strategies, error handling with poison pill prevention, async consumer lifecycle with worker pools and backpressure, and observability patterns."
---

# Event-Driven Microservice Decoupling with Kafka and SQS

## Overview

This skill provides production-tested patterns for building decoupled microservice architectures using a **dual messaging layer**: Apache Kafka (or AWS MSK) for inter-service event streaming and AWS SQS FIFO queues for intra-service task distribution. The architecture enables independently deployable services connected through well-defined event contracts, with fine-grained task parallelism and automatic retry within each service.

## When to Use

Apply this skill when:

- Designing event-driven communication between microservices using Kafka or AWS MSK
- Implementing async processing pipelines where services consume events and produce completion signals
- Setting up SQS FIFO queues for fan-out task distribution within a single service
- Configuring confluent-kafka producers and consumers for Python services
- Implementing message envelope standards and partition key strategies
- Building async consumer loops with worker pools and backpressure handling
- Adding error handling that prevents poison pill messages from blocking partitions
- Integrating Kafka/SQS consumers with FastAPI lifespan management
- Setting up health checks, monitoring, and distributed tracing for messaging
- Deciding whether to use Kafka, SQS, or both for a given communication pattern

**Trigger scenarios**:
- "How do I set up a Kafka consumer for my microservice?"
- "Should I use Kafka or SQS for task distribution?"
- "How do I prevent poison pill messages from blocking my consumer?"
- "What's the best way to handle errors in a Kafka consumer?"
- "How do I fan out work from a single Kafka event into parallel subtasks?"
- "How should I configure confluent-kafka for production?"
- "How do I integrate a Kafka consumer loop with FastAPI?"
- "What message format should I use across my services?"
- "How do I implement backpressure in my async consumer?"
- "What's the right retry strategy for SQS FIFO queues?"

## Configuration Placeholders

Before applying this skill, identify project-specific values:

**Service Names**:
- `{SERVICE_NAME}` — Name of the current service (e.g., `extraction-service`, `order-processor`)
- `{CONSUMER_GROUP}` — Kafka consumer group ID (e.g., `extraction-group`, `order-processing-group`)

**Kafka Topics**:
- `{TOPIC_STAGE_N_COMPLETE}` — Completion event for pipeline stage N (e.g., `order-validated`, `payment-processed`)
- `{TOPIC_ERRORS}` — Centralized error topic (e.g., `processing-errors`)
- `{TOPIC_DLQ}` — Dead letter queue topic (e.g., `{service}-dlq`)

**SQS Queues**:
- `{QUEUE_URL}` — SQS FIFO queue URL for task distribution
- `{DLQ_URL}` — SQS dead letter queue URL

**Entity**:
- `{ENTITY_ID}` — Primary correlation ID for your domain (e.g., `doc_id`, `order_id`, `user_id`)

Replace these placeholders throughout the reference documents with your project values.

## How to Use This Skill

### Implementing Kafka Producers and Consumers

For confluent-kafka configuration, topic design, and partition strategies:
- Consult `references/01-kafka-producer-consumer.md` for producer/consumer classes, SSL/MSK setup, topic design principles, and topic configuration tiers

**Example questions**:
- "How do I configure an idempotent Kafka producer?"
- "What consumer settings do I need for long-running tasks?"
- "How many partitions should my topic have?"

### Implementing SQS Task Distribution

For SQS FIFO queue handlers, parallel processing, and DLQ management:
- Consult `references/02-sqs-task-distribution.md` for the TaskQueueHandler class, enqueue/dequeue patterns, MessageGroupId strategy, and DLQ inspection

**Example questions**:
- "How do I fan out work from a Kafka event into SQS tasks?"
- "How does MessageGroupId enable parallel processing?"
- "How do I inspect failed messages in the DLQ?"

### Designing Message Contracts

For message envelopes, Kafka headers, and partition key strategies:
- Consult `references/03-message-design.md` for the standard message envelope, header conventions, and partition key patterns

**Example questions**:
- "What fields should every message include?"
- "How do I use Kafka headers for distributed tracing?"
- "What partition key should I use for different event types?"

### Implementing Error Handling

For error categories, retry logic, and poison pill prevention:
- Consult `references/04-error-handling-resilience.md` for error classification, retry configuration, Kafka commit strategy, and SQS retry flow

**Example questions**:
- "How do I prevent poison pill messages?"
- "When should I commit after an error?"
- "What retry strategy should I use?"

### Building Consumer Lifecycle

For async worker pools, backpressure, and FastAPI integration:
- Consult `references/05-consumer-lifecycle.md` for the AsyncKafkaService class, SQS polling loop, FastAPI lifespan hooks, and concurrency models

**Example questions**:
- "How do I integrate a Kafka consumer with FastAPI?"
- "How do I implement backpressure?"
- "How do I gracefully shut down consumers?"

### Production Readiness

For observability, configuration, and deployment checklists:
- Consult `references/06-production-checklist.md` for health checks, monitoring, distributed tracing, environment variable conventions, and the complete production checklist

**Example questions**:
- "What health check endpoints do I need?"
- "How should I structure my environment variables?"
- "What's the production readiness checklist for Kafka?"

## Key Architectural Principles

1. **Dual Messaging Layer** — Kafka for inter-service event streaming (durable, replayable, fan-out via consumer groups). SQS FIFO for intra-service task distribution (per-task retry, DLQ, message-group parallelism).

2. **Manual Offset Commit** — Disable auto-commit. Commit only after successful processing or error publishing. Prevents data loss on consumer failure.

3. **Always Commit After Error Handling** — On permanent failures, publish to error topic, then commit. Uncommitted messages become poison pills that block the partition forever.

4. **Idempotent Producers** — Enable `enable.idempotence: True` with `acks: all` for exactly-once semantics at the producer level.

5. **SQS Delete-Only-On-Success** — Never delete SQS messages on failure. Let visibility timeout return them to the queue for automatic retry. DLQ catches messages after max retries.

6. **Cooperative-Sticky Rebalancing** — Use `partition.assignment.strategy: cooperative-sticky` to minimize disruption during consumer group rebalances.

7. **Fail Fast, Surface Errors** — No silent defaults, no swallowed exceptions. Errors must surface immediately with structured logging and error topic publishing.

## Decision Framework

```
Is this communication between different services?
  YES --> Use Kafka
       Does the downstream need to fan-out into parallel subtasks?
            YES --> Kafka triggers the service, service uses SQS internally
            NO  --> Kafka only

Is this distributing work within a single service?
  YES --> Use SQS FIFO
       Do tasks need independent retry and error isolation?
            YES --> SQS with DLQ
            NO  --> asyncio.Queue or similar in-process queue
```

## Quick Reference: Key Settings

| Setting | Value | Rationale |
|---------|-------|-----------|
| `acks` | `all` | All ISR replicas acknowledge |
| `enable.idempotence` | `True` | Prevent duplicate messages |
| `compression.type` | `snappy` | Efficient compression |
| `enable.auto.commit` | `False` | Manual commit after processing |
| `max.poll.interval.ms` | `1800000` | 30 min for long tasks |
| `session.timeout.ms` | `45000` | 45s failure detection |
| `heartbeat.interval.ms` | `15000` | 1/3 of session timeout |
| `partition.assignment.strategy` | `cooperative-sticky` | Minimal rebalance disruption |
| Standard topic retention | 7 days | Normal event topics |
| Error/DLQ topic retention | 30 days | Post-mortem analysis |
| SQS VisibilityTimeout | 900s (15 min) | Long-running task window |
| SQS WaitTimeSeconds | 5s | Long polling to reduce API calls |

---

**Version**: 1.0
**Last Updated**: 2026-02-10
**Production Status**: Battle-tested in multi-service processing pipelines
