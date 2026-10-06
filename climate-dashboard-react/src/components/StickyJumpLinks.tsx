import { useState } from 'react';
import { JumpLinks } from 'design-system';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';

import { useElementHeight } from '../hooks/useElementHeight';
import { useScrollSpy } from '../hooks/useScrollSpy';
import { AnchorScroll, STICKY_HEADER_PX, StickyAnchorRow } from './StickyAnchorRow';

const JUMP_ROW_PX = 52; // the row's height plus a gap on one line, until it has been measured
const JUMP_ROW_GAP_PX = 10;

/** The page's jump links, pinned under the app header while the page scrolls (as on Overview and Climate Correlation), with the current section underlined as the reader scrolls.
 * Also makes jump targets clear the header and this row (`scroll-margin-top`), for as long as the page is mounted. */
export function StickyJumpLinks({ items }: { items: JumpLinkItem[] }) {
  const [row, setRow] = useState<HTMLElement | null>(null);
  const rowHeight = useElementHeight(row);
  const offset = STICKY_HEADER_PX + (rowHeight ? Math.ceil(rowHeight) + JUMP_ROW_GAP_PX : JUMP_ROW_PX);
  const activeId = useScrollSpy(items.map((i) => i.id), offset);
  return (
    <StickyAnchorRow innerRef={setRow}>
      <style>{`[id] { scroll-margin-top: ${offset}px; }`}</style>
      <div className="area2-anchor-line">
        <AnchorScroll>
          <JumpLinks items={items} activeId={activeId} />
        </AnchorScroll>
      </div>
    </StickyAnchorRow>
  );
}
