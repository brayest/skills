# Architecture, Routing, Styling, and Accessibility

## Project Architecture

### Feature-Based Structure (Recommended for >10 Components)

Organize code around features/domains, not by technical type:

```
src/
  features/                  # Feature modules
    auth/
      components/
        LoginForm.tsx
        SignupForm.tsx
      hooks/
        useAuth.ts
      api/
        auth.ts
      types/
        auth.ts
      index.ts               # Public API (barrel export)
    quiz/
      components/
        QuestionDisplay.tsx
        FeedbackPanel.tsx
      hooks/
        useQuestion.ts
        useAnswerSubmission.ts
      api/
        sessions.ts
      types/
        quiz.ts
      index.ts
  shared/                    # Truly shared across features
    components/
      Button.tsx
      Modal.tsx
      ErrorFallback.tsx
    hooks/
      useTimer.ts
    utils/
      format.ts
    types/
      common.ts
  pages/                     # Route compositions (glue features)
    StartPage.tsx
    QuizPage.tsx
    ResultsPage.tsx
  app/                       # App-level config
    App.tsx
    providers.tsx
    router.tsx
```

### Feature-Sliced Design Principles

1. **Unidirectional dependencies** — features don't import from each other
2. **Explicit public APIs** — each feature exports only what others need via `index.ts`
3. **Self-contained** — a feature's components, hooks, API calls, and types live together
4. **Pages are compositions** — they import from features and shared, but contain no business logic

### Type-Based Structure (Adequate for Small Apps)

For apps with fewer than ~15 components:

```
src/
  api/
  components/
  hooks/
  pages/
  store/
  types/
```

Simpler and avoids premature abstraction. Migrate to feature-based when complexity increases.

### Custom Hooks Pattern

Separate business logic from UI:

```typescript
// hooks/useQuestion.ts — logic only
function useQuestion(sessionId: string) {
  return useQuery({
    queryKey: ['question', sessionId],
    queryFn: () => api.getCurrentQuestion(sessionId),
  });
}

// components/QuestionDisplay.tsx — UI only
function QuestionDisplay() {
  const { data: question, isPending } = useQuestion(sessionId);
  if (isPending) return <Skeleton />;
  return <div>{question.question_text}</div>;
}
```

**Rules:**
- Hooks handle data fetching, mutations, and state logic
- Components handle rendering and user interaction
- This separation makes both independently testable

---

## Routing

### TanStack Router (Recommended for New Projects)

100% type-safe routing from the ground up:

```typescript
import { createRouter, createRoute, createRootRoute } from '@tanstack/react-router';

const rootRoute = createRootRoute({
  component: RootLayout,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: StartPage,
});

const examRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/exam/$sessionId',
  component: QuizPage,
  loader: ({ params }) => fetchSession(params.sessionId),
});

const router = createRouter({
  routeTree: rootRoute.addChildren([indexRoute, examRoute]),
});
```

**Advantages:**
- Type-safe path params and search params (catches typos at compile time)
- Parallel route loaders with automatic type inference
- 1st-class search param APIs with schema validation
- Works for SPAs, SSR, and hybrid apps
- 12kb bundle size

### React Router v7

```typescript
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

const router = createBrowserRouter([
  { path: '/', element: <StartPage /> },
  { path: '/exam/:sessionId', element: <QuizPage /> },
  { path: '/results/:sessionId', element: <ResultsPage /> },
]);

<RouterProvider router={router} />
```

**When to use:** Existing React Router codebases. Advanced features (type safety, data loading) require framework mode in v7.

### Routing Decision

| Factor | TanStack Router | React Router v7 |
|--------|----------------|-----------------|
| **Type safety** | Full (params, search, loader) | Partial (framework mode only) |
| **Learning curve** | Moderate | Low (if already using RR) |
| **Ecosystem** | Growing | Established |
| **Bundle size** | 12kb | ~15kb |
| **Best for** | Greenfield, SPA, type-safe apps | Existing RR codebases |

---

## Styling

### Tailwind CSS v4 (Recommended Default)

Utility-first CSS with JIT compilation (Rust-based compiler):

```typescript
function Button({ variant = 'primary', children }) {
  const base = 'px-4 py-2 rounded-lg font-medium transition-colors';
  const variants = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700',
    secondary: 'bg-gray-200 text-gray-800 hover:bg-gray-300',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  };
  return <button className={`${base} ${variants[variant]}`}>{children}</button>;
}
```

**Benefits:** Zero unused CSS, consistent design tokens, rapid development, no naming overhead.

### CSS Modules (For Component-Specific Styles)

```typescript
// Button.module.css
.button { padding: 0.5rem 1rem; border-radius: 0.5rem; }
.primary { background: var(--color-primary); color: white; }

// Button.tsx
import styles from './Button.module.css';
function Button({ variant, children }) {
  return <button className={`${styles.button} ${styles[variant]}`}>{children}</button>;
}
```

**Benefits:** Locally scoped class names, no collisions, works with any preprocessor.

### CSS Variables for Theming

```css
:root {
  --color-primary: #232f3e;
  --color-accent: #ff9900;
  --color-success: #1a7f37;
  --color-error: #cf222e;
  --color-bg: #f6f8fa;
  --color-card: #ffffff;
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-mono: 'Fira Code', monospace;
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 1rem;
}

[data-theme='dark'] {
  --color-bg: #0d1117;
  --color-card: #161b22;
  --color-primary: #58a6ff;
}
```

### Styling Decision

| Approach | Best For | Trade-offs |
|----------|----------|------------|
| **Tailwind CSS** | Most projects, rapid dev | Learning curve, verbose JSX |
| **CSS Modules** | Custom designs, complex animations | More files, no utility classes |
| **Panda CSS** | Type-safe design systems | Newer, smaller ecosystem |
| **Vanilla Extract** | Build-time CSS-in-JS | Steeper setup |
| **Emotion/SC** | Legacy projects | Runtime overhead, avoid for new projects |

---

## Accessibility

### Semantic HTML First

Use native elements before ARIA:

```typescript
// Good — semantic HTML provides accessibility
<button onClick={handleSubmit}>Submit</button>
<nav><ul><li><a href="/home">Home</a></li></ul></nav>
<main><h1>Page Title</h1></main>

// Bad — divs with ARIA recreating native behavior
<div role="button" tabIndex={0} onClick={handleSubmit}>Submit</div>
<div role="navigation"><div role="list"><div role="listitem">...</div></div></div>
```

**Principle:** "No ARIA is better than bad ARIA." Use ARIA only when native HTML elements cannot achieve the desired behavior.

### React Aria (Adobe)

For complex interactive widgets (comboboxes, date pickers, drag-and-drop):

```typescript
import { useButton } from 'react-aria';

function Button(props) {
  const ref = useRef(null);
  const { buttonProps } = useButton(props, ref);
  return <button {...buttonProps} ref={ref}>{props.children}</button>;
}
```

**Provides:** Keyboard navigation, screen reader announcements, focus management, ARIA attributes — all handled automatically.

### Keyboard Navigation

Ensure all interactive elements are keyboard-accessible:

```typescript
function OptionList({ options, onSelect }) {
  const [focusIndex, setFocusIndex] = useState(0);

  const handleKeyDown = (e: KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusIndex((i) => Math.min(i + 1, options.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusIndex((i) => Math.max(i - 1, 0));
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        onSelect(options[focusIndex]);
        break;
    }
  };

  return (
    <div role="listbox" onKeyDown={handleKeyDown}>
      {options.map((option, i) => (
        <div
          key={option.id}
          role="option"
          aria-selected={i === focusIndex}
          tabIndex={i === focusIndex ? 0 : -1}
          onClick={() => onSelect(option)}
        >
          {option.label}
        </div>
      ))}
    </div>
  );
}
```

### WCAG AA Compliance Checklist

| Requirement | Guideline | How to Verify |
|-------------|-----------|---------------|
| Text contrast | 4.5:1 minimum (3:1 for large text) | Browser DevTools contrast checker |
| Focus visible | All focusable elements have visible indicator | Tab through page |
| Keyboard operable | All functionality available via keyboard | Unplug mouse, navigate app |
| Labels | All form inputs have associated labels | axe DevTools audit |
| Alt text | All meaningful images have alt text | axe DevTools audit |
| Heading structure | Headings follow logical hierarchy (h1 → h2 → h3) | Heading map tool |
| Live regions | Dynamic content changes announced to screen readers | Test with VoiceOver/NVDA |
| Error identification | Form errors identify the field and describe the issue | Submit invalid form |

### Focus Management

For SPAs, manage focus on route changes and dynamic content:

```typescript
// Announce route changes
function RouteAnnouncer() {
  const location = useLocation();
  const [announcement, setAnnouncement] = useState('');

  useEffect(() => {
    const title = document.title;
    setAnnouncement(`Navigated to ${title}`);
  }, [location]);

  return (
    <div aria-live="assertive" aria-atomic="true" className="sr-only">
      {announcement}
    </div>
  );
}
```

### Testing Accessibility

- **axe DevTools** — browser extension for automated audit
- **Lighthouse** — accessibility score in Chrome DevTools
- **VoiceOver (macOS)** / **NVDA (Windows)** — manual screen reader testing
- **jest-axe** / **vitest-axe** — automated a11y checks in component tests:

```typescript
import { axe } from 'vitest-axe';

it('has no accessibility violations', async () => {
  const { container } = render(<QuestionDisplay question={mockQuestion} />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```
