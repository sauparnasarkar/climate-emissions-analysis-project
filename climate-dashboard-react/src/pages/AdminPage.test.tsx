import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { adminApi } from '../admin/adminClient';
import type { LlmChoice } from '../admin/types';
import AdminPage from './AdminPage';

vi.mock('../admin/adminClient', () => ({ adminApi: { getLlmChoice: vi.fn(), setLlmChoice: vi.fn() } }));

const SONNET_CHOICE: LlmChoice = { provider: 'anthropic', model: 'claude-sonnet-5', label: 'Claude Sonnet 5 (Anthropic)', updated_at: '2026-01-01T00:00:00+00:00' };
const OLLAMA_CHOICE: LlmChoice = { provider: 'ollama', model: 'qwen2.5:14b-ctx8k', label: 'Qwen 2.5 14B (local, 8k ctx)', updated_at: '2026-01-02T00:00:00+00:00' };

afterEach(() => {
  vi.clearAllMocks();
});

describe('AdminPage', () => {
  it('shows a loading state before getLlmChoice resolves', () => {
    vi.mocked(adminApi.getLlmChoice).mockReturnValue(new Promise(() => {}));
    render(<AdminPage />);

    expect(screen.getByText('Loading current model…')).toBeInTheDocument();
  });

  it('shows an error state if getLlmChoice fails', async () => {
    vi.mocked(adminApi.getLlmChoice).mockRejectedValue(new Error('network error'));
    render(<AdminPage />);

    expect(await screen.findByText(/Could not load the current model/)).toBeInTheDocument();
  });

  it('renders both allow-list options with the live choice selected, once loaded', async () => {
    vi.mocked(adminApi.getLlmChoice).mockResolvedValue(SONNET_CHOICE);
    render(<AdminPage />);

    const sonnetOption = await screen.findByRole('radio', { name: 'Claude Sonnet 5 (Anthropic)' });
    const ollamaOption = screen.getByRole('radio', { name: 'Qwen 2.5 14B (local, 8k ctx)' });
    expect(sonnetOption).toBeChecked();
    expect(ollamaOption).not.toBeChecked();
  });

  it('applying the currently-selected option is disabled', async () => {
    vi.mocked(adminApi.getLlmChoice).mockResolvedValue(SONNET_CHOICE);
    render(<AdminPage />);

    await screen.findByRole('radio', { name: 'Claude Sonnet 5 (Anthropic)' });
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  });

  it('selecting a different option and applying calls setLlmChoice and shows a success alert', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getLlmChoice).mockResolvedValue(SONNET_CHOICE);
    vi.mocked(adminApi.setLlmChoice).mockResolvedValue(OLLAMA_CHOICE);
    render(<AdminPage />);

    await user.click(await screen.findByRole('radio', { name: 'Qwen 2.5 14B (local, 8k ctx)' }));
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    await waitFor(() => expect(adminApi.setLlmChoice).toHaveBeenCalledWith('ollama-qwen14b-ctx8k'));
    expect(await screen.findByText('Switched to Qwen 2.5 14B (local, 8k ctx).')).toBeInTheDocument();
  });

  it('a failed apply shows the curated error message, not a raw exception', async () => {
    const user = userEvent.setup();
    vi.mocked(adminApi.getLlmChoice).mockResolvedValue(SONNET_CHOICE);
    vi.mocked(adminApi.setLlmChoice).mockRejectedValue(new Error('Could not switch models -- the new configuration failed to initialize. Still running: Claude Sonnet 5 (Anthropic).'));
    render(<AdminPage />);

    await user.click(await screen.findByRole('radio', { name: 'Qwen 2.5 14B (local, 8k ctx)' }));
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(await screen.findByText(/Could not switch models/)).toBeInTheDocument();
  });
});
