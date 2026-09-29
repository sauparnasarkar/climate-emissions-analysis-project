import { SegmentedControl } from 'design-system';
import type { AppTheme } from '../lib/theme';

/** Light/Dark switch shared by the dashboard shell's header/mobile drawer and the landing layout. */
export function ThemeToggle({ theme, setTheme }: { theme: AppTheme; setTheme: (t: AppTheme) => void }) {
  return (
    <SegmentedControl
      name="theme"
      size="small"
      value={theme}
      onChange={(v) => setTheme(v as AppTheme)}
      items={[
        { value: 'analytics-bright-tidewater', label: 'Light' },
        { value: 'analytics', label: 'Dark' },
      ]}
    />
  );
}
