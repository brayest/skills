# Performance and React Compiler

## React Compiler 1.0

### What It Does
React Compiler is a build-time tool that automatically optimizes React applications by applying memoization. It analyzes component code, determines dependencies, and inserts memoization where beneficial — all without developer intervention.

**Production results:**
- Sanity Studio: 20-30% overall reduction in render time
- Wakelet: 10% LCP improvement, 15% INP improvement
- Meta: Deployed across production React and React Native apps

### What Changes

**Before (manual):**
```typescript
const ExpensiveList = memo(({ items, filter }) => {
  const filtered = useMemo(
    () => items.filter((item) => item.matches(filter)),
    [items, filter]
  );
  const handleClick = useCallback(
    (id: string) => selectItem(id),
    [selectItem]
  );
  return filtered.map((item) => (
    <Item key={item.id} item={item} onClick={handleClick} />
  ));
});
```

**After (with React Compiler):**
```typescript
const ExpensiveList = ({ items, filter }) => {
  const filtered = items.filter((item) => item.matches(filter));
  const handleClick = (id: string) => selectItem(id);
  return filtered.map((item) => (
    <Item key={item.id} item={item} onClick={handleClick} />
  ));
};
// Compiler automatically memoizes what needs memoizing
```

### Setup

```bash
npm install -D babel-plugin-react-compiler
```

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: ['babel-plugin-react-compiler'],
      },
    }),
  ],
});
```

### The "use memo" Directive

For cases where explicit memoization control is needed:

```typescript
function Dashboard({ data }) {
  "use memo";
  // Compiler applies aggressive memoization to this component
  const processed = data.map(transform).filter(validate);
  return <Chart data={processed} />;
}
```

Use sparingly — the compiler handles most cases automatically.

### What the Compiler Does NOT Do

The compiler optimizes *how* components render, not *whether* they render. These remain developer responsibility:

- **Virtualization** — rendering only visible items in long lists
- **Code splitting** — loading only needed code
- **Architectural decisions** — component tree depth, data flow design
- **Network optimization** — request batching, caching strategy

---

## Virtualization

### When to Use
Any list or grid rendering more than ~100 items. Without virtualization, React creates DOM nodes for every item — even those not visible.

### react-window

```typescript
import { FixedSizeList } from 'react-window';

const VirtualList = ({ items }) => (
  <FixedSizeList
    height={600}
    width="100%"
    itemCount={items.length}
    itemSize={50}
  >
    {({ index, style }) => (
      <div style={style}>
        {items[index].name}
      </div>
    )}
  </FixedSizeList>
);
```

**Variants:**
- `FixedSizeList` — all items same height (fastest)
- `VariableSizeList` — items have different heights
- `FixedSizeGrid` / `VariableSizeGrid` — 2D grids

### @tanstack/react-virtual

More flexible alternative with headless design:

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

function VirtualList({ items }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 50,
  });

  return (
    <div ref={parentRef} style={{ height: 600, overflow: 'auto' }}>
      <div style={{ height: virtualizer.getTotalSize() }}>
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: virtualItem.start,
              height: virtualItem.size,
            }}
          >
            {items[virtualItem.index].name}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Code Splitting

### Route-Based Splitting (Minimum)

```typescript
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const Settings = lazy(() => import('./pages/Settings'));
const Analytics = lazy(() => import('./pages/Analytics'));

function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </Suspense>
  );
}
```

### Component-Level Splitting

For heavy components that aren't always needed:

```typescript
const Chart = lazy(() => import('./components/Chart'));
const CodeEditor = lazy(() => import('./components/CodeEditor'));

function AnalyticsPage() {
  const [showChart, setShowChart] = useState(false);

  return (
    <div>
      <button onClick={() => setShowChart(true)}>Show Chart</button>
      {showChart && (
        <Suspense fallback={<ChartSkeleton />}>
          <Chart data={data} />
        </Suspense>
      )}
    </div>
  );
}
```

### Prefetching

Preload components before they're needed:

```typescript
// Prefetch on hover
const ChartModule = () => import('./components/Chart');

function AnalyticsLink() {
  return (
    <Link
      to="/analytics"
      onMouseEnter={() => ChartModule()} // Start loading on hover
    >
      Analytics
    </Link>
  );
}
```

---

## Image Optimization

### Responsive Images

```html
<img
  srcSet="image-400.webp 400w, image-800.webp 800w, image-1200.webp 1200w"
  sizes="(max-width: 600px) 400px, (max-width: 900px) 800px, 1200px"
  src="image-800.webp"
  alt="Description"
  loading="lazy"
  decoding="async"
/>
```

### Lazy Loading

Use `loading="lazy"` for below-the-fold images. Use `loading="eager"` for above-the-fold (LCP) images.

### Modern Formats

Prefer WebP or AVIF over JPEG/PNG. Use `<picture>` for format fallbacks:

```html
<picture>
  <source srcset="image.avif" type="image/avif" />
  <source srcset="image.webp" type="image/webp" />
  <img src="image.jpg" alt="Description" />
</picture>
```

---

## General Performance Guidelines

1. **Measure first** — Use React DevTools Profiler, Lighthouse, and Web Vitals before optimizing
2. **React Compiler handles memoization** — Don't add useMemo/useCallback unless profiling shows a specific need
3. **Virtualize lists** — Any list >100 items should use react-window or @tanstack/react-virtual
4. **Split routes** — Every route should be lazy-loaded
5. **Split heavy components** — Charts, editors, maps should be lazy-loaded on demand
6. **Optimize images** — Use WebP/AVIF, responsive srcSet, lazy loading
7. **Avoid prop drilling through many levels** — Use Zustand or Context for deeply shared state
8. **Keep component trees shallow** — Deeply nested trees are harder for React to reconcile efficiently
