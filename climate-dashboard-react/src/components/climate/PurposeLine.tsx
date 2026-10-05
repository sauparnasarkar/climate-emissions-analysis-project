import type { ReactNode } from 'react';

/** Every new Area 2 chart states what question it answers (requirements §2.3). */
export function PurposeLine({ children }: { children: ReactNode }) {
  return (
    <p className="__s9cmpx-body4" style={{ margin: '0 0 8px', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
      <strong>Purpose:</strong> {children}
    </p>
  );
}
