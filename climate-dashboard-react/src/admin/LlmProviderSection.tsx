import { useEffect, useState } from 'react';
import { Button, InlineAlert, SegmentedControl, Spinner } from 'design-system';
import { adminApi } from './adminClient';
import type { LlmChoice } from './types';
import { useAsync } from '../hooks/useAsync';

// Mirrors services/agent/src/agent/settings.py's ALLOWED_CHOICES -- SPEC.md §14.2. Kept as a
// small hand-synced copy rather than a shared import, matching this repo's established
// "small per-sub-project copies over a shared import" convention (services/agent/SPEC.md
// "Corrections applied" #15). Only two entries today; a third would be worth revisiting for a
// Select dropdown instead of a SegmentedControl.
const OPTIONS = [
  { id: 'anthropic-sonnet', provider: 'anthropic', model: 'claude-sonnet-5', label: 'Claude Sonnet 5 (Anthropic)' },
  { id: 'ollama-qwen14b-ctx8k', provider: 'ollama', model: 'qwen2.5:14b-ctx8k', label: 'Qwen 2.5 14B (local, 8k ctx)' },
];

function idForChoice(choice: LlmChoice): string | undefined {
  return OPTIONS.find((o) => o.provider === choice.provider && o.model === choice.model)?.id;
}

export function LlmProviderSection() {
  const current = useAsync(() => adminApi.getLlmChoice(), []);
  // The choice this section actually treats as "currently applied" -- seeded from the initial
  // GET, then updated directly from a successful POST's own response. Deliberately NOT derived
  // from `current.data` on every render: that value is frozen at whatever the one-time GET
  // returned, so after a successful switch the Apply button would stay enabled against a
  // choice that's no longer live, letting the admin repeatedly re-POST the same switch.
  const [appliedChoice, setAppliedChoice] = useState<LlmChoice | null>(null);
  // undefined until the admin actually picks something in this session -- until then the
  // SegmentedControl just reflects `appliedChoice`.
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const [applying, setApplying] = useState(false);
  const [status, setStatus] = useState<{ variant: 'success' | 'error'; message: string } | null>(null);

  useEffect(() => {
    if (current.data) setAppliedChoice(current.data);
  }, [current.data]);

  if (current.loading) {
    return <Spinner label="Loading current model…" />;
  }

  if (current.error || !appliedChoice) {
    return (
      <InlineAlert variant="error">
        Could not load the current model — reload the page to try again. If this keeps
        happening, your admin session may have expired.
      </InlineAlert>
    );
  }

  const appliedId = idForChoice(appliedChoice);
  // "" (not undefined) when appliedId is unrecognized -- SegmentedControl falls back to its
  // own internal state (defaulting to the first item) whenever `value` is undefined, which
  // would silently show Sonnet as selected even though the live choice is something else
  // entirely. An explicit "" matches no real item, so nothing renders as selected instead.
  const activeId = selectedId ?? appliedId ?? '';

  const handleApply = async () => {
    if (!selectedId || applying) return;
    setApplying(true);
    setStatus(null);
    try {
      const updated = await adminApi.setLlmChoice(selectedId);
      setAppliedChoice(updated);
      setSelectedId(undefined); // falls back to the freshly-applied choice, Apply goes disabled again
      const label = OPTIONS.find((o) => o.id === selectedId)?.label ?? selectedId;
      setStatus({ variant: 'success', message: `Switched to ${label}.` });
    } catch (err) {
      setStatus({
        variant: 'error',
        message: err instanceof Error ? err.message : 'Could not switch models.',
      });
    } finally {
      setApplying(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {appliedId === undefined && (
        <InlineAlert variant="warning">
          The live model ({appliedChoice.provider}/{appliedChoice.model}) isn't one of the known
          options below -- pick one to switch to a recognized state.
        </InlineAlert>
      )}
      <SegmentedControl
        items={OPTIONS.map((o) => ({ value: o.id, label: o.label }))}
        value={activeId}
        onChange={setSelectedId}
      />
      <div>
        <Button
          onClick={handleApply}
          disabled={!selectedId || selectedId === appliedId || applying}
          isLoading={applying}
        >
          Apply
        </Button>
      </div>
      {status && <InlineAlert variant={status.variant}>{status.message}</InlineAlert>}
    </div>
  );
}
