---
name: react-development
description: "This skill should be used when developing React applications requiring production-grade architecture, modern state management, type-safe patterns, or performance optimization. Provides guidance on React 19 features, Zustand/TanStack Query, TypeScript strict patterns, component composition, and accessibility for React 18+/19 projects."
---

# React Development Best Practices

## Purpose

This skill provides production-grade React development guidance based on the 2026 ecosystem. It covers state management, component architecture, performance optimization, TypeScript patterns, and accessibility — applicable to any React 18+/19 project.

## When to Use This Skill

This skill should be used when:
- Starting a new React project and need architectural guidance
- Choosing between state management approaches (Zustand, TanStack Query, Context, local state)
- Setting up data fetching with TanStack Query v5
- Implementing component patterns (error boundaries, Suspense, headless UI)
- Optimizing performance (React Compiler, virtualization, code splitting)
- Setting up TypeScript strict patterns for React components
- Implementing accessibility (React Aria, keyboard navigation, WCAG compliance)
- Choosing between styling approaches (Tailwind, CSS Modules, CSS-in-JS)
- Deciding on project architecture (feature-based, Feature-Sliced Design)
- Setting up routing (React Router v7, TanStack Router)

## How to Use This Skill

### State Management

For questions about Zustand setup, TanStack Query, or choosing between state management tools:
- Consult `references/state-management.md` for Zustand slice pattern, persist middleware, TanStack Query v5 patterns, and the decision matrix

**Example questions:**
- "How should I structure my Zustand store?"
- "When should I use TanStack Query vs Zustand?"
- "How do I set up persist middleware with partialize?"
- "How do I implement optimistic updates with TanStack Query?"

### Component Patterns

For component architecture, error handling, forms, and UI composition:
- Consult `references/component-patterns.md` for headless UI, error boundaries, Suspense, compound components, and form handling

**Example questions:**
- "How do I set up error boundaries in React?"
- "Should I use Radix UI or shadcn/ui?"
- "How do I implement React Hook Form with Zod validation?"
- "What's the compound component pattern?"

### Performance

For React Compiler, memoization, virtualization, and code splitting:
- Consult `references/performance-and-compiler.md` for React Compiler 1.0, the "use memo" directive, virtualization strategies, and lazy loading

**Example questions:**
- "Do I still need useMemo and useCallback?"
- "How do I set up React Compiler?"
- "When should I use virtualization?"
- "How do I implement code splitting?"

### TypeScript

For strict mode, type patterns, and type-safe APIs:
- Consult `references/typescript-patterns.md` for strict configuration, satisfies operator, discriminated unions, generic components, and type-safe API clients

**Example questions:**
- "How do I use the satisfies operator?"
- "How do I type React component props with discriminated unions?"
- "How do I generate a type-safe API client from OpenAPI?"
- "What TypeScript strict settings should I enable?"

### Architecture

For project structure, routing, styling, API layer, and accessibility:
- Consult `references/architecture.md` for Feature-Sliced Design, custom hooks, routing choices, styling strategies, and WCAG compliance

**Example questions:**
- "How should I organize a large React project?"
- "Should I use React Router v7 or TanStack Router?"
- "How do I set up Tailwind CSS with CSS Modules?"
- "How do I implement keyboard navigation?"

## Core Principles

1. **React Compiler over manual memoization** — Stop reaching for useMemo/useCallback. Let the compiler handle it. Use "use memo" only for explicit control.
2. **Server state vs client state — never mix** — TanStack Query for API data (caching, invalidation, refetching). Zustand for client-only state (UI, selections, navigation). Mixing them creates synchronization bugs.
3. **Feature-based architecture for apps >10 components** — Group by feature, not by type. Each feature owns its components, hooks, API calls, and types.
4. **Strict TypeScript with discriminated unions** — Enable strict mode. Use satisfies + as const for config objects. Use discriminated unions for polymorphic props and API responses.
5. **Semantic HTML first, ARIA when needed** — Use native elements (<button>, <nav>, <label>) before adding ARIA attributes. "No ARIA is better than bad ARIA."
6. **Error boundaries at every feature boundary** — Not just at the root. Isolate failures so only the affected feature crashes.
7. **Zero-runtime styling** — Tailwind CSS v4 or CSS Modules. Avoid runtime CSS-in-JS (styled-components, Emotion) in new projects.
