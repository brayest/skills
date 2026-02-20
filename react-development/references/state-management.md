# State Management Patterns

## Decision Matrix

| State Type | Tool | When to Use | Examples |
|-----------|------|-------------|----------|
| **Server state** | TanStack Query v5 | Data from APIs that needs caching, refetching, invalidation | User profiles, lists, search results |
| **Client state** | Zustand | Shared UI state not derived from server | Selected items, UI preferences, navigation state |
| **Local state** | useState / useReducer | Component-scoped, not shared | Form inputs, toggles, hover states |
| **URL state** | Router params / search params | Shareable, bookmarkable state | Filters, pagination, selected tab |

**Anti-pattern:** Storing server data in Zustand. This creates a synchronization problem — Zustand doesn't know when server data is stale. Use TanStack Query for anything that comes from an API.

---

## Zustand

### Basic Store Setup

```typescript
import { create } from 'zustand';

interface AppState {
  count: number;
  increment: () => void;
  reset: () => void;
}

const useAppStore = create<AppState>((set) => ({
  count: 0,
  increment: () => set((state) => ({ count: state.count + 1 })),
  reset: () => set({ count: 0 }),
}));
```

### Slice Pattern (Recommended for Stores with Multiple Domains)

Divide the store into modular slices. Each slice manages its own state and actions.

```typescript
import { create, StateCreator } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

// --- Slice definitions ---

interface AuthSlice {
  user: User | null;
  setUser: (user: User | null) => void;
}

interface UISlice {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

const createAuthSlice: StateCreator<
  AuthSlice & UISlice, // Full store type for cross-slice access
  [],
  [],
  AuthSlice
> = (set) => ({
  user: null,
  setUser: (user) => set({ user }),
});

const createUISlice: StateCreator<
  AuthSlice & UISlice,
  [],
  [],
  UISlice
> = (set) => ({
  sidebarOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
});

// --- Combined store ---

type AppStore = AuthSlice & UISlice;

const useAppStore = create<AppStore>()(
  devtools(
    persist(
      (...a) => ({
        ...createAuthSlice(...a),
        ...createUISlice(...a),
      }),
      {
        name: 'app-store',
        partialize: (state) => ({
          user: state.user,
          // Exclude transient UI state from persistence
        }),
      }
    )
  )
);
```

**Critical rule:** Apply middleware (persist, devtools, immer) only to the combined store, not to individual slices. Applying middleware to slices causes unexpected behavior.

### Persist Middleware

```typescript
import { persist } from 'zustand/middleware';

const useStore = create(
  persist(
    (set) => ({
      session: null,
      theme: 'light',
      setSession: (session) => set({ session }),
    }),
    {
      name: 'store-key', // localStorage key
      partialize: (state) => ({
        session: state.session,
        // Exclude fields that shouldn't persist (loading states, errors, etc.)
      }),
    }
  )
);
```

**Hydration:** Zustand persist hydrates asynchronously via microtask. To check hydration status:

```typescript
// Wait for hydration before using persisted state
if (!useStore.persist.hasHydrated()) {
  await new Promise<void>((resolve) => {
    const unsub = useStore.persist.onFinishHydration(() => {
      unsub();
      resolve();
    });
  });
}
```

### Immer Middleware

For stores with deeply nested state, use Immer for ergonomic immutable updates:

```typescript
import { immer } from 'zustand/middleware/immer';

const useStore = create(
  immer<State>((set) => ({
    nested: { deep: { value: 0 } },
    updateValue: (v: number) =>
      set((state) => {
        state.nested.deep.value = v; // Direct mutation — Immer handles immutability
      }),
  }))
);
```

### Devtools

```typescript
import { devtools } from 'zustand/middleware';

const useStore = create(
  devtools(
    (set) => ({ /* ... */ }),
    { name: 'MyStore', enabled: import.meta.env.DEV }
  )
);
```

### Selectors (Performance)

Select only what a component needs to minimize re-renders:

```typescript
// Good — only re-renders when `count` changes
const count = useStore((state) => state.count);

// Bad — re-renders on ANY state change
const state = useStore();
```

---

## TanStack Query v5

### Setup

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,      // 1 minute before refetch
      gcTime: 5 * 60_000,     // 5 minutes garbage collection
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Wrap app
<QueryClientProvider client={queryClient}>
  <App />
</QueryClientProvider>
```

### queryOptions (Type-Safe, Shareable Configs)

```typescript
import { queryOptions } from '@tanstack/react-query';

const userQueryOptions = (userId: string) =>
  queryOptions({
    queryKey: ['user', userId],
    queryFn: () => api.getUser(userId),
    staleTime: 30_000,
  });

// In component
const { data } = useQuery(userQueryOptions(userId));

// In prefetch
queryClient.prefetchQuery(userQueryOptions(nextUserId));

// In invalidation
queryClient.invalidateQueries({ queryKey: ['user', userId] });
```

### Mutations

```typescript
const createUser = useMutation({
  mutationFn: (data: CreateUserRequest) => api.createUser(data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['users'] });
  },
  onError: (error) => {
    toast.error(error.message);
  },
});

// Usage
createUser.mutate({ name: 'John', email: 'john@example.com' });
```

### Optimistic Updates

```typescript
const updateTodo = useMutation({
  mutationFn: (todo: Todo) => api.updateTodo(todo),
  onMutate: async (newTodo) => {
    await queryClient.cancelQueries({ queryKey: ['todos'] });
    const previous = queryClient.getQueryData(['todos']);
    queryClient.setQueryData(['todos'], (old: Todo[]) =>
      old.map((t) => (t.id === newTodo.id ? newTodo : t))
    );
    return { previous };
  },
  onError: (_err, _newTodo, context) => {
    queryClient.setQueryData(['todos'], context?.previous);
  },
  onSettled: () => {
    queryClient.invalidateQueries({ queryKey: ['todos'] });
  },
});
```

### Suspense Integration

```typescript
const { data } = useSuspenseQuery(userQueryOptions(userId));
// `data` is never undefined — Suspense handles the loading state
```

### Error Boundary Integration

```typescript
const { data } = useQuery({
  ...userQueryOptions(userId),
  throwOnError: true, // Throws to nearest ErrorBoundary
});
```

### Key v5 Migration Notes
- `cacheTime` renamed to `gcTime`
- `loading` status renamed to `pending`
- `keepPreviousData` merged with `placeholderData`
- All hooks use unified object API (no overloads)
- `useQuery` no longer accepts positional parameters
