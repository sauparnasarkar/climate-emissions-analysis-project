# Streamlit Curriculum

> Part of the [training document series](../00-architecture-overview.md). This folder is a
> self-contained curriculum for building a quick, single-process interactive dashboard — the
> "Option A" presentation-layer approach described in the
> [architecture overview](../00-architecture-overview.md#8-options-for-the-presentation-layer).

## Reading order

1. [**Core Concepts**](01-core-concepts.md) — the rerun-on-every-interaction mental model,
   caching, widgets, layout, session state, and forms.
2. [**Charting & Visualization**](02-charting-visualization.md) — Plotly Express and Graph
   Objects in depth, plus other charting options worth knowing about.
3. [**Testing**](03-testing.md) — Streamlit's `AppTest` framework, and a candid discussion of
   when manual verification is a reasonable alternative.
4. [**Deployment**](04-deployment.md) — Streamlit Community Cloud, containerized deployment,
   and secrets management.

## Prerequisites

Comfort with Python and basic pandas is assumed. No prior web-framework experience is
assumed — Streamlit is deliberately designed not to require one.

## See also

- [Architecture Overview](../00-architecture-overview.md) for how this approach compares to
  a decoupled API + frontend
- [Data Science / ML](../01-data-science-ml/00-index.md) for what this kind of dashboard
  typically reads and displays
- [React Front End](../04-react-frontend/00-index.md) for the alternative, decoupled approach
