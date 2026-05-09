// =============================================================================
// PH Agent Hub — Logo component
// =============================================================================
// Renders the SVG logo inline. Use `size` to control the square dimension.
// Use `showText` to optionally display "PH Agent" next to the icon.
// =============================================================================

interface LogoProps {
  size?: number;
  showText?: boolean;
  textColor?: string;
}

export function Logo({ size = 32, showText = false, textColor = "inherit" }: LogoProps) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, lineHeight: 1 }}>
      <img
        src="/logo.svg"
        alt="PH Agent Hub"
        width={size}
        height={size}
        style={{ display: "block", flexShrink: 0 }}
      />
      {showText && (
        <span
          style={{
            fontSize: size * 0.5,
            fontWeight: 700,
            color: textColor,
            whiteSpace: "nowrap",
          }}
        >
          PH Agent
        </span>
      )}
    </span>
  );
}
