import { useId } from 'react';

/**
 * The ids a module section puts on its `<section>` and heading.
 *
 * On the Correlation page they are fixed: the section id is the page's anchor (`#scenarios`, ...) and the heading id is what the
 * section's `aria-labelledby` points at. Inside the Ask page's answer thread the same component can appear more than once (two
 * earlier answers about the relationship), and a repeated id is invalid and breaks `aria-labelledby`. `embedded` therefore drops the
 * anchor id (an anchor means nothing outside the module page) and makes the heading id unique, so a section is the same component in
 * both places and only its identifiers differ.
 */
export function useSectionIds(embedded: boolean | undefined, anchor: string, headingId: string): { sectionId: string | undefined; headingId: string } {
  const unique = useId();
  return embedded ? { sectionId: undefined, headingId: `${headingId}-${unique}` } : { sectionId: anchor, headingId };
}
