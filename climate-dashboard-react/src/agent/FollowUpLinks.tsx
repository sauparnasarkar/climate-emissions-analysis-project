import { Link } from 'react-router-dom';
import type { FollowUpLink } from './types';

/** An answer's deep links into the dashboard ("Open in Historical Trends →"): real in-app navigation, so the router's base path applies. Each route
 * carries its own query and anchor (services/agent SPEC §15.5, §15.13), so the page opens on the view the answer showed. Absent when there are none. */
export function FollowUpLinks({ links }: { links: FollowUpLink[] }) {
  if (links.length === 0) return null;
  return (
    <nav aria-label="Open in the dashboard">
      <ul style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 20px', margin: 0, padding: 0, listStyle: 'none' }}>
        {links.map((link) => (
          <li key={link.route}>
            <Link to={link.route} className="area2-link __s9cmpx-body3">
              {link.label} <span aria-hidden="true">→</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
