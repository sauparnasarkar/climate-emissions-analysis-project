import { useEffect, useState, type RefObject } from 'react';

/** Whether any part of the element is on screen, kept current as the page scrolls. True where IntersectionObserver does not exist (nothing to measure with). */
export function useInView(ref: RefObject<Element | null>): boolean {
  const [inView, setInView] = useState(true);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);
  return inView;
}
