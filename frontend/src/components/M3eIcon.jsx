import { M3eIcon as WebIcon } from '@m3e/react/icon';

// M3eIcon — M3E Material Symbols icon. Replaces the hand-rolled Icon.jsx.
// Sets the icon size via the M3E `--m3e-icon-size` CSS var (the host's font
// size) so every existing `size` call site behaves identically.
export default function M3eIcon({ name, size = 18, className = '', weight = 500, ...rest }) {
  return (
    <WebIcon
      name={name}
      variant="rounded"
      weight={weight}
      className={className}
      style={{ '--m3e-icon-size': `${size}px` }}
      {...rest}
    />
  );
}