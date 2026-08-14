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

  it('sizes the starter-prompt grid so tracks shrink below 280px on a narrow viewport', () => {
    // jsdom has no real layout engine, so this can't measure actual overflow the way a real
    // browser does -- confirmed live on a real narrow viewport (labs.syena.io/ghg-emissions-
    // analysis/ask, 500px window): plain `minmax(280px, 1fr)` refuses to shrink below 280px per
    // auto-fit track, which pushed <main> to 968px wide with nothing to constrain it back to the
    // viewport. `minmax(min(280px, 100%), 1fr)` fixed it (484px). This test pins the CSS pattern
    // so a future edit can't silently revert to the overflowing literal.
    stubStream({});
    render(<AgentPage />);
    // StarterPromptTile's prompt text sits in a <span>, inside the tile's own inner flex column
    // div, inside the Tile's own root div, inside the grid -- three hops up from the text node.
    const promptText = screen.getByText('What are the top 10 forecasted emitters in 2040?');
    const tileInnerColumn = promptText.closest('div');
    const tileRoot = tileInnerColumn?.parentElement;
    const grid = tileRoot?.parentElement;
    expect(grid).not.toBeNull();
    expect((grid as HTMLElement).style.gridTemplateColumns).toContain('min(280px, 100%)');
  });

  it('prefills (but does not submit) a country-specific starter prompt on click', async () => {
    const submit = vi.fn();
    stubStream({ submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<AgentPage />);

    await user.click(screen.getByText("How has India's emissions grown compared to other countries?"));

    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("How has India's emissions grown compared to other countries?")).toBeInTheDocument();
  });

  it('submits immediately on a forecast starter prompt click (no placeholder to type over)', async () => {
    const submit = vi.fn();
    stubStream({ submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<AgentPage />);

    await user.click(screen.getByText('What are the top 10 forecasted emitters in 2040?'));

    expect(submit).toHaveBeenCalledWith('What are the top 10 forecasted emitters in 2040?', null);
  });

  it('shows a labeled Progress bar while loading, docks the PromptBar, and hides the starter grid', () => {
    stubStream({ loading: true, progress: { label: 'Fetching historical emissions for China', percent: 30 } });
    render(<AgentPage />);

    expect(screen.getByText('Fetching historical emissions for China')).toBeInTheDocument();
    expect(screen.getByText('30%')).toBeInTheDocument();
    expect(screen.queryByText('What are the top 10 forecasted emitters in 2040?')).not.toBeInTheDocument();
  });

  it('shows the starter-prompt grid again once a response lands after the loading state', () => {
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [],
      response_text: 'Some answer.',
      scope_notes: [],
      suggested_prompts: [],
      percent: 100,
    };
    const stream = mutableStream({ loading: true });
    const { rerender } = render(<AgentPage />);

    expect(screen.queryByText('What are the top 10 forecasted emitters in 2040?')).not.toBeInTheDocument();

    stream.loading = false;
    stream.result = result;
    rerender(<AgentPage />);

    // Once the result lands, the docked state should stay in place and the same four starter
    // prompts should reappear below it for the next turn.
    expect(screen.queryByText('Ask about climate emissions')).not.toBeInTheDocument();
    expect(screen.getByText('What are the top 10 forecasted emitters in 2040?')).toBeInTheDocument();
  });

  it('keeps the between-turns starter grid hidden while editing, even after clearing a prefill prompt', async () => {
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

    await user.click(screen.getByText("What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?"));
    await user.clear(screen.getByLabelText('Ask about climate emissions'));

    expect(
      screen.queryByText("What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?", { selector: 'span' }),
    ).not.toBeInTheDocument();
  });

  it('hides the between-turns starter grid immediately when an instant-submit prompt is picked', async () => {
    const result: AgentQueryResult = {
      thread_id: 't1',
      widgets: [],
      response_text: 'Some answer.',
      scope_notes: [],
      suggested_prompts: [],
      percent: 100,
    };
    const submit = vi.fn();
    stubStream({ result, submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<AgentPage />);

    await user.click(screen.getByText('What are the top 10 forecasted emitters in 2040?'));

    // threadIdRef is already 't1' from the seeded result above, not null (a genuinely fresh
    // conversation's first submit would pass null; this is a follow-up in an existing thread).
    expect(submit).toHaveBeenCalledWith('What are the top 10 forecasted emitters in 2040?', 't1');
    expect(screen.queryByText('What are the top 10 forecasted emitters in 2040?', { selector: 'span' })).not.toBeInTheDocument();
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
