# Component Patterns

## Headless UI

### Philosophy
Separate behavior/accessibility from visual presentation. Use unstyled, accessible primitives as the foundation — style them with your own CSS.

### Radix UI
Low-level accessible primitives for building design systems:

```typescript
import * as Dialog from '@radix-ui/react-dialog';

const Modal = ({ children, trigger }) => (
  <Dialog.Root>
    <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="modal-overlay" />
      <Dialog.Content className="modal-content">
        {children}
        <Dialog.Close asChild>
          <button className="modal-close">Close</button>
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
);
```

**Benefits:** Built-in keyboard navigation, focus trapping, ARIA attributes, screen reader support. 130M+ monthly downloads. Used by Vercel, Linear, and others.

### shadcn/ui
Copy-paste components built on Radix + Tailwind. Not a dependency — components are copied into the project and owned by the team.

```bash
npx shadcn@latest add button dialog
```

**When to use:** Rapid prototyping with good defaults. Full customization since the code is yours.

### Ark UI
Headless components from the Chakra UI team. Supports React, Vue, and Solid.

---

## Error Boundaries

### Setup with react-error-boundary

```typescript
import { ErrorBoundary } from 'react-error-boundary';

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <div role="alert">
      <p>Something went wrong:</p>
      <pre>{error.message}</pre>
      <button onClick={resetErrorBoundary}>Try again</button>
    </div>
  );
}

// Usage
<ErrorBoundary FallbackComponent={ErrorFallback}>
  <FeatureComponent />
</ErrorBoundary>
```

### Placement Strategy

1. **Root level** — catches everything, shows generic error page
2. **Feature level** — isolates feature failures (quiz, dashboard, settings)
3. **Component level** — for unreliable third-party widgets

```typescript
// Feature-level isolation
<Layout>
  <ErrorBoundary fallback={<p>Quiz failed to load</p>}>
    <QuizFeature />
  </ErrorBoundary>
  <ErrorBoundary fallback={<p>Sidebar unavailable</p>}>
    <Sidebar />
  </ErrorBoundary>
</Layout>
```

### Async Error Handling

Error boundaries only catch rendering errors. For event handlers and async errors:

```typescript
import { useErrorBoundary } from 'react-error-boundary';

function SubmitButton() {
  const { showBoundary } = useErrorBoundary();

  const handleClick = async () => {
    try {
      await api.submit(data);
    } catch (error) {
      showBoundary(error); // Propagates to nearest ErrorBoundary
    }
  };

  return <button onClick={handleClick}>Submit</button>;
}
```

---

## Suspense

### Loading States

```typescript
import { Suspense } from 'react';

<Suspense fallback={<Skeleton />}>
  <AsyncComponent />
</Suspense>
```

### Suspense + Error Boundary Composition

```typescript
<ErrorBoundary FallbackComponent={ErrorFallback}>
  <Suspense fallback={<Skeleton />}>
    <AsyncFeature />
  </Suspense>
</ErrorBoundary>
```

This pattern provides declarative loading AND error handling. No manual loading/error state management.

### Nested Suspense

```typescript
<Suspense fallback={<PageSkeleton />}>
  <Header />
  <Suspense fallback={<ContentSkeleton />}>
    <MainContent />
  </Suspense>
  <Suspense fallback={<SidebarSkeleton />}>
    <Sidebar />
  </Suspense>
</Suspense>
```

Outer Suspense catches everything. Inner boundaries provide granular loading states.

---

## Compound Components

### Pattern
Parent component shares implicit state with children via Context:

```typescript
const TabsContext = createContext<TabsContextValue | null>(null);

function Tabs({ children, defaultTab }: TabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className="tabs">{children}</div>
    </TabsContext.Provider>
  );
}

function TabList({ children }: { children: ReactNode }) {
  return <div role="tablist">{children}</div>;
}

function Tab({ id, children }: { id: string; children: ReactNode }) {
  const { activeTab, setActiveTab } = useContext(TabsContext)!;
  return (
    <button
      role="tab"
      aria-selected={activeTab === id}
      onClick={() => setActiveTab(id)}
    >
      {children}
    </button>
  );
}

function TabPanel({ id, children }: { id: string; children: ReactNode }) {
  const { activeTab } = useContext(TabsContext)!;
  if (activeTab !== id) return null;
  return <div role="tabpanel">{children}</div>;
}

// Attach sub-components
Tabs.List = TabList;
Tabs.Tab = Tab;
Tabs.Panel = TabPanel;

// Usage
<Tabs defaultTab="profile">
  <Tabs.List>
    <Tabs.Tab id="profile">Profile</Tabs.Tab>
    <Tabs.Tab id="settings">Settings</Tabs.Tab>
  </Tabs.List>
  <Tabs.Panel id="profile"><ProfileContent /></Tabs.Panel>
  <Tabs.Panel id="settings"><SettingsContent /></Tabs.Panel>
</Tabs>
```

**When to use:** Components that share implicit state and must be used together (Tabs, Accordion, Dropdown, Combobox).

---

## Form Handling

### React Hook Form + Zod

```typescript
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Must be at least 8 characters'),
  role: z.enum(['admin', 'user']),
});

type FormData = z.infer<typeof schema>;

function LoginForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    await api.login(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('email')} />
      {errors.email && <span>{errors.email.message}</span>}

      <input type="password" {...register('password')} />
      {errors.password && <span>{errors.password.message}</span>}

      <select {...register('role')}>
        <option value="user">User</option>
        <option value="admin">Admin</option>
      </select>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}
```

**Benefits:**
- Uncontrolled inputs for performance (minimal re-renders)
- Zod schemas shared between client and server
- TypeScript types inferred from schema via `z.infer`
- Built-in validation, error messages, dirty/touched tracking

### Controlled vs Uncontrolled

- **Controlled** (React manages value via state): Use when the value drives other UI or needs real-time validation
- **Uncontrolled** (DOM manages value, React Hook Form reads on submit): Use for performance in large forms

**Rule of thumb:** Use React Hook Form (uncontrolled) for standard forms. Use controlled inputs only when you need immediate value access (e.g., search-as-you-type, conditional rendering based on input).
