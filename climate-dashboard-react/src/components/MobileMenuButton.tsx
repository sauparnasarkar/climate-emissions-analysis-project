import { Icon } from 'design-system';

/** The bordered "Menu" button both headers show on a phone (landing: opens its dropdown; dashboard: opens the
 * sidebar drawer). Colour comes from its surroundings, so the theme's header rules keep it legible on the dark
 * dashboard bar and it reads as plain text on the light landing bar. */
export function MobileMenuButton({ open, onClick, controls }: { open: boolean; onClick: () => void; controls?: string }) {
  return (
    <button
      type="button"
      aria-expanded={open}
      aria-controls={controls}
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 8,
        minHeight: 44,
        padding: '0 12px',
        background: 'transparent',
        color: 'inherit',
        border: '1px solid color-mix(in srgb, currentColor 35%, transparent)',
        borderRadius: 8,
        cursor: 'pointer',
        font: 'inherit',
        whiteSpace: 'nowrap',
      }}
    >
      <Icon name={open ? 'close' : 'menu'} size={18} />
      Menu
    </button>
  );
}
