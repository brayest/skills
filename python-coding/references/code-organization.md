# Code Organization Patterns for Python Applications

## Project Structure Templates

### Microservice / API Service

```
my_service/
├── domain/                     # Business logic (no external dependencies)
│   ├── __init__.py
│   ├── models.py              # Domain models (Pydantic/dataclasses)
│   ├── services.py            # Domain services
│   ├── interfaces.py          # Abstract interfaces
│   └── exceptions.py          # Domain-specific exceptions
├── application/                # Use cases / orchestration
│   ├── __init__.py
│   ├── use_cases.py           # Application services
│   ├── dto.py                 # Data transfer objects
│   └── commands.py            # Command/query objects
├── infrastructure/             # External dependencies
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── repositories.py
│   │   └── migrations/
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── kafka_client.py
│   │   └── sqs_handler.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── auth_client.py
│   │   └── third_party_api.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── s3_client.py
│   │   └── cache.py
│   └── config/
│       ├── __init__.py
│       └── settings.py
├── shared/                     # Cross-cutting concerns
│   ├── __init__.py
│   ├── logging.py
│   ├── observability.py
│   └── utils.py
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── main.py                     # Entry point
├── requirements.txt            # Dependencies
├── Dockerfile
└── README.md
```

### Library / Package

```
my_package/
├── my_package/                 # Main package
│   ├── __init__.py
│   ├── core/                  # Core functionality
│   │   ├── __init__.py
│   │   └── base.py
│   ├── utils/                 # Utilities
│   │   ├── __init__.py
│   │   └── helpers.py
│   └── exceptions.py
├── tests/
│   ├── __init__.py
│   └── test_core.py
├── docs/                       # Documentation
│   └── index.md
├── pyproject.toml             # Project configuration
├── README.md
└── LICENSE
```

### Data Science / ML Project

```
ml_project/
├── data/                       # Data files
│   ├── raw/
│   ├── processed/
│   └── external/
├── notebooks/                  # Jupyter notebooks
│   ├── 01_exploration.ipynb
│   └── 02_modeling.ipynb
├── src/                        # Source code
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   └── dataset.py
│   ├── features/
│   │   ├── __init__.py
│   │   └── engineering.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── train.py
│   └── visualization/
│       ├── __init__.py
│       └── plots.py
├── tests/
├── pyproject.toml
└── README.md
```

---

## Feature-Based vs Layer-Based Organization

### Layer-Based Organization (Traditional)

**Structure:**
```
app/
├── models/              # All models
│   ├── user.py
│   ├── order.py
│   └── product.py
├── services/            # All services
│   ├── user_service.py
│   ├── order_service.py
│   └── product_service.py
└── repositories/        # All repositories
    ├── user_repo.py
    ├── order_repo.py
    └── product_repo.py
```

**Problems:**
- Related code scattered across directories
- Hard to extract features to separate services
- Unclear module boundaries

### Feature-Based Organization (Recommended)

**Structure:**
```
app/
├── users/               # User feature
│   ├── models.py
│   ├── service.py
│   ├── repository.py
│   └── routes.py
├── orders/              # Order feature
│   ├── models.py
│   ├── service.py
│   ├── repository.py
│   └── routes.py
└── products/            # Product feature
    ├── models.py
    ├── service.py
    ├── repository.py
    └── routes.py
```

**Benefits:**
- Related code co-located
- Easy to extract to microservice
- Clear module boundaries
- Better discoverability

### Hybrid Approach for Complex Domains

For larger applications:

```
app/
├── domain/                         # Domain layer (feature-based)
│   ├── users/
│   │   ├── models.py
│   │   ├── services.py
│   │   └── interfaces.py
│   └── orders/
│       ├── models.py
│       ├── services.py
│       └── interfaces.py
├── application/                    # Application layer (feature-based)
│   ├── users/
│   │   └── use_cases.py
│   └── orders/
│       └── use_cases.py
└── infrastructure/                 # Infrastructure layer (technical)
    ├── database/
    │   ├── user_repository.py
    │   └── order_repository.py
    └── messaging/
        └── kafka_client.py
```

---

## Single Responsibility Principle

### File-Level SRP

Each file should have **one reason to change**.

**Bad:**
```python
# utils.py - Too many responsibilities
def validate_email(email): ...
def send_email(to, subject): ...
def format_currency(amount): ...
def query_database(sql): ...
```

**Good:**
```python
# validators.py - Email validation only
def validate_email(email): ...
def validate_phone(phone): ...

# email_client.py - Email operations only
def send_email(to, subject): ...
def send_bulk_email(recipients): ...

# formatters.py - Formatting only
def format_currency(amount): ...
def format_date(date): ...

# database.py - Database operations only
def query_database(sql): ...
def execute_transaction(queries): ...
```

### Class-Level SRP

**Bad:**
```python
class User:
    """God class - too many responsibilities."""

    def save_to_database(self): ...
    def send_welcome_email(self): ...
    def validate_data(self): ...
    def calculate_discount(self): ...
    def log_activity(self): ...
```

**Good:**
```python
class User:
    """Domain model - data and validation only."""

    def is_valid(self) -> bool: ...

class UserRepository:
    """Persistence only."""

    def save(self, user: User): ...

class EmailService:
    """Email operations only."""

    def send_welcome(self, user: User): ...

class DiscountCalculator:
    """Discount logic only."""

    def calculate(self, user: User) -> Decimal: ...
```

---

## Module Design Guidelines

### Module Size Recommendations

- **Maximum file size:** 500 lines (preferably < 300)
- **Maximum function length:** 50 lines (preferably < 20)
- **Maximum class methods:** 10 methods
- **Maximum module imports:** 20 imports

### When to Split a Module

Split when:
- File exceeds 500 lines
- Multiple distinct responsibilities
- File name becomes generic ("utils.py", "helpers.py")
- Difficult to find specific functionality
- Changes frequently for unrelated reasons

### How to Split a Module

**Before (monolithic):**
```python
# services.py - 800 lines
class UserService: ...      # 200 lines
class OrderService: ...     # 200 lines
class ProductService: ...   # 200 lines
class PaymentService: ...   # 200 lines
```

**After (modular):**
```python
# services/
├── __init__.py
├── user_service.py         # 200 lines
├── order_service.py        # 200 lines
├── product_service.py      # 200 lines
└── payment_service.py      # 200 lines
```

Or feature-based:
```python
# users/service.py           # 200 lines
# orders/service.py          # 200 lines
# products/service.py        # 200 lines
# payments/service.py        # 200 lines
```

---

## Import Organization

### Import Order (PEP 8)

```python
# 1. Standard library imports
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional

# 2. Third-party imports
import boto3
import requests
from pydantic import BaseModel

# 3. Local application imports
from domain.models import User
from infrastructure.database import UserRepository
from shared.logging import get_logger
```

### Absolute vs Relative Imports

**Prefer absolute imports:**
```python
# ✅ GOOD - Clear and explicit
from domain.models import User
from infrastructure.database import UserRepository
```

**Avoid relative imports (except in packages):**
```python
# ❌ AVOID - Harder to refactor
from ..models import User
from ...infrastructure.database import UserRepository
```

### Circular Import Prevention

**Problem:**
```python
# models.py
from services import UserService

class User:
    service = UserService()

# services.py
from models import User

class UserService:
    def create_user(self) -> User: ...
```

**Solutions:**

1. **Use interfaces (best):**
```python
# domain/interfaces.py
class UserServiceInterface:
    def create_user(self) -> 'User': ...

# domain/models.py
from domain.interfaces import UserServiceInterface

class User:
    service: UserServiceInterface
```

2. **Import inside function:**
```python
# models.py
class User:
    def get_service(self):
        from services import UserService
        return UserService()
```

3. **Restructure dependencies:**
```python
# Remove circular dependency by injecting service
class User:
    def __init__(self, service):
        self.service = service
```

---

## Naming Conventions

### Files and Directories

- **Modules:** `snake_case.py`
- **Packages:** `snake_case/`
- **Test files:** `test_*.py` or `*_test.py`

Examples:
```
user_repository.py          # ✅ Good
UserRepository.py           # ❌ Bad (use snake_case)
user-repository.py          # ❌ Bad (no hyphens)
```

### Classes and Functions

```python
# Classes: PascalCase
class UserService: ...
class HTTPConnection: ...

# Functions/methods: snake_case
def calculate_total(): ...
def send_email(): ...

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
DATABASE_URL = "postgresql://..."

# Private: prefix with _
def _internal_helper(): ...
class _InternalClass: ...
```

### Module Organization

```python
# module.py

# 1. Module docstring
"""
Module for user authentication.

Handles user login, logout, and session management.
"""

# 2. Imports (organized as above)
import os
from typing import Optional

# 3. Constants
DEFAULT_SESSION_TIMEOUT = 3600

# 4. Exception classes
class AuthenticationError(Exception):
    """Raised when authentication fails."""

# 5. Classes
class AuthService:
    """Service for user authentication."""

# 6. Functions
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""

# 7. Main execution (if applicable)
if __name__ == "__main__":
    main()
```

---

## Package Initialization

### `__init__.py` Best Practices

**Minimal (recommended for most packages):**
```python
# domain/__init__.py
"""Domain layer for business logic."""

# Optionally expose public API
from domain.models import User, Order
from domain.services import UserService

__all__ = ['User', 'Order', 'UserService']
```

**With version:**
```python
# my_package/__init__.py
"""My Package - Description here."""

__version__ = "1.0.0"
__author__ = "Your Name"

from my_package.core import MainClass

__all__ = ['MainClass']
```

**Lazy imports (for large packages):**
```python
# my_package/__init__.py
"""My Package with lazy imports."""

def __getattr__(name):
    """Lazy import heavy modules."""
    if name == 'HeavyClass':
        from my_package.heavy_module import HeavyClass
        return HeavyClass
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

---

## File Organization Anti-Patterns

### ❌ God Files

**Problem:** Single file doing everything
```
app.py                  # 5000 lines - everything in one file
```

**Solution:** Split by responsibility

### ❌ Generic Names

**Problem:** Vague file names
```
utils.py               # What utils?
helpers.py             # What helpers?
common.py              # What's common?
```

**Solution:** Specific names
```
string_formatters.py   # String formatting utilities
date_utils.py          # Date manipulation utilities
validators.py          # Input validation functions
```

### ❌ Deep Nesting

**Problem:** Too many directory levels
```
app/
  infrastructure/
    persistence/
      database/
        repositories/
          user/
            mysql/
              user_repository.py  # Too deep!
```

**Solution:** Maximum 3-4 levels
```
app/
  infrastructure/
    database/
      user_repository.py        # Better!
```

### ❌ Mixed Concerns

**Problem:** Infrastructure mixed with domain
```
domain/
  user.py                      # Domain model
  user_repository.py           # Infrastructure!
```

**Solution:** Separate by layer
```
domain/
  models.py                    # Domain models only
infrastructure/
  repositories.py              # Infrastructure only
```

---

## Documentation in Code

### Module Docstrings

```python
"""
User Authentication Module

This module provides user authentication functionality including:
- Login and logout
- Session management
- Password hashing and verification
- Token generation

Example:
    >>> auth_service = AuthService()
    >>> user = auth_service.login('user@example.com', 'password')
    >>> token = auth_service.generate_token(user)

Note:
    This module requires bcrypt for password hashing.
"""
```

### Function Docstrings (Google Style)

```python
def calculate_discount(
    price: Decimal,
    discount_percent: float,
    member_tier: str
) -> Decimal:
    """
    Calculate final price after discount.

    Applies percentage discount and additional tier-based discount
    for premium members.

    Args:
        price: Original price before discount
        discount_percent: Percentage discount (0-100)
        member_tier: Membership tier ('basic', 'premium', 'vip')

    Returns:
        Final price after all discounts applied

    Raises:
        ValueError: If discount_percent is not in range 0-100
        ValueError: If member_tier is not recognized

    Example:
        >>> calculate_discount(Decimal('100.00'), 10, 'premium')
        Decimal('85.50')
    """
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")

    # Implementation...
```

### When to Add Docstrings

**Always:**
- Public modules
- Public classes
- Public functions/methods

**Optional (but recommended):**
- Complex private functions
- Non-obvious algorithms

**Not needed:**
- Self-explanatory code
- Simple getters/setters
- Obvious implementations

---

## Checklist for Well-Organized Code

- [ ] **Clear structure** - Feature-based or clean architecture
- [ ] **Single responsibility** - Each file has one purpose
- [ ] **Appropriate size** - Files < 500 lines, functions < 50 lines
- [ ] **Consistent naming** - snake_case files, PascalCase classes
- [ ] **Organized imports** - Stdlib, third-party, local
- [ ] **No circular imports** - Dependencies point inward
- [ ] **Documented** - Module and function docstrings
- [ ] **Testable** - Structure supports testing
- [ ] **Maintainable** - Easy to find and modify code
