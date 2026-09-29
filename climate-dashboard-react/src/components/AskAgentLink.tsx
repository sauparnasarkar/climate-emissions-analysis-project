import { Link, useLocation } from 'react-router-dom';
import { Icon } from 'design-system';

/** The "Ask the Agent" entry point, shared by the landing header and the dashboard header so it
 * looks and sits the same on every page. A real link (it navigates); colour comes from its
 * surroundings, so the theme's header rules keep it legible on the dark bar. */
export function AskAgentLink() {
  const { pathname } = useLocation();
  const active = pathname === '/ask';
  return (
    <Link
      to="/ask"
      aria-current={active ? 'page' : undefined}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 16px',
        whiteSpace: 'nowrap',
        fontSize: 14,
        color: 'inherit',
        textDecoration: 'none',
        border: '1px solid color-mix(in srgb, currentColor 35%, transparent)',
        borderRadius: 8,
        background: active ? 'color-mix(in srgb, currentColor 12%, transparent)' : 'transparent',
      }}
    >
      <Icon name="sparkle" size={16} />
      Ask the Agent
    </Link>
  );
}
