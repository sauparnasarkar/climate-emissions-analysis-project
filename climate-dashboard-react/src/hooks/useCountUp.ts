import { useEffect, useRef, useState } from 'react';

/** Animates from the previous value (0 on first mount) to `target` over `durationMs`. */
export function useCountUp(target: number, durationMs = 1500): number {
  const [value, setValue] = useState(0);
  const fromRef = useRef(0);

  useEffect(() => {
    const from = fromRef.current;
    const to = target;
    // Same matchMedia pattern design-system's SidebarNav already uses for its own
    // transitions -- skip straight to the final value instead of animating (SPEC.md §5.10).
    // matchMedia itself (not just window) is guarded -- some non-browser/older-browser
    // environments have a window global without it, which would otherwise throw here.
    const reduceMotion =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (from === to || reduceMotion) {
      setValue(to);
      fromRef.current = to;
      return;
    }
    const start = performance.now();
    let raf: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      const eased = 1 - (1 - t) ** 3;
      setValue(from + (to - from) * eased);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, durationMs]);

  return value;
}
