import { useEffect, useState } from 'react';

/** Slack (px) so a section whose top is just under the pinned rows still counts as reached. */
const REACHED_SLACK_PX = 4;

/** Which section is current while the page scrolls: the last one whose top has passed under the pinned header + anchor row (`offsetPx` from the viewport top),
 * the first one above that, and the last one once the page can scroll no further (a short final section never reaches the top). Ids that have no element yet
 * (data still loading) are skipped. Feeds JumpLinks' `activeId`, so the underline follows the reader, not just the last click. */
export function useScrollSpy(ids: readonly string[], offsetPx: number): string | undefined {
  const key = ids.join('|');
  const [active, setActive] = useState<string | undefined>(ids[0]);
  useEffect(() => {
    const list = key ? key.split('|') : [];
    let frame = 0;
    const compute = () => {
      frame = 0;
      const present = list.map((id) => ({ id, el: document.getElementById(id) })).filter((s): s is { id: string; el: HTMLElement } => s.el !== null);
      if (!present.length) return setActive(list[0]);
      const atBottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      let current = present[0].id;
      for (const s of present) if (s.el.getBoundingClientRect().top <= offsetPx + REACHED_SLACK_PX) current = s.id;
      // Only at the very bottom, and only if some scrolling happened (a page that fits the screen stays on its first section).
      if (atBottom && window.scrollY > 0) current = present[present.length - 1].id;
      setActive(current);
    };
    const schedule = () => { if (!frame) frame = window.requestAnimationFrame(compute); };
    compute();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [key, offsetPx]);
  return active;
}
