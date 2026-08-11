/**
 * AssistantMark — the two-tone sparkle mark used for Obi's icon throughout the
 * widget (panel header, typing indicator, teaser popup, launcher button).
 *
 * Purely decorative: every place it appears sits beside a visible text label,
 * so it's hidden from assistive tech rather than announced a second time.
 */
export interface AssistantMarkProps {
  size?: number;
  className?: string;
}

export function AssistantMark({ size = 20, className = "" }: AssistantMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
    >
      <path
        d="M11 2C11.9 7.2 13.3 8.6 18.5 9.5C13.3 10.4 11.9 11.8 11 17C10.1 11.8 8.7 10.4 3.5 9.5C8.7 8.6 10.1 7.2 11 2Z"
        fill="currentColor"
        className="text-accent"
      />
      <path
        d="M18.5 13.5C18.9 15.8 19.6 16.5 22 17C19.6 17.5 18.9 18.2 18.5 20.5C18.1 18.2 17.4 17.5 15 17C17.4 16.5 18.1 15.8 18.5 13.5Z"
        fill="currentColor"
        className="text-accent-secondary"
      />
    </svg>
  );
}
