# React Front-End Curriculum

> Part of the [training document series](../00-architecture-overview.md). This folder is a
> self-contained curriculum for building a decoupled, component-based frontend that consumes
> a backend API — the "Option B" presentation-layer approach described in the
> [architecture overview](../00-architecture-overview.md#8-options-for-the-presentation-layer).

## Reading order

1. [**Core Concepts**](01-core-concepts.md) — components, props, state, hooks, the
   custom-hook pattern for data fetching, and how a design system (tokens, themes,
   components, tests) is structured and consumed.
2. [**Routing & API Integration**](02-routing-api-integration.md) — client-side routing, a
   typed API client, mirroring backend response shapes, state-management options beyond
   local component state, and build-tooling concerns.
3. [**Testing**](03-testing.md) — Vitest/Jest, React Testing Library, mocking, testing
   custom hooks, testing a data-heavy dashboard's patterns, and where end-to-end testing fits.
4. [**Deployment**](04-deployment.md) — static hosting, containerized deployment, CI/CD
   for a frontend build, service-worker caching and edge-gated routes, and the case where
   the build itself is the release.
5. [**Patterns for Data-Heavy Dashboards**](05-data-heavy-dashboard-patterns.md) — view-model
   builders, independent sections, URL-backed state, a page-wide shared control, phone-sized
   variants, accessibility, theming, and embedding a conversational agent's answers.

## Prerequisites

Comfort with modern JavaScript (functions, array methods, `async`/`await`, ES modules) is
assumed. TypeScript examples are used throughout, but prior TypeScript experience is not
required — the type annotations are explained as they're introduced.

## See also

- [Architecture Overview](../00-architecture-overview.md) for how this compares to a
  single-process dashboard approach
- [Python API Backend](../02-python-api-backend/00-index.md) for the backend this frontend
  typically consumes
- [Data Science / ML](../01-data-science-ml/00-index.md) for what the underlying data being
  visualized typically represents
- [Conversational Agents](../06-conversational-agent/00-index.md) for surfacing an
  open-ended, natural-language view alongside the fixed charts/controls this curriculum builds
