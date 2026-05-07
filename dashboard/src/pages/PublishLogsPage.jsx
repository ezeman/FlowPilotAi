import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import StatusPill from "../components/StatusPill";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";

function formatDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("th-TH", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export default function PublishLogsPage() {
  const { t } = useLang();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/publish-logs")
      .then(setLogs)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">{t("publishLogs.eyebrow")}</div>
          <h1>{t("publishLogs.title")}</h1>
          <p>{t("publishLogs.subtitle")}</p>
        </div>
        <div className="hero-actions">
          <Link className="secondary-button" to="/studio">
            {t("publishLogs.openPublisher")}
          </Link>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}

      <Card title={t("publishLogs.publishHistory")} subtitle={t("publishLogs.publishHistorySubtitle")} variant="glass">
        {loading ? (
          <div className="loading-center">
            <Spinner />
          </div>
        ) : logs.length === 0 ? (
          <div className="empty-state centered">
            <p>{t("publishLogs.noLogs")}</p>
          </div>
        ) : (
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <th>{t("publishLogs.tablePost")}</th>
                  <th>{t("publishLogs.tableStatus")}</th>
                  <th>{t("publishLogs.tableFbId")}</th>
                  <th>{t("publishLogs.tableTime")}</th>
                  <th>{t("publishLogs.tableResponseError")}</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>
                      <Link to={`/posts/${log.post_id}/edit`} style={{ color: "var(--primary)", fontWeight: 700 }}>
                        #{log.post_id}
                      </Link>
                    </td>
                    <td>
                      <StatusPill status={log.status} />
                    </td>
                    <td>{log.fb_post_id || "-"}</td>
                    <td>{formatDate(log.created_at)}</td>
                    <td style={{ color: log.error_message ? "var(--danger)" : "var(--text-muted)", maxWidth: "360px" }}>
                      {log.error_message || (log.response_payload ? JSON.stringify(log.response_payload).slice(0, 180) : "-")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
