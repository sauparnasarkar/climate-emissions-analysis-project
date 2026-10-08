const CSS = `
.ask-skel { display: flex; flex-direction: column; gap: 12px; }
.ask-skel__bar { border-radius: 6px; background: var(--__s9cmpx-static-divider-weak); }
@media (prefers-reduced-motion: no-preference) {
  .ask-skel__bar { animation: ask-skel-pulse 1.4s ease-in-out infinite; }
  @keyframes ask-skel-pulse { 0%, 100% { opacity: .55; } 50% { opacity: 1; } }
}
`;

/** Placeholder while an answer is on its way (design handoff: the question heading is shown at once, then a skeleton for the lead and the chart).
 * The shimmer is a CSS animation only where the user has not asked for reduced motion. */
export function AnswerSkeleton() {
  return (
    <div className="ask-skel" role="status" aria-label="Loading the answer">
      <style>{CSS}</style>
      <div className="ask-skel__bar" style={{ height: 16, width: '92%' }} />
      <div className="ask-skel__bar" style={{ height: 16, width: '78%' }} />
      <div className="ask-skel__bar" style={{ height: 220, width: '100%', marginTop: 4 }} />
    </div>
  );
}
