const STATUS_LABELS = {
  offline: "Offline",
  starting: "Starting",
  online_managed: "Online (Managed)",
  online_external: "Online (External)",
  stopping: "Stopping",
  error: "Error",
};

const SERVICE_ICONS = {
  metaclaw: "\ud83e\uddc0",
  picoclaw: "\ud83e\udd80",
};

function ServiceCard({ service, busyAction, onAction }) {
  const isExternal = service?.status === "online_external" && !service?.managed;
  const disableStopRestart = isExternal || busyAction;
  const disableStart = busyAction || service?.status === "online_managed";
  const isOnline =
    service?.status === "online_managed" || service?.status === "online_external";

  return (
    <section className="service-card">
      <header>
        <h3>
          <span>{SERVICE_ICONS[service?.name] || "\u2699\ufe0f"}</span>
          {service?.name === "metaclaw" ? "MetaClaw" : "PicoClaw"}
        </h3>
        <span className={`status-badge ${service?.status || "offline"}`}>
          {STATUS_LABELS[service?.status] || "Unknown"}
        </span>
      </header>

      <ul className="meta-list">
        <li>
          <strong>Port</strong> {service?.port ?? "\u2014"}
        </li>
        <li>
          <strong>Mode</strong> {service?.managed ? "Managed" : "External"}
        </li>
        <li>
          <strong>Probe</strong> {service?.last_probe || "\u2014"}
        </li>
        <li>
          <strong>PID</strong> {service?.pid || "\u2014"}
        </li>
      </ul>

      {service?.last_error ? (
        <p className="error-text">{service.last_error}</p>
      ) : null}

      {isExternal ? (
        <p className="hint-text">
          External process detected \u2014 stop/restart disabled by policy.
        </p>
      ) : null}

      <div className="actions">
        <button disabled={disableStart} onClick={() => onAction(service.name, "start")}>
          \u25b6 Start
        </button>
        <button disabled={disableStopRestart} onClick={() => onAction(service.name, "stop")}>
          \u25a0 Stop
        </button>
        <button
          disabled={disableStopRestart}
          onClick={() => onAction(service.name, "restart")}
        >
          \u21bb Restart
        </button>
      </div>
    </section>
  );
}

export default ServiceCard;
