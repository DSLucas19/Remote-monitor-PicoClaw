import { useEffect, useMemo, useRef, useState } from "react";
import ServiceCard from "./components/ServiceCard";

const rawApiBase = (import.meta.env.VITE_API_BASE_URL || "").trim();
const API_BASE = rawApiBase ? rawApiBase.replace(/\/$/, "") : "";
const WS_BASE = rawApiBase
  ? rawApiBase.replace(/^http/i, "ws").replace(/\/$/, "")
  : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;

function App() {
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [token, setToken] = useState(() => localStorage.getItem("rm_session_token") || "");
  const [sessionInfo, setSessionInfo] = useState(() => {
    const raw = localStorage.getItem("rm_session_info");
    return raw ? JSON.parse(raw) : null;
  });
  const [services, setServices] = useState({});
  const [logs, setLogs] = useState([]);
  const [logFilter, setLogFilter] = useState("all");
  const [wsState, setWsState] = useState("disconnected");
  const [notice, setNotice] = useState("");
  const [actionBusy, setActionBusy] = useState("");
  const [keys, setKeys] = useState([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState("");
  const logBottomRef = useRef(null);

  const filteredLogs = useMemo(() => {
    if (logFilter === "all") {
      return logs;
    }
    return logs.filter((entry) => entry.service === logFilter);
  }, [logs, logFilter]);

  const setSession = (nextToken, nextInfo) => {
    setToken(nextToken);
    setSessionInfo(nextInfo);
    if (nextToken) {
      localStorage.setItem("rm_session_token", nextToken);
      localStorage.setItem("rm_session_info", JSON.stringify(nextInfo || {}));
    } else {
      localStorage.removeItem("rm_session_token");
      localStorage.removeItem("rm_session_info");
    }
  };

  const authedFetch = async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(options.headers || {})
      }
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || `Request failed (${response.status})`);
    }
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      return response.json();
    }
    return null;
  };

  const refreshStatus = async () => {
    if (!token) return;
    try {
      const data = await authedFetch("/api/status");
      const next = {};
      data.services.forEach((item) => {
        next[item.name] = item;
      });
      setServices(next);
    } catch (error) {
      setNotice(error.message);
    }
  };

  const refreshKeys = async () => {
    if (!token) return;
    try {
      const data = await authedFetch("/api/keys");
      setKeys(data);
    } catch (error) {
      setNotice(error.message);
    }
  };

  const refreshLogs = async () => {
    if (!token) return;
    try {
      const data = await authedFetch("/api/logs?limit=200");
      setLogs(data);
    } catch (error) {
      setNotice(error.message);
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/auth/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKeyInput.trim() })
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Invalid key");
      }
      const payload = await response.json();
      setSession(payload.access_token, {
        key_id: payload.key_id,
        key_name: payload.key_name,
        expires_in: payload.expires_in
      });
      setApiKeyInput("");
      setNotice("Login success.");
    } catch (error) {
      setNotice(error.message);
    }
  };

  const handleLogout = async () => {
    try {
      if (token) {
        await authedFetch("/api/auth/session", { method: "DELETE" });
      }
    } catch {
      // Ignore logout API errors.
    } finally {
      setSession("", null);
      setServices({});
      setKeys([]);
      setLogs([]);
      setCreatedKey("");
      setNotice("Logged out.");
    }
  };

  const handleServiceAction = async (service, action) => {
    setActionBusy(`${service}:${action}`);
    setNotice("");
    try {
      const payload = await authedFetch(`/api/services/${service}/${action}`, { method: "POST" });
      setNotice(payload.message || `${service} ${action} done`);
      await refreshStatus();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setActionBusy("");
    }
  };

  const handleGatewayConnect = async () => {
    setActionBusy("picoclaw:gateway");
    try {
      const payload = await authedFetch("/api/services/picoclaw/gateway/connect", { method: "POST" });
      setNotice(payload.message);
    } catch (error) {
      setNotice(error.message);
    } finally {
      setActionBusy("");
    }
  };

  const handleCreateKey = async (event) => {
    event.preventDefault();
    setNotice("");
    setCreatedKey("");
    try {
      const payload = await authedFetch("/api/keys", {
        method: "POST",
        body: JSON.stringify({ name: newKeyName.trim() })
      });
      setNewKeyName("");
      setCreatedKey(payload.api_key);
      await refreshKeys();
      setNotice("New key created. Save it now.");
    } catch (error) {
      setNotice(error.message);
    }
  };

  const handleRevoke = async (id) => {
    try {
      await authedFetch(`/api/keys/${id}/revoke`, { method: "POST" });
      await refreshKeys();
      setNotice(`Key #${id} revoked.`);
    } catch (error) {
      setNotice(error.message);
    }
  };

  useEffect(() => {
    if (!token) return;
    refreshStatus();
    refreshLogs();
    refreshKeys();
    const timer = setInterval(refreshStatus, 3000);
    return () => clearInterval(timer);
  }, [token]);

  useEffect(() => {
    if (!token) {
      setWsState("disconnected");
      return;
    }

    let socket;
    let reconnectTimer;
    let pingTimer;
    let disposed = false;

    const connect = () => {
      socket = new WebSocket(`${WS_BASE}/ws/logs?token=${encodeURIComponent(token)}&limit=100`);
      setWsState("connecting");

      socket.onopen = () => {
        setWsState("connected");
        pingTimer = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send("ping");
          }
        }, 15000);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          setLogs((prev) => {
            const next = [...prev, payload];
            if (next.length > 2000) {
              return next.slice(next.length - 2000);
            }
            return next;
          });
        } catch {
          // Ignore malformed log messages.
        }
      };

      socket.onclose = () => {
        setWsState("disconnected");
        if (pingTimer) clearInterval(pingTimer);
        if (!disposed) {
          reconnectTimer = window.setTimeout(connect, 2500);
        }
      };

      socket.onerror = () => {
        setWsState("error");
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      if (socket && socket.readyState <= 1) {
        socket.close();
      }
    };
  }, [token]);

  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [filteredLogs]);

  if (!token) {
    return (
      <main className="layout login-layout">
        <section className="panel login-panel">
          <h1>Remote Monitor Dashboard</h1>
          <p>Enter your API key to create a session.</p>
          <form onSubmit={handleLogin}>
            <input
              type="password"
              value={apiKeyInput}
              onChange={(event) => setApiKeyInput(event.target.value)}
              placeholder="rmk_..."
              required
            />
            <button type="submit">Sign In</button>
          </form>
          {notice ? <p className="notice">{notice}</p> : null}
        </section>
      </main>
    );
  }

  return (
    <main className="layout dashboard-layout">
      <header className="topbar panel">
        <div>
          <h1>Remote Monitor Dashboard</h1>
          <p>
            Session key: <strong>{sessionInfo?.key_name || "Unknown"}</strong> | WS:{" "}
            <span className={`ws-${wsState}`}>{wsState}</span>
          </p>
        </div>
        <div className="top-actions">
          <button onClick={refreshStatus}>Refresh</button>
          <button onClick={handleGatewayConnect} disabled={actionBusy === "picoclaw:gateway"}>
            Connect Gateway
          </button>
          <button className="danger" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      {notice ? <p className="notice">{notice}</p> : null}

      <section className="services-grid">
        <ServiceCard
          service={services.metaclaw}
          busyAction={actionBusy.startsWith("metaclaw")}
          onAction={handleServiceAction}
        />
        <ServiceCard
          service={services.picoclaw}
          busyAction={actionBusy.startsWith("picoclaw")}
          onAction={handleServiceAction}
        />
      </section>

      <section className="panel keys-panel">
        <h2>API Keys</h2>
        <form onSubmit={handleCreateKey} className="key-form">
          <input
            value={newKeyName}
            onChange={(event) => setNewKeyName(event.target.value)}
            placeholder="Key name (ex: Laptop B)"
            required
          />
          <button type="submit">Create Key</button>
        </form>
        {createdKey ? (
          <p className="created-key">
            New key (show once): <code>{createdKey}</code>
          </p>
        ) : null}
        <div className="key-list">
          {keys.map((item) => (
            <div key={item.id} className={`key-item ${item.active ? "" : "revoked"}`}>
              <span>
                #{item.id} {item.name} ({item.prefix}...)
              </span>
              <span>{item.active ? "ACTIVE" : "REVOKED"}</span>
              {item.active ? (
                <button
                  onClick={() => handleRevoke(item.id)}
                  disabled={sessionInfo?.key_id === item.id}
                  className="danger"
                >
                  Revoke
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="panel logs-panel">
        <div className="logs-header">
          <h2>Live Console</h2>
          <select value={logFilter} onChange={(event) => setLogFilter(event.target.value)}>
            <option value="all">All services</option>
            <option value="metaclaw">MetaClaw</option>
            <option value="picoclaw">PicoClaw</option>
          </select>
        </div>
        <div className="logs-box">
          {filteredLogs.map((entry, index) => (
            <pre key={`${entry.timestamp}-${index}`}>
              [{new Date(entry.timestamp).toLocaleTimeString()}] [{entry.service}] [{entry.stream}] {entry.message}
            </pre>
          ))}
          <span ref={logBottomRef} />
        </div>
      </section>
    </main>
  );
}

export default App;
