import { useState } from 'react';
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
  // undefined until the admin actually picks something in this session -- until then the
  // SegmentedControl just reflects whatever's live, from `current.data`.
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const [applying, setApplying] = useState(false);
  const [status, setStatus] = useState<{ variant: 'success' | 'error'; message: string } | null>(null);

  if (current.loading) {
    return <Spinner label="Loading current model…" />;
  }

  if (current.error || !current.data) {
    return (
      <InlineAlert variant="error">
        Could not load the current model — reload the page to try again. If this keeps
        happening, your admin session may have expired.
      </InlineAlert>
    );
  }

  const activeId = selectedId ?? idForChoice(current.data);
  const appliedId = idForChoice(current.data);

  const handleApply = async () => {
    if (!selectedId || applying) return;
    setApplying(true);
    setStatus(null);
    try {
      await adminApi.setLlmChoice(selectedId);
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
