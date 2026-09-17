export function GsbLogo({
  height = 40,
  className = "",
}: {
  height?: number;
  className?: string;
}) {
  return (
    <img
      className={`gsb-logo ${className}`.trim()}
      src="/brand/gsb-logo.png?v=2"
      alt="GSB Infrastructure"
      height={height}
      style={{ height, width: "auto" }}
    />
  );
}
