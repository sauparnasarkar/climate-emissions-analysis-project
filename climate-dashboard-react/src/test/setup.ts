import '@testing-library/jest-dom/vitest';

// jsdom doesn't implement ResizeObserver at all — design-system's DataTable uses it
// (scroll-hint sizing), so any test rendering DataTable would otherwise throw
// "ResizeObserver is not defined" as soon as its effect runs.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverStub);
