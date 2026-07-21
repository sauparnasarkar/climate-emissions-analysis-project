import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import AboutPage from './AboutPage';

describe('AboutPage', () => {
  it('renders the static methodology and data-source content without crashing', () => {
    render(<AboutPage />);

    expect(screen.getByText('About This Project')).toBeInTheDocument();
    expect(screen.getByText('Methodology Summary')).toBeInTheDocument();
    expect(screen.getByText('Data Sources')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'https://github.com/owid/co2-data' })).toHaveAttribute(
      'href',
      'https://github.com/owid/co2-data',
    );
  });
});
