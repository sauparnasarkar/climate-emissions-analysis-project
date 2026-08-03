import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'design-system';

/** Animates from the previous value (0 on first mount) to `target` over `durationMs`. */
export function useCountUp(target: number, durationMs = 1500): number {
  const [value, setValue] = useState(0);
  const fromRef = useRef(0);
  // Live-subscribed (unlike this hook's own previous one-shot matchMedia check) -- shared
  // with design-system's SidebarNav and this app's useYearAnimation, so all three agree on
  // the current reduced-motion state without re-implementing the check three times.
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const from = fromRef.current;
    const to = target;
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
  }, [target, durationMs, reduceMotion]);

  return value;
}
