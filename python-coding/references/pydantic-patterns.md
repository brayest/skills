# Pydantic Patterns for Type-Safe Python Applications

## Introduction

Pydantic provides runtime data validation and type safety using Python type hints. It's essential for building robust Python applications where data validation and serialization are critical.

**Version:** These patterns assume Pydantic v2.x (recommended for new projects)

---

## Basic Model Definition

### Simple Models

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class User(BaseModel):
    """User domain model with validation."""

    id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    name: str = Field(..., min_length=1, max_length=100)
    age: Optional[int] = Field(None, ge=0, le=150)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Usage
user = User(
    id="123",
    email="user@example.com",
    name="John Doe",
    age=30
)

# Validation fails
try:
    invalid_user = User(
        id="123",
        email="user@example.com",
        name="",  # Too short!
        age=200   # Too old!
    )
except ValidationError as e:
    print(e.errors())
```

### Field Constraints

```python
from pydantic import BaseModel, Field
from typing import List
from decimal import Decimal

class Product(BaseModel):
    """Product with field constraints."""

    # String constraints
    name: str = Field(..., min_length=3, max_length=100)
    sku: str = Field(..., pattern=r'^[A-Z]{3}-\d{6}$')

    # Numeric constraints
    price: Decimal = Field(..., gt=0, decimal_places=2)
    quantity: int = Field(..., ge=0)
    discount_percent: float = Field(0.0, ge=0.0, le=100.0)

    # Collection constraints
    tags: List[str] = Field(default_factory=list, max_length=10)

    # Immutable (frozen)
    class Config:
        frozen = False  # Set to True for immutability
```

---

## Custom Validators

### Field Validators (Pydantic v2)

```python
from pydantic import BaseModel, field_validator, Field

class UserRegistration(BaseModel):
    """User registration with custom validation."""

    username: str = Field(..., min_length=3)
    email: str
    password: str
    confirm_password: str

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Validate username is alphanumeric."""
        if not v.isalnum():
            raise ValueError('Username must be alphanumeric')
        return v.lower()  # Normalize to lowercase

    @field_validator('email')
    @classmethod
    def email_must_be_valid(cls, v: str) -> str:
        """Validate email format."""
        if '@' not in v:
            raise ValueError('Invalid email format')
        if not v.endswith(('.com', '.org', '.net')):
            raise ValueError('Email must end with .com, .org, or .net')
        return v.lower()

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate passwords match."""
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Passwords do not match')
        return v
```

### Model Validators

```python
from pydantic import BaseModel, model_validator

class DateRange(BaseModel):
    """Date range with model-level validation."""

    start_date: datetime
    end_date: datetime

    @model_validator(mode='after')
    def check_dates(self) -> 'DateRange':
        """Validate end_date is after start_date."""
        if self.end_date <= self.start_date:
            raise ValueError('end_date must be after start_date')
        return self
```

---

## Model Composition and Inheritance

### Nested Models

```python
from pydantic import BaseModel
from typing import List

class Address(BaseModel):
    """Address model."""
    street: str
    city: str
    state: str
    zip_code: str

class Contact(BaseModel):
    """Contact information."""
    email: str
    phone: str

class Customer(BaseModel):
    """Customer with nested models."""
    name: str
    contact: Contact
    addresses: List[Address]

# Usage
customer = Customer(
    name="John Doe",
    contact=Contact(
        email="john@example.com",
        phone="555-1234"
    ),
    addresses=[
        Address(
            street="123 Main St",
            city="Springfield",
            state="IL",
            zip_code="62701"
        )
    ]
)

# Access nested fields
print(customer.contact.email)
print(customer.addresses[0].city)
```

### Model Inheritance

```python
from pydantic import BaseModel
from datetime import datetime

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

class SoftDeleteMixin(BaseModel):
    """Mixin for soft delete."""
    deleted_at: Optional[datetime] = None
    is_deleted: bool = False

class BaseEntity(TimestampMixin, SoftDeleteMixin):
    """Base entity with common fields."""
    id: str

class User(BaseEntity):
    """User inherits all base fields."""
    email: str
    name: str

# User now has: id, email, name, created_at, updated_at, deleted_at, is_deleted
```

---

## Serialization and Deserialization

### Dictionary Conversion

```python
from pydantic import BaseModel

class User(BaseModel):
    id: str
    email: str
    name: str

# Create from dict
user_dict = {
    'id': '123',
    'email': 'user@example.com',
    'name': 'John Doe'
}
user = User(**user_dict)

# Convert to dict (Pydantic v2)
data = user.model_dump()
print(data)  # {'id': '123', 'email': 'user@example.com', 'name': 'John Doe'}

# Exclude fields
data = user.model_dump(exclude={'id'})

# Include only specific fields
data = user.model_dump(include={'email', 'name'})

# Exclude None values
data = user.model_dump(exclude_none=True)
```

### JSON Serialization

```python
import json
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

class Order(BaseModel):
    """Order with complex types."""
    id: str
    total: Decimal
    created_at: datetime

# Serialize to JSON (Pydantic v2)
order = Order(id='123', total=Decimal('99.99'), created_at=datetime.utcnow())

json_str = order.model_dump_json()
print(json_str)  # {"id":"123","total":"99.99","created_at":"2026-02-10T15:30:45.123Z"}

# Deserialize from JSON
order2 = Order.model_validate_json(json_str)
```

### Safe JSON Serialization Utility

```python
from typing import Any
import json

def safe_json_dumps(obj: Any, indent: int = None) -> str:
    """
    Safely serialize objects to JSON, handling Pydantic models.

    Args:
        obj: Object to serialize (Pydantic model, dict, list, etc.)
        indent: JSON indentation

    Returns:
        JSON string
    """
    if hasattr(obj, 'model_dump'):
        # Pydantic v2
        return obj.model_dump_json(indent=indent)
    elif hasattr(obj, 'dict'):
        # Pydantic v1 (legacy)
        return json.dumps(obj.dict(), indent=indent)
    elif isinstance(obj, dict):
        # Dict - may contain nested Pydantic objects
        converted = {}
        for key, value in obj.items():
            if hasattr(value, 'model_dump'):
                converted[key] = value.model_dump()
            elif hasattr(value, 'dict'):
                converted[key] = value.dict()
            else:
                converted[key] = value
        return json.dumps(converted, indent=indent)
    else:
        return json.dumps(obj, indent=indent)

# Usage
result = safe_json_dumps(user)
```

---

## Configuration and Settings

### Application Settings with pydantic-settings

**Install:**
```bash
pip install pydantic-settings
```

**Implementation:**

```python
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Service configuration
    service_name: str = Field(default="my-service", alias="SERVICE_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")

    # Database configuration
    database_url: str = Field(..., alias="DATABASE_URL")  # Required
    database_pool_size: int = Field(default=10, alias="DB_POOL_SIZE")

    # AWS configuration
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket: str = Field(..., alias="S3_BUCKET")

    # Optional features
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    class Config:
        env_file = ".env"  # Load from .env file in development
        env_file_encoding = 'utf-8'
        case_sensitive = False

# Create settings instance
settings = Settings()

# Use throughout application
print(settings.database_url)
print(settings.aws_region)
```

---

## Advanced Patterns

### Discriminated Unions

```python
from pydantic import BaseModel, Field
from typing import Literal, Union

class CreditCardPayment(BaseModel):
    """Credit card payment method."""
    type: Literal['credit_card'] = 'credit_card'
    card_number: str
    cvv: str
    expiry: str

class PayPalPayment(BaseModel):
    """PayPal payment method."""
    type: Literal['paypal'] = 'paypal'
    email: str

class BankTransfer(BaseModel):
    """Bank transfer payment method."""
    type: Literal['bank_transfer'] = 'bank_transfer'
    account_number: str
    routing_number: str

# Union type with discriminator
Payment = Union[CreditCardPayment, PayPalPayment, BankTransfer]

class Order(BaseModel):
    """Order with discriminated payment type."""
    id: str
    payment: Payment = Field(..., discriminator='type')

# Pydantic automatically selects correct model based on 'type' field
order1 = Order(
    id='123',
    payment={'type': 'credit_card', 'card_number': '1234', 'cvv': '123', 'expiry': '12/25'}
)

order2 = Order(
    id='456',
    payment={'type': 'paypal', 'email': 'user@example.com'}
)
```

### Generic Models

```python
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    page: int
    page_size: int

class User(BaseModel):
    id: str
    name: str

class Product(BaseModel):
    id: str
    name: str
    price: float

# Type-safe paginated responses
user_response = PaginatedResponse[User](
    items=[User(id='1', name='John'), User(id='2', name='Jane')],
    total=2,
    page=1,
    page_size=10
)

product_response = PaginatedResponse[Product](
    items=[Product(id='1', name='Widget', price=9.99)],
    total=1,
    page=1,
    page_size=10
)
```

### Computed Fields

```python
from pydantic import BaseModel, computed_field
from decimal import Decimal

class Invoice(BaseModel):
    """Invoice with computed fields."""
    subtotal: Decimal
    tax_rate: float = 0.10

    @computed_field
    @property
    def tax_amount(self) -> Decimal:
        """Calculate tax amount."""
        return self.subtotal * Decimal(str(self.tax_rate))

    @computed_field
    @property
    def total(self) -> Decimal:
        """Calculate total with tax."""
        return self.subtotal + self.tax_amount

# Usage
invoice = Invoice(subtotal=Decimal('100.00'))
print(invoice.tax_amount)  # Decimal('10.00')
print(invoice.total)       # Decimal('110.00')

# Computed fields included in serialization
print(invoice.model_dump())
# {'subtotal': Decimal('100.00'), 'tax_rate': 0.1, 'tax_amount': Decimal('10.00'), 'total': Decimal('110.00')}
```

---

## Validation Patterns

### Pre and Post Validation

```python
from pydantic import BaseModel, field_validator

class EmailAddress(BaseModel):
    """Email address with normalization."""
    email: str

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, v):
        """Normalize before validation."""
        if isinstance(v, str):
            return v.lower().strip()
        return v

    @field_validator('email', mode='after')
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate after normalization."""
        if not v.endswith('@company.com'):
            raise ValueError('Only company emails allowed')
        return v
```

### Conditional Validation

```python
from pydantic import BaseModel, field_validator

class ShippingInfo(BaseModel):
    """Shipping information with conditional validation."""
    country: str
    state: Optional[str] = None
    postal_code: str

    @field_validator('state')
    @classmethod
    def state_required_for_us(cls, v, info):
        """State required for US addresses."""
        if info.data.get('country') == 'US' and not v:
            raise ValueError('State required for US addresses')
        return v

    @field_validator('postal_code')
    @classmethod
    def validate_postal_code(cls, v, info):
        """Validate postal code format by country."""
        country = info.data.get('country')

        if country == 'US':
            if not v.match(r'^\d{5}(-\d{4})?$'):
                raise ValueError('Invalid US ZIP code')
        elif country == 'CA':
            if not v.match(r'^[A-Z]\d[A-Z] \d[A-Z]\d$'):
                raise ValueError('Invalid Canadian postal code')

        return v
```

---

## Error Handling

### Validation Errors

```python
from pydantic import BaseModel, ValidationError

class User(BaseModel):
    email: str
    age: int

try:
    user = User(email='not-an-email', age='not-a-number')
except ValidationError as e:
    print(e.errors())
    # [
    #   {'type': 'value_error', 'loc': ('email',), 'msg': 'value is not a valid email address'},
    #   {'type': 'int_parsing', 'loc': ('age',), 'msg': 'Input should be a valid integer'}
    # ]

    # Access specific error details
    for error in e.errors():
        print(f"Field: {error['loc']}, Error: {error['msg']}")
```

### Custom Error Messages

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    """User with custom error messages."""

    email: str = Field(
        ...,
        pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$',
        json_schema_extra={'error_messages': {
            'pattern': 'Email must be in valid format'
        }}
    )

    age: int = Field(
        ...,
        ge=18,
        le=100,
        json_schema_extra={'error_messages': {
            'greater_than_equal': 'Must be at least 18 years old',
            'less_than_equal': 'Age cannot exceed 100'
        }}
    )
```

---

## Best Practices

### 1. Use Type Hints Consistently

```python
# ✅ GOOD - Explicit types
class User(BaseModel):
    id: str
    email: str
    age: Optional[int] = None

# ❌ BAD - Missing types
class User(BaseModel):
    id = ""  # Type inferred, but not explicit
    email = ""
```

### 2. Provide Field Descriptions

```python
# ✅ GOOD - Documented fields
class User(BaseModel):
    id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")

# ❌ BAD - No descriptions
class User(BaseModel):
    id: str
    email: str
```

### 3. Use Appropriate Defaults

```python
# ✅ GOOD - Explicit defaults
class Config(BaseModel):
    timeout: int = Field(default=30, ge=1, le=300)
    retry_count: int = Field(default=3, ge=0)

# ❌ BAD - Mutable defaults
class Config(BaseModel):
    tags: List[str] = []  # DANGEROUS! Shared across instances

# ✅ GOOD - Factory for mutable defaults
class Config(BaseModel):
    tags: List[str] = Field(default_factory=list)
```

### 4. Validate at Boundaries

```python
# API endpoint
@app.post("/users")
async def create_user(user_data: UserInput):  # ✅ Pydantic validates
    """User data validated automatically by Pydantic."""
    # user_data is guaranteed to be valid
    user = await user_service.create(user_data)
    return user
```

### 5. Use Immutable Models for Value Objects

```python
class Money(BaseModel):
    """Immutable money value object."""
    amount: Decimal
    currency: str

    class Config:
        frozen = True  # Immutable

# Usage
price = Money(amount=Decimal('99.99'), currency='USD')
# price.amount = Decimal('100.00')  # Raises ValidationError
```

---

## Common Patterns

### API Response Models

```python
from pydantic import BaseModel
from typing import Optional, Any

class APIResponse(BaseModel):
    """Standard API response."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None

# Success response
success_response = APIResponse(
    success=True,
    data={'user_id': '123'},
    message='User created successfully'
)

# Error response
error_response = APIResponse(
    success=False,
    error='VALIDATION_ERROR',
    message='Invalid email format'
)
```

### Database Model to Pydantic

```python
# Database model (SQLAlchemy)
from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserDB(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String)
    name = Column(String)

# Pydantic schema
class UserSchema(BaseModel):
    """Pydantic schema for API."""
    id: int
    email: str
    name: str

    class Config:
        from_attributes = True  # Pydantic v2 (was orm_mode in v1)

# Convert SQLAlchemy model to Pydantic
db_user = session.query(UserDB).first()
user_schema = UserSchema.from_orm(db_user)
```

---

## Summary

Pydantic patterns enable:
- **Runtime validation** - Catch errors at boundaries
- **Type safety** - IDE support and type checking
- **Self-documentation** - Field descriptions as docs
- **Serialization** - Easy JSON conversion
- **Configuration** - Type-safe settings management

**Key takeaways:**
1. Use Pydantic for all data validation
2. Add field constraints and validators
3. Document fields with descriptions
4. Leverage computed fields for derived data
5. Use settings for environment configuration
