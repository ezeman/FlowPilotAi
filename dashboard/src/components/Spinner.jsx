export default function Spinner({ size = "md", label = "กำลังโหลด..." }) {
  return (
    <span className="spinner-wrap" aria-label={label} role="status">
      <span className={`spinner${size === "sm" ? " spinner-sm" : ""}`} />
    </span>
  );
}
