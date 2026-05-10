interface TagChipProps {
  label: string;
  active?: boolean;
  onClick?: () => void;
  small?: boolean;
}

export function TagChip({ label, active = false, onClick, small = false }: TagChipProps) {
  return (
    <button
      className={["chip", active ? "chip-active" : "chip-outline", small ? "chip-small" : ""]
        .filter(Boolean)
        .join(" ")}
      onClick={onClick}
      type="button"
    >
      {label}
    </button>
  );
}
