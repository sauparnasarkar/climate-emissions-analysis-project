import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StarterPromptTile } from './StarterPromptTile';

describe('StarterPromptTile', () => {
  it('renders the kicker and prompt, and fires onClick on click', async () => {
    const onClick = vi.fn();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<StarterPromptTile kicker="Forecasts" prompt="What are the top 10 forecasted emitters in 2040?" onClick={onClick} />);

    expect(screen.getByText('Forecasts')).toBeInTheDocument();
    expect(screen.getByText('What are the top 10 forecasted emitters in 2040?')).toBeInTheDocument();
    await user.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('fires onClick on Enter and Space for keyboard activation', async () => {
    const onClick = vi.fn();
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    render(<StarterPromptTile kicker="Forecasts" prompt="Prompt text" onClick={onClick} />);

    screen.getByRole('button').focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');
    expect(onClick).toHaveBeenCalledTimes(2);
  });
});
