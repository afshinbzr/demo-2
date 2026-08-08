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

  function show() {
    if (disabled) return;
    const rect = ref.current?.getBoundingClientRect();
    if (rect) {
      setPos({ top: rect.bottom + 6, left: rect.left });
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
