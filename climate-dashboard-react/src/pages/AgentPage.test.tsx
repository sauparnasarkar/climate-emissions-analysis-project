import { render, screen, waitFor, within } from '@testing-library/react';
import { useRef } from 'react';
import { useRouteAnnouncements } from '../hooks/useRouteAnnouncements';
import { Link, MemoryRouter, Route, Routes } from 'react-router-dom';
import { AskThreadProvider } from '../agent/AskThreadProvider';
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


function page() {
  return (
    <MemoryRouter>
      <AskThreadProvider>
        <AgentPage />
      </AskThreadProvider>
    </MemoryRouter>
  );
}

function renderPage() {
  return render(page());
}

function resultOf(overrides: Partial<AgentQueryResult> = {}): AgentQueryResult {
  return { thread_id: 't1', widgets: [], response_text: 'Some answer.', scope_notes: [], suggested_prompts: [], percent: 100, ...overrides };
}

const METHOD_WIDGET = { intent: 'text' as const, chart_kind: null, title: 'Methodology', as_of: null, source_tool_call: 'get_methodology_notes:{}', props: { data_provenance: 'OWID CO2 dataset.' } };

describe('AgentPage', () => {
  it('shows the empty state: title, hint, three category columns with a NEW tag on Climate outcomes', () => {
    stubStream({});
    renderPage();
    expect(screen.getByRole('heading', { name: 'Ask about emissions and climate outcomes' })).toBeInTheDocument();
    expect(screen.getByText('Enter to send · Shift + Enter for a new line')).toBeInTheDocument();
    for (const name of ['Historical trends', 'Climate outcomes', 'Forecasts']) {
      expect(screen.getByRole('region', { name })).toBeInTheDocument();
    }
    expect(within(screen.getByRole('region', { name: 'Climate outcomes' })).getByText('NEW')).toBeInTheDocument();
    for (const name of ['Historical trends', 'Climate outcomes', 'Forecasts']) {
      expect(within(screen.getByRole('region', { name })).getAllByRole('button')).toHaveLength(2);
    }
  });

  it('prefills a starter card on click, focuses the textarea, and does not submit', async () => {
    const submit = vi.fn();
    stubStream({ submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    renderPage();
    const prompt = 'What are the top 10 forecasted emitters in 2040?';
    await user.click(screen.getByText(prompt));
    expect(submit).not.toHaveBeenCalled();
    const textarea = screen.getByDisplayValue(prompt);
    expect(textarea).toHaveFocus();
  });

  it('shows the question heading, progress and a skeleton while loading', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'China trends{Enter}');
    stream.loading = true;
    stream.progress = { label: 'Fetching historical emissions for China', percent: 30 };
    rerender(page());
    expect(screen.getByRole('heading', { level: 2, name: 'China trends' })).toBeInTheDocument();
    expect(screen.getByText('Fetching historical emissions for China')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Loading the answer' })).toBeInTheDocument();
  });

  it('submits a typed question, shows it as an h2 with its category once the answer lands, and keeps earlier answers in order', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    const input = screen.getByLabelText('Ask about climate emissions');

    await user.type(input, 'What are the top 10 forecasted emitters in 2040?{Enter}');
    expect(stream.submit).toHaveBeenCalledWith('What are the top 10 forecasted emitters in 2040?', null);
    stream.result = resultOf({ widgets: [METHOD_WIDGET], response_text: 'First answer.', follow_up_prompts: ['Why?'] });
    rerender(page());
    expect(screen.getByRole('heading', { level: 2, name: 'What are the top 10 forecasted emitters in 2040?' })).toBeInTheDocument();
    expect(screen.getByText('Forecasts')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Second question{Enter}');
    expect(stream.submit).toHaveBeenLastCalledWith('Second question', 't1');
    stream.result = resultOf({ thread_id: 't1', widgets: [METHOD_WIDGET], response_text: 'Second answer.' });
    rerender(page());
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(['What are the top 10 forecasted emitters in 2040?', 'Second question']);
  });

  it('shows follow-up chips that prefill (not send), and "+ New question" returns to the empty state', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Q1{Enter}');
    stream.result = resultOf({ widgets: [METHOD_WIDGET], follow_up_prompts: ['How has the mix changed?'] });
    rerender(page());

    const submitCalls = vi.mocked(stream.submit).mock.calls.length;
    await user.click(screen.getByRole('button', { name: 'How has the mix changed?' }));
    expect(vi.mocked(stream.submit).mock.calls.length).toBe(submitCalls);
    expect(screen.getByDisplayValue('How has the mix changed?')).toHaveFocus();

    vi.mocked(stream.reset).mockImplementation(() => {
      stream.result = null;
    });
    await user.click(screen.getByRole('button', { name: '+ New question' }));
    expect(stream.reset).toHaveBeenCalled();
    rerender(page());
    expect(screen.getByRole('heading', { name: 'Ask about emissions and climate outcomes' })).toBeInTheDocument();
  });

  it('renders deep links as in-app links carrying the route as given', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Q1{Enter}');
    stream.result = resultOf({ widgets: [METHOD_WIDGET], follow_up_links: [{ label: 'Open in Climate Correlation', route: '/climate-correlation#scenarios' }] });
    rerender(page());
    expect(screen.getByRole('link', { name: /Open in Climate Correlation/ })).toHaveAttribute('href', '/climate-correlation#scenarios');
  });

  it('shows a stream error with Try again, resubmits the same question, and restores the typed text', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'My question{Enter}');
    stream.error = 'Connection to the agent failed.';
    rerender(page());
    expect(screen.getByText('Connection to the agent failed.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('My question')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(stream.submit).toHaveBeenLastCalledWith('My question', null);
  });

  it('off-topic/opinion results (no widgets) render as an alert with "Try instead" tiles that prefill', async () => {
    const submit = vi.fn();
    const stream = mutableStream({ submit });
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Who is right?{Enter}');
    stream.result = resultOf({ response_text: "I can't offer opinions.", suggested_prompts: ['How has growth changed in China?'] });
    rerender(page());
    expect(screen.getByText("I can't offer opinions.")).toBeInTheDocument();
    await user.click(screen.getByText('How has growth changed in China?'));
    expect(screen.getByDisplayValue('How has growth changed in China?')).toHaveFocus();
    expect(submit).toHaveBeenCalledTimes(1);
  });

  it('renders scope_notes, the lead and the KPI row for a data answer', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'China?{Enter}');
    stream.result = resultOf({
      widgets: [METHOD_WIDGET],
      response_text: 'China emitted 12,289 Mt of CO₂ in 2024.',
      scope_notes: ['Capped to the 10 highest-value countries.'],
      kpis: [{ label: 'CO₂ emissions', value: 12289, unit: 'Mt', decimals: 0, year: 2024, sub: 'Largest of 215 countries', series: null }],
    });
    rerender(page());
    expect(screen.getByText('Capped to the 10 highest-value countries.')).toBeInTheDocument();
    expect(screen.getByText('China emitted 12,289 Mt of CO₂ in 2024.')).toBeInTheDocument();
    const cards = within(screen.getByRole('list', { name: 'Key figures' })).getAllByRole('listitem');
    expect(cards[0]).toHaveTextContent('CO₂ emissions · 2024');
    expect(screen.getByText('OWID CO2 dataset.')).toBeInTheDocument();
  });

  it('renders a context_reuse answer once, as markdown, not as an alert', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const { rerender } = renderPage();
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'More on India{Enter}');
    const text = '## India\n\n**India** is growing fast.';
    stream.result = resultOf({
      widgets: [{ intent: 'text', chart_kind: null, title: 'Answer', as_of: null, source_tool_call: 'context_reuse', props: { text } }],
      response_text: text,
    });
    rerender(page());
    expect(screen.getAllByText(/is growing fast/)).toHaveLength(1);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('keeps the thread when the page is left and opened again (in-memory, above the routes)', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const app = () => (
      <MemoryRouter initialEntries={['/ask']}>
        <AskThreadProvider>
          <Link to="/ask">ask</Link>
          <Link to="/elsewhere">elsewhere</Link>
          <Routes>
            <Route path="/ask" element={<AgentPage />} />
            <Route path="/elsewhere" element={<p>another page</p>} />
          </Routes>
        </AskThreadProvider>
      </MemoryRouter>
    );
    const { rerender } = render(app());
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Q1{Enter}');
    stream.result = resultOf({ widgets: [METHOD_WIDGET], response_text: 'First answer.' });
    rerender(app());
    expect(screen.getByRole('heading', { level: 2, name: 'Q1' })).toBeInTheDocument();

    await user.type(screen.getByLabelText('Ask about climate emissions'), 'half typed');
    await user.click(screen.getByRole('link', { name: 'elsewhere' }));
    expect(screen.getByText('another page')).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'ask' }));

    expect(screen.getByRole('heading', { level: 2, name: 'Q1' })).toBeInTheDocument();
    expect(screen.getByText('First answer.')).toBeInTheDocument();
    expect(screen.getByDisplayValue('half typed')).toBeInTheDocument();
    // a question asked now continues the same thread
    await user.clear(screen.getByLabelText('Ask about climate emissions'));
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Q2{Enter}');
    expect(stream.submit).toHaveBeenLastCalledWith('Q2', 't1');
  });

  it('captures an answer that lands while the user is on another page', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const app = () => (
      <MemoryRouter initialEntries={['/ask']}>
        <AskThreadProvider>
          <Link to="/ask">ask</Link>
          <Link to="/elsewhere">elsewhere</Link>
          <Routes>
            <Route path="/ask" element={<AgentPage />} />
            <Route path="/elsewhere" element={<p>another page</p>} />
          </Routes>
        </AskThreadProvider>
      </MemoryRouter>
    );
    const { rerender } = render(app());
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Slow one{Enter}');
    stream.loading = true;
    rerender(app());
    await user.click(screen.getByRole('link', { name: 'elsewhere' }));
    stream.loading = false;
    stream.result = resultOf({ widgets: [METHOD_WIDGET], response_text: 'Landed while away.' });
    rerender(app());
    await user.click(screen.getByRole('link', { name: 'ask' }));
    expect(screen.getByRole('heading', { level: 2, name: 'Slow one' })).toBeInTheDocument();
    expect(screen.getByText('Landed while away.')).toBeInTheDocument();
  });

  it('restores the scroll position on return, after the layout resets it to the top', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const scrollTo = vi.fn();
    vi.stubGlobal('scrollTo', scrollTo);
    let y = 0;
    Object.defineProperty(window, 'scrollY', { configurable: true, get: () => y });
    // The same route-change scroll reset the real layout applies (useRouteAnnouncements), so the test fails if the restore does not outlast it.
    function Shell() {
      const ref = useRef<HTMLElement>(null);
      useRouteAnnouncements(ref);
      return (
        <main ref={ref} tabIndex={-1}>
          <Link to="/ask">ask</Link>
          <Link to="/elsewhere">elsewhere</Link>
          <Routes>
            <Route path="/ask" element={<AgentPage />} />
            <Route path="/elsewhere" element={<p>another page</p>} />
          </Routes>
        </main>
      );
    }
    const app = () => (
      <MemoryRouter initialEntries={['/ask']}>
        <AskThreadProvider>
          <Shell />
        </AskThreadProvider>
      </MemoryRouter>
    );
    const { rerender } = render(app());
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Q1{Enter}');
    stream.result = resultOf({ widgets: [METHOD_WIDGET], response_text: 'First answer.' });
    rerender(app());

    y = 480;
    window.dispatchEvent(new Event('scroll'));
    await user.click(screen.getByRole('link', { name: 'elsewhere' }));
    y = 0;
    scrollTo.mockClear();
    await user.click(screen.getByRole('link', { name: 'ask' }));
    await waitFor(() => expect(scrollTo).toHaveBeenLastCalledWith(0, 480));
    vi.unstubAllGlobals();
    mockReducedMotion(false);
  });

  it('does not scroll back over an answer that lands before the queued restore frame', async () => {
    const stream = mutableStream();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    const scrollTo = vi.fn();
    vi.stubGlobal('scrollTo', scrollTo);
    const frames = new Map<number, FrameRequestCallback>();
    let nextFrame = 1;
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      frames.set(nextFrame, cb);
      return nextFrame++;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
    let y = 0;
    Object.defineProperty(window, 'scrollY', { configurable: true, get: () => y });
    const app = () => (
      <MemoryRouter initialEntries={['/ask']}>
        <AskThreadProvider>
          <Link to="/ask">ask</Link>
          <Link to="/elsewhere">elsewhere</Link>
          <Routes>
            <Route path="/ask" element={<AgentPage />} />
            <Route path="/elsewhere" element={<p>another page</p>} />
          </Routes>
        </AskThreadProvider>
      </MemoryRouter>
    );
    const { rerender } = render(app());
    await user.type(screen.getByLabelText('Ask about climate emissions'), 'Q1{Enter}');
    stream.result = resultOf({ widgets: [METHOD_WIDGET], response_text: 'First answer.' });
    rerender(app());
    y = 480;
    window.dispatchEvent(new Event('scroll'));
    await user.click(screen.getByRole('link', { name: 'elsewhere' }));
    await user.click(screen.getByRole('link', { name: 'ask' }));
    expect(frames.size).toBeGreaterThan(0); // the restore is queued

    // a second answer lands before the frame runs
    stream.result = resultOf({ thread_id: 't1', widgets: [METHOD_WIDGET], response_text: 'Late answer.' });
    rerender(app());
    expect(screen.getByText('Late answer.')).toBeInTheDocument();
    scrollTo.mockClear();
    for (const cb of [...frames.values()]) cb(0);
    expect(scrollTo).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
    mockReducedMotion(false);
  });
});
