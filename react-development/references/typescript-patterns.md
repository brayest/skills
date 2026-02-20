# TypeScript Patterns for React

## Strict Mode Configuration

Non-negotiable for production React apps:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "forceConsistentCasingInFileNames": true,
    "isolatedModules": true,
    "skipLibCheck": true
  }
}
```

`strict: true` enables: `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis`, `alwaysStrict`.

`noUncheckedIndexedAccess` adds `| undefined` to array/record index access — catches common bugs.

---

## `satisfies` Operator

Validates that a value matches a type without narrowing the inferred type:

```typescript
// WITHOUT satisfies — type is widened to Record<string, string>
const colors: Record<string, string> = {
  primary: '#232f3e',
  accent: '#ff9900',
};
colors.primary; // type: string

// WITH satisfies — structure validated, literals preserved
const colors = {
  primary: '#232f3e',
  accent: '#ff9900',
} satisfies Record<string, string>;
colors.primary; // type: "#232f3e"
colors.typo;    // Error: Property 'typo' does not exist
```

### Config Objects

```typescript
const API_ENDPOINTS = {
  users: '/api/v1/users',
  sessions: '/api/v1/sessions',
  questions: '/api/v1/questions',
} satisfies Record<string, string>;
// Auto-complete works: API_ENDPOINTS.users
// Typo-safe: API_ENDPOINTS.uesrs → compile error
```

### Route Configs

```typescript
const routes = {
  home: '/',
  exam: '/exam/:sessionId',
  results: '/results/:sessionId',
} satisfies Record<string, string>;
```

---

## `as const` Assertions

Prevent type widening — preserve literal types:

```typescript
// Without as const
const STATUS = { ACTIVE: 'active', INACTIVE: 'inactive' };
// type: { ACTIVE: string; INACTIVE: string }

// With as const
const STATUS = { ACTIVE: 'active', INACTIVE: 'inactive' } as const;
// type: { readonly ACTIVE: "active"; readonly INACTIVE: "inactive" }
```

### Combining `as const satisfies`

```typescript
const BLOOM_LEVELS = {
  remember: 'I',
  understand: 'II',
  apply: 'III',
  analyze: 'IV',
  evaluate: 'V',
  create: 'VI',
} as const satisfies Record<string, string>;

// Structure validated against Record<string, string>
// Literal types preserved: BLOOM_LEVELS.remember is "I", not string
// Object is readonly — cannot be mutated
```

---

## Discriminated Unions

Type-safe handling of different shapes based on a discriminant field:

### Component Props

```typescript
type ButtonVariant = 'primary' | 'secondary' | 'danger';

interface IconButtonProps {
  variant: ButtonVariant;
  icon: ReactNode;
  label: string;  // Required for accessibility
  children?: never;
}

interface TextButtonProps {
  variant: ButtonVariant;
  icon?: never;
  label?: never;
  children: ReactNode;
}

type ButtonProps = IconButtonProps | TextButtonProps;

function Button(props: ButtonProps) {
  if ('icon' in props) {
    return <button aria-label={props.label}>{props.icon}</button>;
  }
  return <button>{props.children}</button>;
}
```

### API Responses

```typescript
interface MCQuestion {
  question_type: 'multiple_choice_single' | 'multiple_choice_multiple';
  options: Record<string, string>;  // { "A": "text", "B": "text" }
}

interface OrderingQuestion {
  question_type: 'ordering';
  options: { steps: string[] };
}

type Question = (MCQuestion | OrderingQuestion) & {
  id: number;
  question_text: string;
  bloom_level: string;
};

// TypeScript narrows based on question_type
function renderQuestion(q: Question) {
  switch (q.question_type) {
    case 'multiple_choice_single':
    case 'multiple_choice_multiple':
      // q.options is Record<string, string> here
      return Object.entries(q.options).map(([key, value]) => /* ... */);
    case 'ordering':
      // q.options is { steps: string[] } here
      return q.options.steps.map((step) => /* ... */);
  }
}
```

### Result Types (Error Handling)

```typescript
type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

function processResult(result: Result<User>) {
  if (result.ok) {
    console.log(result.data.name); // TypeScript knows data exists
  } else {
    console.error(result.error);   // TypeScript knows error exists
  }
}
```

---

## Generic Components

### Typed Select Component

```typescript
interface SelectProps<T extends string> {
  options: readonly T[];
  value: T;
  onChange: (value: T) => void;
}

function Select<T extends string>({ options, value, onChange }: SelectProps<T>) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as T)}>
      {options.map((option) => (
        <option key={option} value={option}>{option}</option>
      ))}
    </select>
  );
}

// Usage — type-safe
const roles = ['admin', 'user', 'viewer'] as const;
<Select options={roles} value="admin" onChange={(v) => /* v is 'admin' | 'user' | 'viewer' */} />
```

### Typed List Component

```typescript
interface ListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => ReactNode;
  keyExtractor: (item: T) => string;
}

function List<T>({ items, renderItem, keyExtractor }: ListProps<T>) {
  return (
    <ul>
      {items.map((item, index) => (
        <li key={keyExtractor(item)}>{renderItem(item, index)}</li>
      ))}
    </ul>
  );
}
```

---

## Type-Safe API Clients

### Manual Pattern (Axios Wrappers)

```typescript
// api/client.ts
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  headers: { 'Content-Type': 'application/json' },
  timeout: 10_000,
});

// api/users.ts
export const usersApi = {
  getUser: (id: string) =>
    apiClient.get<User>(`/api/v1/users/${id}`).then((r) => r.data),

  createUser: (data: CreateUserRequest) =>
    apiClient.post<User>('/api/v1/users', data).then((r) => r.data),

  updateUser: (id: string, data: UpdateUserRequest) =>
    apiClient.put<User>(`/api/v1/users/${id}`, data).then((r) => r.data),
};
```

### Generated Pattern (Zodios)

For teams with OpenAPI specs:

```typescript
import { makeApi, Zodios } from '@zodios/core';
import { z } from 'zod';

const api = makeApi([
  {
    method: 'get',
    path: '/users/:id',
    alias: 'getUser',
    response: z.object({
      id: z.string(),
      name: z.string(),
      email: z.string().email(),
    }),
  },
]);

const client = new Zodios('/api/v1', api);
const user = await client.getUser({ params: { id: '123' } });
// Fully typed: user.name, user.email — with runtime validation
```

### Backend Schema Mirroring

Keep API types in a dedicated file. Match backend naming (snake_case). Convert to camelCase in the application layer:

```typescript
// types/api.ts — mirrors backend Pydantic schemas
export interface SessionResponse {
  session_id: string;
  total_questions: number;
  current_question_index: number;
  started_at: string;
}

// Converted in store/hooks
interface Session {
  sessionId: string;
  totalQuestions: number;
  currentQuestionIndex: number;
  startedAt: string;
}
```

---

## Common Patterns

### Exhaustive Switch

```typescript
function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${value}`);
}

function getLabel(status: 'active' | 'inactive' | 'pending') {
  switch (status) {
    case 'active': return 'Active';
    case 'inactive': return 'Inactive';
    case 'pending': return 'Pending';
    default: return assertNever(status); // Compile error if a case is missing
  }
}
```

### Template Literal Types

```typescript
type EventName = `on${Capitalize<'click' | 'hover' | 'focus'>}`;
// "onClick" | "onHover" | "onFocus"
```

### Extract/Exclude Utility Types

```typescript
type QuestionType = 'multiple_choice_single' | 'multiple_choice_multiple' | 'ordering';
type MCType = Extract<QuestionType, `multiple_choice_${string}`>;
// "multiple_choice_single" | "multiple_choice_multiple"
```
