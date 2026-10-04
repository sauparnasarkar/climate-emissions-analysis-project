import { useEffect, useState } from 'react';

/** The window's inner height in px, kept current on resize. Used to size the landing carousel so a banner and its
 * controls fit above the fold on a laptop. */
export function useViewportHeight(): number {
  const [height, setHeight] = useState(() => (typeof window === 'undefined' ? 900 : window.innerHeight));
  useEffect(() => {
    const onResize = () => setHeight(window.innerHeight);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return height;
}
