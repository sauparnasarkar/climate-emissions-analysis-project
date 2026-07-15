/// <reference types="vite/client" />

// design-system is aliased to source, so its own plotly.js-dist-min import resolves
// against design-system/node_modules (no co-located @types there) — declare it ambiently.
declare module 'plotly.js-dist-min';
