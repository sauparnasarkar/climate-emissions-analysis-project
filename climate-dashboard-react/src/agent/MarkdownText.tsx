import { Children, isValidElement, type ComponentProps, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Table } from 'design-system';

// design-system's index.ts doesn't export TableColumn separately (same situation as SyChartSeries
// in WidgetRenderer.tsx) -- derived via ComponentProps rather than adding a design-system export
// for a single-app frontend PR.
type TableColumnType = ComponentProps<typeof Table>['columns'][number];
// Record<string, unknown>, not Record<string, ReactNode> -- Table's own Row generic defaults to
// unknown values (it's a general-purpose grid component, not markdown-specific), so `render`
// below must cast back to ReactNode at the point each cell is actually rendered.
type TableRow = Record<string, unknown>;

function childrenOf(node: ReactNode): ReactNode[] {
  return isValidElement(node) ? Children.toArray((node.props as { children?: ReactNode }).children) : [];
}

// react-markdown (via remark-gfm) always gives a GFM table's `table` override exactly one
// <thead><tr><th>...</th></tr></thead> and one <tbody><tr><td>...</td></tr>...</tbody> as
// children, already rendered to real React elements with inline formatting (bold, etc.) resolved
// -- reshaping that fixed, predictable structure into design-system's Table columns/rows is more
// robust than re-parsing raw markdown source, and doesn't need a custom remark plugin. Preserves
// each cell's actual React content (e.g. a bolded country name) via `render`, rather than
// flattening to plain text.
function MarkdownTable({ children }: { children?: ReactNode }) {
  const sections = Children.toArray(children);
  const thead = sections.find((s) => isValidElement(s) && s.type === 'thead');
  const tbody = sections.find((s) => isValidElement(s) && s.type === 'tbody');
  const headerCells = childrenOf(childrenOf(thead)[0]);
  const bodyRows = childrenOf(tbody);

  const columns: TableColumnType[] = headerCells.map((cell, i) => ({
    key: `c${i}`,
    header: isValidElement(cell) ? (cell.props as { children?: ReactNode }).children : cell,
    render: (row: TableRow) => row[`c${i}`] as ReactNode,
  }));
  const rows: TableRow[] = bodyRows.map((row) => {
    const cells = childrenOf(row);
    const obj: TableRow = {};
    cells.forEach((cell, i) => {
      obj[`c${i}`] = isValidElement(cell) ? (cell.props as { children?: ReactNode }).children : cell;
    });
    return obj;
  });

  return (
    <div style={{ overflowX: 'auto' }}>
      <Table columns={columns} rows={rows} size="small" striped="even" rowBorders />
    </div>
  );
}

// Renders response_text / a text widget's props.text as real markdown -- headers, bold, and GFM
// tables -- via react-markdown's component-mapping API (real React elements, never
// dangerouslySetInnerHTML) and, for tables specifically, this app's own design-system Table
// component (SPEC.md correction #22). Needed once ui_selection_node started surfacing agent_node's
// own unconstrained answers directly: unlike compose_response_node's tightly-scoped 2-4 sentence
// summaries, those answers are Claude's natural, often table-and-header-rich writing style for a
// detailed comparison, and showing the raw `##`/`**`/`|---|` syntax as plain text reads as broken,
// not just unstyled. Headers/paragraphs/lists are mapped onto this app's existing __s9cmpx-*
// typography classes (see AboutPage.tsx for the same headline2/5/6 hierarchy) rather than
// design-system's Typography component -- no page in this app uses Typography yet, so adopting it
// only here would be an unexplained inconsistency, not a real improvement.
export function MarkdownText({ text }: { text: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="__s9cmpx-headline5" style={{ margin: '4px 0' }}>{children}</h1>,
          h2: ({ children }) => <h2 className="__s9cmpx-headline6" style={{ margin: '4px 0' }}>{children}</h2>,
          h3: ({ children }) => (
            <h3 className="__s9cmpx-body3" style={{ margin: '4px 0', fontWeight: 600 }}>
              {children}
            </h3>
          ),
          p: ({ children }) => <p className="__s9cmpx-body3" style={{ margin: 0 }}>{children}</p>,
          ul: ({ children }) => <ul style={{ margin: 0, paddingLeft: 20 }}>{children}</ul>,
          ol: ({ children }) => <ol style={{ margin: 0, paddingLeft: 20 }}>{children}</ol>,
          li: ({ children }) => (
            <li className="__s9cmpx-body3" style={{ margin: '2px 0' }}>
              {children}
            </li>
          ),
          strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
          table: MarkdownTable,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
