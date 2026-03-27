const STATUS_LABELS = {
  offline: "Offline",
  starting: "Starting",
  online_managed: "Online (Managed)",
  online_external: "Online (External)",
  stopping: "Stopping",
  error: "Error"
};

function ServiceCard({ service, busyAction, onAction }) {
  const isExternal = service?.status === "online_external" && !service?.managed;
  const disableStopRestart = isExternal || busyAction;
  const disableStart = busyAction || service?.status === "online_managed";

  return (
    <section className="service-card">
      <header>
        <h3>{service?.name === "metaclaw" ? "MetaClaw" : "PicoClaw"}</h3>
        <span className={`status-badge ${service?.status || "offline"}`}>
          {STATUS_LABELS[service?.status] || "Unknown"}
        </span>
      </header>
      <ul className="meta-list">
        <li>
          <strong>Port:</strong> {service?.port ?? "-"}
        </li>
        <li>
          <strong>Mode:</strong> {service?.managed ? "Managed" : "External/None"}
        </li>
        <li>
          <strong>Probe:</strong> {service?.last_probe || "-"}
        </li>
        <li>
          <strong>PID:</strong> {service?.pid || "-"}
        </li>
      </ul>
      {service?.last_error ? <p className="error-text">{service.last_error}</p> : null}
      {isExternal ? (
        <p className="hint-text">External process detected: stop/restart disabled by policy.</p>
      ) : null}
      <div className="actions">
        <button disabled={disableStart} onClick={() => onAction(service.name, "start")}>
          Start
        </button>
        <button disabled={disableStopRestart} onClick={() => onAction(service.name, "stop")}>
          Stop
        </button>
        <button disabled={disableStopRestart} onClick={() => onAction(service.name, "restart")}>
          Restart
        </button>
      </div>
    </section>
  );
}

export default ServiceCard;

