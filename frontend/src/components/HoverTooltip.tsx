import { useRef, useState, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  content: ReactNode;
  disabled?: boolean;
}

/** Wraps a value so hovering it shows its source/citation immediately -
 * a quicker verification path than click-select-then-look-at-side-panel. */
export default function HoverTooltip({ children, content, disabled }: Props) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const ref = useRef<HTMLSpanElement>(null);

  const POPUP_W = 340;
  const POPUP_MAX_H = 220;

  function show() {
    if (disabled) return;
    const rect = ref.current?.getBoundingClientRect();
    if (rect) {
      // Flip above / clamp horizontally so the popup can't render off-screen
      // for rows near the bottom or right edge of the viewport.
      const spaceBelow = window.innerHeight - rect.bottom;
      const top =
        spaceBelow < POPUP_MAX_H && rect.top > spaceBelow
          ? Math.max(8, rect.top - POPUP_MAX_H - 6)
          : rect.bottom + 6;
      const left = Math.min(rect.left, Math.max(8, window.innerWidth - POPUP_W - 8));
      setPos({ top, left });
    }
    setVisible(true);
  }

  return (
    <span
      ref={ref}
      className="hover-tooltip-trigger"
      onMouseEnter={show}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && !disabled && (
        <div className="hover-tooltip-popup" style={{ top: pos.top, left: pos.left }}>
          {content}
        </div>
      )}
    </span>
  );
}
