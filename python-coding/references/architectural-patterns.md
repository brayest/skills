# Architectural Patterns for Python Applications

## Clean Architecture / Hexagonal Architecture

### Overview

Clean Architecture separates software into layers with strict dependency rules: dependencies point inward toward the domain. The domain (business logic) has zero dependencies on infrastructure, enabling testability, flexibility, and clarity.

**Core Principle:** Domain logic should be independent of frameworks, UI, databases, and external agencies.

### Recommended Layer Structure

```
project_name/
├── domain/              # Business Logic (Core - No External Dependencies)
│   ├── models.py       # Domain models (Pydantic/dataclasses)
│   ├── services.py     # Domain services (business rules)
│   ├── interfaces.py   # Abstract interfaces for infrastructure
│   └── exceptions.py   # Domain-specific exceptions
├── application/         # Use Cases / Orchestration
│   ├── use_cases.py    # Application services
│   ├── dto.py          # Data transfer objects
│   └── commands.py     # Command/query objects
├── infrastructure/      # External Dependencies (Adapters)
│   ├── database/       # Database adapters
│   │   ├── repositories.py
│   │   └── migrations/
│   ├── messaging/      # Message queue handlers
│   │   ├── kafka_client.py
│   │   └── sqs_handler.py
│   ├── clients/        # External API clients
│   │   ├── auth_client.py
│   │   └── third_party_api.py
│   ├── storage/        # File storage (S3, local)
│   └── config/         # Configuration management
└── shared/             # Cross-cutting Concerns
    ├── logging.py
    ├── observability.py
    └── utils.py
```

### Dependency Rules

1. **Domain Layer** - Zero external dependencies
   - No imports from `infrastructure/`, `application/`, or third-party frameworks
   - Pure Python with business logic only
   - Define interfaces that infrastructure must implement

2. **Application Layer** - Depends only on domain
   - Orchestrates domain services
   - Implements use cases
   - Can import from `domain/`, not `infrastructure/`

3. **Infrastructure Layer** - Implements domain interfaces
   - Can import from `domain/` (to implement interfaces)
   - Handles external dependencies (databases, APIs, message queues)
   - Adapts external systems to domain interfaces

4. **Shared Layer** - Accessible by all layers
   - Utility functions
   - Logging configuration
   - No business logic

### Example: Domain Interface Pattern

**Define interface in domain layer:**

```python
# domain/interfaces.py
from abc import ABC, abstractmethod
from typing import Optional
from domain.models import User

class UserRepository(ABC):
    """Abstract interface for user persistence."""

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Retrieve user by ID."""
        pass

    @abstractmethod
    async def save(self, user: User) -> None:
        """Persist user to storage."""
        pass
```

**Implement in infrastructure layer:**

```python
# infrastructure/database/repositories.py
from domain.interfaces import UserRepository
from domain.models import User
import boto3

class DynamoDBUserRepository(UserRepository):
    """DynamoDB implementation of UserRepository."""

    def __init__(self, table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    async def get_by_id(self, user_id: str) -> Optional[User]:
        response = self.table.get_item(Key={'userId': user_id})
        if 'Item' not in response:
            return None
        return User(**response['Item'])

    async def save(self, user: User) -> None:
        self.table.put_item(Item=user.model_dump())
```

**Use in application layer:**

```python
# application/use_cases.py
from domain.interfaces import UserRepository
from domain.models import User

class GetUserUseCase:
    """Retrieve user by ID."""

    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    async def execute(self, user_id: str) -> User:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        return user
```

### Benefits

- **Testability:** Mock infrastructure with simple in-memory implementations
- **Flexibility:** Swap DynamoDB for PostgreSQL without touching business logic
- **Clarity:** Clear boundaries between layers
- **Maintainability:** Changes to infrastructure don't break domain

---

## Dependency Injection Pattern

### Overview

Dependency Injection (DI) provides dependencies to objects instead of having objects create them internally. This enables testability, flexibility, and loose coupling.

### Constructor-Based Injection

**Recommended approach for Python:**

```python
class UserService:
    """Service for user operations."""

    def __init__(
        self,
        user_repository: UserRepository,
        email_client: EmailClient,
        logger: logging.Logger
    ):
        self.user_repository = user_repository
        self.email_client = email_client
        self.logger = logger

    async def register_user(self, email: str, name: str) -> User:
        """Register new user and send welcome email."""
        user = User(email=email, name=name)
        await self.user_repository.save(user)
        await self.email_client.send_welcome(user)
        self.logger.info(f"User registered: {user.id}")
        return user
```

### Manual Dependency Wiring

For smaller projects, manually wire dependencies at application startup:

```python
# main.py
import asyncio
from infrastructure.database.repositories import DynamoDBUserRepository
from infrastructure.clients.email_client import SendGridEmailClient
from application.use_cases import UserService
from shared.logging import get_logger

async def main():
    # Create dependencies
    user_repository = DynamoDBUserRepository(table_name='users')
    email_client = SendGridEmailClient(api_key=os.getenv('SENDGRID_API_KEY'))
    logger = get_logger(__name__)

    # Inject dependencies
    user_service = UserService(
        user_repository=user_repository,
        email_client=email_client,
        logger=logger
    )

    # Use service
    await user_service.register_user('user@example.com', 'John Doe')

if __name__ == "__main__":
    asyncio.run(main())
```

### Framework-Based Injection (FastAPI)

For web applications, use framework DI:

```python
# dependencies.py
from fastapi import Depends
from infrastructure.database.repositories import DynamoDBUserRepository
from domain.interfaces import UserRepository

def get_user_repository() -> UserRepository:
    """Dependency provider for user repository."""
    return DynamoDBUserRepository(table_name='users')

# routes.py
from fastapi import APIRouter, Depends
from application.use_cases import GetUserUseCase

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    user_repository: UserRepository = Depends(get_user_repository)
):
    use_case = GetUserUseCase(user_repository)
    user = await use_case.execute(user_id)
    return user
```

### Benefits

- **Testability:** Easily swap real dependencies with mocks
- **Flexibility:** Change implementations without modifying code
- **Clarity:** Dependencies explicit in constructor

---

## Strategy Pattern

### Overview

Strategy Pattern defines a family of algorithms, encapsulates each one, and makes them interchangeable. The algorithm varies independently from clients that use it.

### When to Use

- Multiple ways to perform an operation
- Behavior should be selected at runtime
- Avoid large if/elif/else chains

### Implementation

**Define strategy interface:**

```python
# domain/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Any

class AggregationStrategy(ABC):
    """Interface for data aggregation strategies."""

    @abstractmethod
    def aggregate(self, values: List[Any]) -> Any:
        """Aggregate multiple values into single result."""
        pass
```

**Implement concrete strategies:**

```python
# domain/strategies.py
from domain.interfaces import AggregationStrategy
from typing import List, Any

class SumStrategy(AggregationStrategy):
    """Sum all numeric values."""

    def aggregate(self, values: List[Any]) -> float:
        return sum(float(v) for v in values if v is not None)

class MaxStrategy(AggregationStrategy):
    """Return maximum value."""

    def aggregate(self, values: List[Any]) -> Any:
        return max(v for v in values if v is not None)

class CombineStrategy(AggregationStrategy):
    """Combine all string values."""

    def aggregate(self, values: List[str]) -> str:
        return " | ".join(v for v in values if v)
```

**Use with context:**

```python
# application/services.py
from domain.interfaces import AggregationStrategy
from domain.strategies import SumStrategy, MaxStrategy, CombineStrategy

class DataAggregator:
    """Aggregates data using configurable strategies."""

    STRATEGIES = {
        'sum': SumStrategy(),
        'max': MaxStrategy(),
        'combine': CombineStrategy()
    }

    def aggregate_field(
        self,
        field_name: str,
        values: List[Any],
        strategy_name: str
    ) -> Any:
        """Aggregate field values using specified strategy."""
        strategy = self.STRATEGIES.get(strategy_name)
        if not strategy:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        return strategy.aggregate(values)
```

**Configuration-driven strategy selection:**

```json
{
  "fields": {
    "total_hours": {"strategy": "sum"},
    "max_temperature": {"strategy": "max"},
    "descriptions": {"strategy": "combine"}
  }
}
```

```python
# Usage
import json

config = json.load(open('config.json'))
aggregator = DataAggregator()

for field_name, field_config in config['fields'].items():
    values = get_values(field_name)
    result = aggregator.aggregate_field(
        field_name,
        values,
        field_config['strategy']
    )
```

### Benefits

- **Flexibility:** Add new strategies without modifying existing code
- **Testability:** Test each strategy in isolation
- **Configuration:** Select behavior at runtime via configuration

---

## Factory Pattern

### Overview

Factory Pattern provides an interface for creating objects without specifying exact class. Useful when object creation is complex or when the type should be determined at runtime.

### Simple Factory

```python
# infrastructure/factories.py
from domain.interfaces import UserRepository
from infrastructure.database.repositories import (
    DynamoDBUserRepository,
    PostgreSQLUserRepository,
    InMemoryUserRepository
)

class RepositoryFactory:
    """Factory for creating repository instances."""

    @staticmethod
    def create_user_repository(repo_type: str, **kwargs) -> UserRepository:
        """
        Create user repository based on type.

        Args:
            repo_type: Type of repository ('dynamodb', 'postgresql', 'memory')
            **kwargs: Repository-specific configuration

        Returns:
            UserRepository implementation
        """
        if repo_type == 'dynamodb':
            return DynamoDBUserRepository(
                table_name=kwargs['table_name']
            )
        elif repo_type == 'postgresql':
            return PostgreSQLUserRepository(
                connection_string=kwargs['connection_string']
            )
        elif repo_type == 'memory':
            return InMemoryUserRepository()
        else:
            raise ValueError(f"Unknown repository type: {repo_type}")
```

**Usage:**

```python
# main.py
import os
from infrastructure.factories import RepositoryFactory

# Create repository based on environment
repo_type = os.getenv('REPOSITORY_TYPE', 'memory')
user_repository = RepositoryFactory.create_user_repository(
    repo_type=repo_type,
    table_name=os.getenv('DYNAMODB_TABLE_NAME'),
    connection_string=os.getenv('DATABASE_URL')
)
```

### Factory with Registration

For extensibility:

```python
# infrastructure/factories.py
from typing import Dict, Type, Callable
from domain.interfaces import UserRepository

class UserRepositoryRegistry:
    """Registry for user repository implementations."""

    _factories: Dict[str, Callable[..., UserRepository]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., UserRepository]):
        """Register repository factory."""
        cls._factories[name] = factory

    @classmethod
    def create(cls, name: str, **kwargs) -> UserRepository:
        """Create repository by name."""
        factory = cls._factories.get(name)
        if not factory:
            raise ValueError(f"Unknown repository: {name}")
        return factory(**kwargs)

# Register implementations
UserRepositoryRegistry.register(
    'dynamodb',
    lambda **kw: DynamoDBUserRepository(table_name=kw['table_name'])
)
UserRepositoryRegistry.register(
    'postgresql',
    lambda **kw: PostgreSQLUserRepository(connection_string=kw['connection_string'])
)

# Usage
repository = UserRepositoryRegistry.create(
    'dynamodb',
    table_name='users'
)
```

### Benefits

- **Encapsulation:** Hide object creation complexity
- **Flexibility:** Switch implementations via configuration
- **Testability:** Easily inject test doubles

---

## Domain-Driven Design (DDD)

### Core Concepts

**Entity:** Object with unique identity that persists over time
**Value Object:** Immutable object defined by its attributes
**Aggregate:** Cluster of entities/value objects treated as single unit
**Repository:** Interface for accessing aggregates
**Domain Service:** Stateless service for domain operations that don't belong to entities

### Entity Example

```python
# domain/models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid

class Order(BaseModel):
    """Order entity with unique identity."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str
    total: float
    status: str = 'pending'
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def complete(self) -> None:
        """Mark order as complete."""
        if self.status != 'pending':
            raise ValueError(f"Cannot complete order in {self.status} status")
        self.status = 'completed'

    def cancel(self) -> None:
        """Cancel order."""
        if self.status == 'completed':
            raise ValueError("Cannot cancel completed order")
        self.status = 'cancelled'
```

### Value Object Example

```python
# domain/models.py
from pydantic import BaseModel, Field

class Money(BaseModel):
    """Value object representing monetary amount."""

    amount: float = Field(ge=0)
    currency: str = Field(pattern='^[A-Z]{3}$')  # ISO 4217

    def add(self, other: 'Money') -> 'Money':
        """Add money values."""
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def multiply(self, factor: float) -> 'Money':
        """Multiply amount by factor."""
        return Money(amount=self.amount * factor, currency=self.currency)

    class Config:
        frozen = True  # Immutable
```

### Domain Service Example

```python
# domain/services.py
from domain.models import Order, Money

class OrderPricingService:
    """Domain service for order pricing calculations."""

    def calculate_total(
        self,
        subtotal: Money,
        tax_rate: float,
        discount_percentage: float = 0
    ) -> Money:
        """Calculate order total with tax and discount."""
        # Apply discount
        if discount_percentage > 0:
            discount_amount = subtotal.multiply(discount_percentage / 100)
            subtotal = Money(
                amount=subtotal.amount - discount_amount.amount,
                currency=subtotal.currency
            )

        # Apply tax
        tax_amount = subtotal.multiply(tax_rate)
        total = subtotal.add(tax_amount)

        return total
```

### Repository Pattern

```python
# domain/interfaces.py
from abc import ABC, abstractmethod
from typing import Optional, List
from domain.models import Order

class OrderRepository(ABC):
    """Abstract repository for Order aggregate."""

    @abstractmethod
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        pass

    @abstractmethod
    async def save(self, order: Order) -> None:
        pass

    @abstractmethod
    async def find_by_customer(self, customer_id: str) -> List[Order]:
        pass

    @abstractmethod
    async def delete(self, order_id: str) -> None:
        pass
```

### Benefits

- **Ubiquitous Language:** Business concepts directly in code
- **Rich Domain Models:** Business rules enforced by domain objects
- **Maintainability:** Complex domain logic organized clearly

---

## Decision Guide: When to Use Each Pattern

### Use Clean Architecture When:
- Building applications with complex business logic
- Need to swap infrastructure (database, message queue)
- Want to test business logic without external dependencies
- Building microservices or modular monoliths

### Use Dependency Injection When:
- Need testability (mock dependencies)
- Want flexibility to swap implementations
- Building applications with multiple components
- Following Clean Architecture or Hexagonal Architecture

### Use Strategy Pattern When:
- Multiple algorithms for same operation
- Behavior should be selected at runtime
- Want to avoid complex if/elif chains
- Configuration should drive behavior

### Use Factory Pattern When:
- Object creation is complex
- Type should be determined at runtime
- Want to hide creation details from clients
- Need centralized object creation

### Use Domain-Driven Design When:
- Domain is complex with rich business rules
- Need ubiquitous language between developers and domain experts
- Building long-lived applications
- Domain logic is core competitive advantage

---

## Anti-Patterns to Avoid

### ❌ God Objects
**Problem:** Single class knows/does too much

**Symptoms:**
- File >1000 lines
- Class with >20 methods
- Unclear single responsibility

**Solution:** Split into smaller, focused classes

### ❌ Circular Dependencies
**Problem:** Module A imports module B which imports module A

**Solution:**
- Use dependency injection
- Extract interface to separate module
- Restructure layers (domain → application → infrastructure)

### ❌ Anemic Domain Models
**Problem:** Domain models are just data containers with no behavior

```python
# ❌ Bad - Anemic model
class Order:
    id: str
    total: float
    status: str

# Business logic in service layer
def complete_order(order: Order):
    if order.status != 'pending':
        raise ValueError("Cannot complete")
    order.status = 'completed'
```

**Solution:** Put business logic in domain models

```python
# ✅ Good - Rich domain model
class Order:
    id: str
    total: float
    status: str

    def complete(self):
        """Mark order as complete."""
        if self.status != 'pending':
            raise ValueError("Cannot complete")
        self.status = 'completed'
```

### ❌ Infrastructure in Domain
**Problem:** Domain layer imports database, API clients, etc.

**Solution:** Define interfaces in domain, implement in infrastructure
