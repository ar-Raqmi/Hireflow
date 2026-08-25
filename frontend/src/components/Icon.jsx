// Icon — thin wrapper over Material Symbols Rounded, used app-wide.
export default function Icon({ name, size = 18, className = '' }) {
  return (
    <span
      className={`mi ${className}`}
      style={{ fontSize: size, fontVariationSettings: "'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 24" }}
      aria-hidden="true"
    >
      {name}
    </span>
  );
}