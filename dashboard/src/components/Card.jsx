export default function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
  variant = "default"
}) {
  const classes = ["card", variant === "glass" ? "glass-card" : "", className].filter(Boolean).join(" ");

  return (
    <section className={classes}>
      {(title || subtitle || actions) && (
        <div className="card-header">
          <div>
            {title ? <h2 className="card-title">{title}</h2> : null}
            {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
