import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AgentPage } from './AgentPage';
import { useAgentStream } from '../agent/useAgentStream';
import type { AgentQueryResult } from '../agent/types';

vi.mock('../agent/useAgentStream', () => ({ useAgentStream: vi.fn() }));

// This page never renders a real chart/grid in these tests (results below are widget-free or
// use get_methodology_notes' plain-text path), so no design-system chart/grid stubbing is
// needed here -- WidgetRenderer.test.tsx already covers per-tool prop mapping directly.

// PromptBar calls design-system's useReducedMotion during render -- jsdom has no
// window.matchMedia at all. Same pattern as CountryProfilePage.test.tsx/ForecastsPage.test.tsx.
function mockReducedMotion(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? matches : false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function stubStream(overrides: Partial<ReturnType<typeof useAgentStream>>) {
  vi.mocked(useAgentStream).mockReturnValue({
    submit: vi.fn(),
    progress: null,
    result: null,
    error: null,
    loading: false,
    reset: vi.fn(),
    ...overrides,
  });
}

function mutableStream(overrides: Partial<ReturnType<typeof useAgentStream>> = {}) {
  const state: ReturnType<typeof useAgentStream> = {
    submit: vi.fn(),
    progress: null,
    result: null,
    error: null,
    loading: false,
    reset: vi.fn(),
    ...overrides,
  };
  vi.mocked(useAgentStream).mockImplementation(() => state);
  return state;
}

beforeEach(() => {
  mockReducedMotion(false);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('AgentPage', () => {
  it('shows the landing state: headline, landing PromptBar, and all four starter prompts', () => {
    stubStream({});
    render(<AgentPage />);

    expect(screen.getByText('Ask about climate emissions')).toBeInTheDocument();
    expect(screen.getByText('What are the top 10 forecasted emitters in 2040?')).toBeInTheDocument();
    expect(screen.getByText('Considering the top 10 emitters now and the forecasted ones in 2040, show the comparative trend for the countries.')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Send/ })).toHaveLength(1);
  });

  it('lays out the four starter prompts in a fixed 2x2 grid, not auto-fit', () => {
    // Now that this grid lives inside PromptBar's own expandedContent (a fixed-width container),
    // not a full-page one, it targets an explicit 2/3-column count the same way the response
    // widget grid does, rather than auto-fit reflowing based on available width.
    stubStream({});
    const { container } = render(<AgentPage />);

    const grid = container.querySelector('.starter-prompt-grid') as HTMLElement;
    expect(grid).not.toBeNull();
    expect(grid.style.gridTemplateColumns).toBe('repeat(2, 1fr)');
    expect(grid.children).toHaveLength(4);
  });

  it.each([
    ['country-specific', "How has India's emissions grown compared to other countries?"],
    ['forecast', 'What are the top 10 forecasted emitters in 2040?'],
  ])('prefills a %s starter prompt on click, focuses the textarea, and does not submit', async (_label, prompt) => {
    // The starter grid now lives inside PromptBar's own expandedContent (design-system PR #44) --
    // clicking a tile moves focus there first, so this also confirms the panel doesn't collapse
    // out from under the click, and that the new ref-based focus() call (closing "Corrections
    // applied" #18) actually lands the user in the textarea afterward, not stuck on the tile.
    // Both rows behave identically here (SPEC.md "Corrections applied" #26) -- the forecast row
    // used to auto-submit instead, which read as an inconsistent surprise next to this row.
    const submit = vi.fn();
    stubStream({ submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<AgentPage />);

    await user.click(screen.getByText(prompt));

    expect(submit).not.toHaveBeenCalled();
    const textarea = screen.getByDisplayValue(prompt);
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveFocus();
  });

  it('shows a labeled Progress bar and docks the PromptBar while loading', () => {
    stubStream({ loading: true, progress: { label: 'Fetching historical emissions for China', percent: 30 } });
    render(<AgentPage />);

    expect(screen.getByText('Fetching historical emissions for China')).toBeInTheDocument();
    expect(screen.getByText('30%')).toBeInTheDocument();
    // Docked never autofocuses (unlike landing), and loading itself also collapses the panel --
    // queryByRole, unlike queryByText, correctly excludes the aria-hidden tiles still in the DOM
    // (SPEC.md: the collapsed panel is aria-hidden/inert, not unmounted, per design-system's own
    // Drawer precedent).
    expect(screen.queryByRole('button', { name: /forecasted emitters/ })).not.toBeInTheDocument();
  });

  it('keeps the starter grid collapsed after a response lands -- reveals it only once the docked bar is focused', async () => {
    // Replaces the earlier "grid reappears automatically between turns" behavior: visibility is
    // now purely focus-driven (matching the user's own "expand on clicking" request), not an
    // approximated dismissed/idle-and-empty state machine.
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [],
      response_text: 'Some answer.',
      scope_notes: [],
      suggested_prompts: [],
      percent: 100,
    };
    stubStream({ result });
    render(<AgentPage />);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();

    expect(screen.queryByText('Ask about climate emissions')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /forecasted emitters/ })).not.toBeInTheDocument();

    await user.click(screen.getByLabelText('Ask about climate emissions'));
    expect(screen.getByRole('button', { name: /forecasted emitters/ })).toBeInTheDocument();
  });

  it('keeps the panel open through a prefill-and-edit, since focus stays inside the bar the whole time', async () => {
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [],
      response_text: 'Some answer.',
      scope_notes: [],
      suggested_prompts: [],
      percent: 100,
    };
    stubStream({ result });
    render(<AgentPage />);
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();

    await user.click(screen.getByLabelText('Ask about climate emissions'));
    await user.click(screen.getByText("What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?"));
    await user.clear(screen.getByLabelText('Ask about climate emissions'));

    // Clicking the tile moved focus to the textarea (this same page's own prefill+focus wiring),
    // and clearing text doesn't blur it -- so the panel is still expanded, unlike the old
    // dismissed-on-edit approximation this test used to check for.
    expect(
      screen.getByText("What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?"),
    ).toBeInTheDocument();
  });

  it('collapses the panel once an instant-submit tile triggers loading, even though the click never touches PromptBar\'s own submit path', async () => {
    // Mirrors design-system PromptBar.stories.tsx's own ExpandedContentCollapsesOnExternalSubmit:
    // a §6 suggested-prompt "Try instead" reframe tile calls the useAgentStream hook's submit()
    // directly (ResultSectionView's onSuggestedPromptClick={handleSubmit}), bypassing PromptBar's
    // internal trySubmit entirely -- only the `loading` prop turning true (which a static
    // stubStream() mock never does on its own) drives the collapse here. Starter-grid tiles no
    // longer stand in for this case now that all four prefill instead of auto-submitting
    // (SPEC.md "Corrections applied" #26) -- the reframe tile is the one remaining instant-submit
    // path left in the app.
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [],
      response_text: "I can't offer opinions, but here's what the data shows instead.",
      scope_notes: [],
      suggested_prompts: ['How has emissions growth changed in China over the last decade?'],
      percent: 100,
    };
    const submit = vi.fn();
    const stream = mutableStream({ result, submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = render(<AgentPage />);

    await user.click(screen.getByLabelText('Ask about climate emissions'));
    expect(screen.getByRole('button', { name: /forecasted emitters/ })).toBeInTheDocument();

    await user.click(screen.getByText('How has emissions growth changed in China over the last decade?'));
    // threadIdRef is already 't1' from the seeded result above, not null (a genuinely fresh
    // conversation's first submit would pass null; this is a follow-up in an existing thread).
    expect(submit).toHaveBeenCalledWith('How has emissions growth changed in China over the last decade?', 't1');

    stream.loading = true;
    rerender(<AgentPage />);
    expect(screen.queryByRole('button', { name: /forecasted emitters/ })).not.toBeInTheDocument();
  });

  it('surfaces a stream error as an InlineAlert', () => {
    stubStream({ error: 'Connection to the agent failed.' });
    render(<AgentPage />);
    expect(screen.getByText('Connection to the agent failed.')).toBeInTheDocument();
  });

  it('off_topic/opinion-shaped results (no widgets) render response_text as an InlineAlert, plus suggested_prompts as tiles', () => {
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [],
      response_text: "I can't offer opinions, but here's what the data shows instead.",
      scope_notes: [],
      suggested_prompts: ['How has emissions growth changed in China over the last decade?'],
      percent: 100,
    };
    stubStream({ result });
    render(<AgentPage />);

    expect(screen.getByText("I can't offer opinions, but here's what the data shows instead.")).toBeInTheDocument();
    expect(screen.getByText('How has emissions growth changed in China over the last decade?')).toBeInTheDocument();
  });

  it('renders scope_notes as an InlineAlert above a data_query result\'s widgets', () => {
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [
        {
          intent: 'text',
          chart_kind: null,
          title: 'Methodology',
          as_of: null,
          source_tool_call: 'get_methodology_notes:{}',
          props: { data_provenance: 'OWID CO2 dataset.' },
        },
      ],
      response_text: 'Here is the requested methodology summary.',
      scope_notes: ['Capped to the 10 highest-value countries.'],
      suggested_prompts: [],
      percent: 100,
    };
    stubStream({ result });
    render(<AgentPage />);

    expect(screen.getByText('Capped to the 10 highest-value countries.')).toBeInTheDocument();
    expect(screen.getByText('Here is the requested methodology summary.')).toBeInTheDocument();
    expect(screen.getByText('OWID CO2 dataset.')).toBeInTheDocument();
  });

  it('renders a context_reuse answer as a normal markdown response, not an InlineAlert, with no duplicate paragraph', () => {
    // SPEC.md correction #22: a turn that answered from prior context (zero new tool calls)
    // carries a real, often markdown-rich answer -- must render like any other data answer, not
    // like off_topic/opinion's short guardrail text (InlineAlert), and not duplicated (the widget
    // and response_text are the same underlying text).
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [
        {
          intent: 'text',
          chart_kind: null,
          title: 'Answer',
          as_of: null,
          source_tool_call: 'context_reuse',
          props: { text: '## India\n\n**India** is growing fast.' },
        },
      ],
      response_text: '## India\n\n**India** is growing fast.',
      scope_notes: [],
      suggested_prompts: [],
      percent: 100,
    };
    stubStream({ result });
    render(<AgentPage />);

    expect(screen.getByRole('heading', { name: 'India' })).toBeInTheDocument();
    expect(document.querySelector('strong')?.textContent).toBe('India');
    // Only one rendering of the answer -- not also duplicated as a plain-text paragraph above it.
    expect(screen.getAllByText(/is growing fast/)).toHaveLength(1);
    // Not shown as an InlineAlert (role="status" for the "default" variant used throughout this
    // page) -- off_topic/opinion's role, not this one's.
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  function nWidgets(n: number): AgentQueryResult['widgets'] {
    return Array.from({ length: n }, (_, i) => ({
      intent: 'text' as const,
      chart_kind: null,
      title: `Widget ${i}`,
      as_of: null,
      source_tool_call: `get_methodology_notes:{"n":${i}}`,
      props: { data_provenance: `source ${i}` },
    }));
  }

  it.each([
    [1, 1],
    [2, 2],
    [3, 3],
    [4, 2], // deliberately not 4 -- a 4-up row of these cards reads as cramped
    [5, 3],
    [6, 3],
  ])('lays out %i widgets in %i columns', (widgetCount, expectedColumns) => {
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: nWidgets(widgetCount),
      response_text: 'Summary.',
      scope_notes: [],
      suggested_prompts: [],
      percent: 100,
    };
    stubStream({ result });
    const { container } = render(<AgentPage />);

    const grid = container.querySelector('.agent-widget-grid') as HTMLElement;
    expect(grid).not.toBeNull();
    expect(grid.style.gridTemplateColumns).toBe(`repeat(${expectedColumns}, 1fr)`);
    expect(grid.children).toHaveLength(widgetCount);
  });
});
