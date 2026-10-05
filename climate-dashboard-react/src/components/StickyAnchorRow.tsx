import { useEffect, useRef, type ReactNode } from 'react';

export const STICKY_HEADER_PX = 68;

/** The sticky anchor row of an Area 2 page (requirements §2.2): pinned just below the app header. */
export function StickyAnchorRow({ innerRef, children }: { innerRef: (el: HTMLDivElement | null) => void; children: ReactNode }) {
  return (
    <div ref={innerRef} style={{ marginBottom: 16, position: 'sticky', top: STICKY_HEADER_PX, zIndex: 5, background: 'var(--__s9cmpx-static-background-weak)', padding: '4px 0' }}>
      <style>{ANCHOR_ROW_STYLES}</style>
      {children}
    </div>
  );
}

/** The row's layout: wrapping on larger screens; on a phone (decision 69) one horizontally scrolling line, scrollbar hidden, with a soft fade at the trailing edge. */
const ANCHOR_ROW_STYLES = `
.area2-anchor-line { display: flex; align-items: center; justify-content: space-between; gap: 4px 16px; flex-wrap: wrap; }
.area2-anchor-scroll { flex: 1 1 auto; min-width: 0; }
@media (max-width: 640px) {
  .area2-anchor-line { flex-wrap: nowrap; gap: 8px; }
  .area2-anchor-scroll { overflow-x: auto; scrollbar-width: none; -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent); mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent); }
  .area2-anchor-scroll::-webkit-scrollbar { display: none; }
  .area2-anchor-scroll nav ul { flex-wrap: nowrap !important; gap: 18px !important; padding-right: 28px !important; }
  .area2-anchor-scroll nav li { flex: none; white-space: nowrap; }
}
`;

/** The scrolling part of the row (the jump links). Scrolls the current link into view as it changes, so on a phone it stays visible. */
export function AnchorScroll({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof MutationObserver === 'undefined') return;
    const reveal = () => {
      const current = el.querySelector<HTMLElement>('[aria-current="location"]');
      if (current && el.scrollWidth > el.clientWidth) {
        // Position relative to the scroller itself (offsetLeft is relative to the offset parent, which can be the sticky row, so it would count the leading year chip too).
        // Only the row's own horizontal scroll: never move the page.
        const box = el.getBoundingClientRect();
        const link = current.getBoundingClientRect();
        const left = el.scrollLeft + (link.left - box.left) - (el.clientWidth - link.width) / 2;
        el.scrollTo({ left: Math.max(0, left) });
      }
    };
    // Re-reveal when links are inserted (data arriving), when a link arrives already current, when the current one changes, and when the row's size changes (e.g. desktop -> phone).
    const mo = new MutationObserver(reveal);
    mo.observe(el, { attributes: true, attributeFilter: ['aria-current'], childList: true, subtree: true });
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(reveal) : null;
    ro?.observe(el);
    reveal();
    return () => { mo.disconnect(); ro?.disconnect(); };
  }, []);
  return <div ref={ref} className="area2-anchor-scroll">{children}</div>;
}
