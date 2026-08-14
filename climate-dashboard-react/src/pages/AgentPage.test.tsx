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
});
