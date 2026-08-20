import { Card, CardHeader } from 'design-system';
import { LlmProviderSection } from '../admin/LlmProviderSection';

// Unlisted -- registered only as a <Route> in App.tsx, absent from NAV_ITEMS and
// SidebarNav.persistentAction, reachable by URL only. Same precedent /ask already sets
// (root ARCHITECTURE.md §8). Gated at the edge by a Cloudflare Access login policy, not any
// app-level check here -- see services/agent/SPEC.md §14.1.
export default function AdminPage() {
  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 16px' }}>Admin</h1>
      <Card withBorder padding="large">
        <CardHeader title="LLM Model" supportText="Which model services/agent uses for every conversational query." />
        <div style={{ marginTop: 16 }}>
          <LlmProviderSection />
        </div>
      </Card>
    </div>
  );
}
