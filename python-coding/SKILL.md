---
name: python-coding
description: This skill should be used when developing Python applications requiring production-grade architecture, async/await patterns, or enterprise-level code quality. Provides guidance on Clean Architecture, domain-driven design, Pydantic modeling, structured logging, and async concurrency patterns for Python 3.11+.
---

# Python Coding Best Practices

## Purpose

This skill provides production-grade Python development guidance based on proven patterns from enterprise microservices. It covers architectural patterns, async/await techniques, type-safe domain modeling, and production engineering practices applicable to any Python 3.11+ project.

## When to Use This Skill

This skill should be used when:
- Starting a new Python project and need architectural guidance
- Implementing async/await patterns for high-concurrency applications
- Designing domain models with Pydantic for type safety
- Setting up production logging, observability, and error handling
- Organizing code for maintainability and testability
- Building microservices or standalone services
- Migrating from sync to async Python code
- Implementing clean architecture or hexagonal architecture patterns
- Need guidance on Python code organization and project structure
- Establishing best practices for a Python team or project

## How to Use This Skill

### Architectural Guidance

For questions about code organization, architecture patterns, or project structure:
- Consult `references/architectural-patterns.md` for Clean Architecture, DDD, and Hexagonal Architecture
- Consult `references/code-organization.md` for module structure and file organization strategies

**Example questions:**
- "How should I structure a Python microservice?"
- "What's the difference between Clean Architecture and Hexagonal Architecture?"
- "How do I implement dependency injection in Python?"
- "Should I use feature-based or layer-based organization?"

### Async/Await Development

For implementing concurrent Python applications:
- Consult `references/async-patterns.md` for producer-consumer patterns, background tasks, and async/sync bridges
- Includes error handling, graceful shutdown, and task lifecycle management

**Example questions:**
- "How do I implement async producer-consumer pattern?"
- "How do I bridge sync and async code with ThreadPoolExecutor?"
- "What's the best way to handle graceful shutdown in async applications?"
- "How do I manage concurrent tasks with controlled concurrency?"

### Type-Safe Domain Modeling

For implementing Pydantic models and type hints:
- Consult `references/pydantic-patterns.md` for validation, custom validators, and serialization patterns
- Includes best practices for type annotations and API contracts

**Example questions:**
- "How do I create Pydantic models with custom validation?"
- "What's the best way to handle nested models?"
- "How do I serialize Pydantic models to JSON?"
- "How do I use Pydantic for application settings?"

### Production Engineering

For logging, observability, and error handling:
- Consult `references/production-engineering.md` for structured logging, distributed tracing, and fail-fast patterns
- Includes configuration management and secret handling strategies

**Example questions:**
- "How do I set up structured JSON logging for DataDog?"
- "How do I implement distributed tracing with DataDog APM?"
- "What's the fail-fast error handling pattern?"
- "How do I manage configuration and secrets in production?"

### Code Organization

For project structure and module design:
- Consult `references/code-organization.md` for file organization, naming conventions, and module design guidelines

**Example questions:**
- "How should I organize my Python project?"
- "When should I split a module into multiple files?"
- "What are the best practices for naming files and classes?"
- "How do I avoid circular imports?"

## Key Principles

All guidance follows these core principles:

1. **Fail-Fast Error Handling** - No silent failures, no default fallbacks. Errors should fail immediately and explicitly.

2. **Type Safety** - Comprehensive type hints and Pydantic validation at system boundaries.

3. **Separation of Concerns** - Clean boundaries between domain, application, and infrastructure layers.

4. **Async First** - Non-blocking I/O for all network operations and concurrent processing.

5. **Observable by Default** - Structured JSON logging and distributed tracing for production visibility.

6. **Configuration via Environment** - All configuration through environment variables (12-factor app compliance).

7. **Testability** - Code organized to support unit and integration testing through dependency injection.

## Implementation Workflow

When starting a new Python project or refactoring existing code:

### 1. Project Setup

- Review `references/code-organization.md` for appropriate project structure
- Review `references/architectural-patterns.md` for architectural approach (Clean Architecture, DDD, etc.)
- Set up structured logging first using `references/production-engineering.md`
- Define domain models with Pydantic using `references/pydantic-patterns.md`

### 2. Development

- Implement domain logic with zero external dependencies (infrastructure-agnostic)
- Create infrastructure adapters that implement domain interfaces
- Use dependency injection for all external dependencies (databases, APIs, message queues)
- Follow async patterns from `references/async-patterns.md` for concurrent operations

### 3. Production Readiness

- Implement structured JSON logging with trace correlation
- Set up graceful shutdown with proper resource cleanup
- Configure observability (DataDog APM, metrics)
- Validate error handling follows fail-fast principles
- Ensure all configuration via environment variables

## Decision Trees

### Choosing Architecture Pattern

**Use Clean Architecture when:**
- Building applications with complex business logic
- Need to swap infrastructure (database, message queue)
- Want to test business logic without external dependencies
- Building microservices or modular monoliths

**Use Simple Structure when:**
- Building simple scripts or small utilities
- Prototype or proof-of-concept projects
- No complex business logic required

### Choosing Async vs Sync

**Use async/await when:**
- Building I/O-bound applications (APIs, microservices)
- Need high concurrency (many simultaneous connections)
- Working with async libraries (aiohttp, asyncio)

**Use sync when:**
- CPU-bound processing
- Working primarily with sync libraries
- Simple scripts or batch processing

### Organizing Code

**Use feature-based organization when:**
- Building larger applications with distinct features
- Features may be extracted to separate services
- Team is organized by feature/domain

**Use layer-based organization when:**
- Building small services with simple structure
- Team is comfortable with traditional MVC-style organization

## Best Practices Summary

### Architecture
- Domain layer has zero infrastructure dependencies
- Infrastructure implements domain interfaces
- Use dependency injection throughout
- Follow Single Responsibility Principle

### Async/Await
- Use `asyncio.Queue` for producer-consumer patterns
- Track all background tasks for graceful shutdown
- Bridge sync code with `ThreadPoolExecutor`
- Always set timeouts on async operations

### Type Safety
- Use Pydantic models for all data validation
- Add type hints to all function signatures
- Validate at system boundaries
- Use computed fields for derived data

### Production
- Structured JSON logging to stdout
- Distributed tracing with correlation IDs
- Fail-fast error handling
- Configuration via environment variables
- Proper resource cleanup on shutdown

### Organization
- Keep files < 500 lines
- Keep functions < 50 lines
- Use snake_case for files, PascalCase for classes
- One responsibility per file
- Avoid circular imports

## Anti-Patterns to Avoid

- **No silent failures** - Never use `try/except: pass` or default fallbacks that mask errors
- **No god objects** - Split large files (>500 lines) into focused modules
- **No circular imports** - Restructure dependencies or use interfaces
- **No blocking in async** - Use async libraries or ThreadPoolExecutor for sync operations
- **No mutable defaults** - Use `Field(default_factory=list)` instead of `= []`
- **No infrastructure in domain** - Keep domain layer infrastructure-agnostic

## Additional Resources

Each reference file contains detailed patterns, code examples, and decision guidance:

- **architectural-patterns.md** - Clean Architecture, DDD, Hexagonal, Dependency Injection, Strategy, Factory
- **async-patterns.md** - Producer-Consumer, Background Tasks, Async/Sync Bridge, Graceful Shutdown, Error Recovery
- **production-engineering.md** - Structured Logging, Distributed Tracing, Fail-Fast, Configuration, Observability
- **code-organization.md** - Project Structure, Feature vs Layer Organization, Module Design, Naming Conventions
- **pydantic-patterns.md** - Model Definition, Validators, Serialization, Settings, Advanced Patterns

## Getting Started

To apply these patterns to your Python project:

1. **Assess current state** - Identify areas needing improvement (architecture, async, types, logging)
2. **Choose patterns** - Select appropriate patterns from reference files based on project needs
3. **Implement incrementally** - Apply patterns one at a time, starting with highest impact
4. **Verify** - Test changes thoroughly
5. **Document** - Update project documentation with architectural decisions

**For new projects:**
- Start with proper structure from `code-organization.md`
- Define domain models with Pydantic
- Set up logging and observability first
- Build infrastructure adapters around domain interfaces

**For existing projects:**
- Identify technical debt areas
- Refactor one module at a time
- Add type hints and validation gradually
- Improve logging and observability
- Introduce async patterns where beneficial
