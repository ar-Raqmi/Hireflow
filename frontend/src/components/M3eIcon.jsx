import { M3eIcon as WebIcon } from '@m3e/react/icon';

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
