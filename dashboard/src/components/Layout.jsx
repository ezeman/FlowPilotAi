import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { useLang } from "../context/LangContext";
import { apiRequest } from "../services/api";
import LanguageSwitcher from "./LanguageSwitcher";

function IconDashboard() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M3 3h6v6H3V3zm8 0h6v9h-6V3zM3 11h6v6H3v-6zm8 3h6v3h-6v-3z" />
    </svg>
  );
}

function IconStudio() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M10 2l2.1 4.5L17 7l-3.5 3.4.8 4.9-4.3-2.5-4.3 2.5.8-4.9L3 7l4.9-.5L10 2z" />
    </svg>
  );
}

function IconCalendar() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M6 2h2v2h4V2h2v2h2a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2h2V2zm10 6H4v8h12V8z" />
    </svg>
  );
}

function IconPosts() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M4 4h12v2H4V4zm0 5h12v2H4V9zm0 5h8v2H4v-2z" />
    </svg>
  );
}

function IconLogs() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M10 2a8 8 0 108 8 8 8 0 00-8-8zm1 4H9v5l4 2 .9-1.8-2.9-1.4V6z" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M11.3 2l.5 2a6.7 6.7 0 011.5.9l2-.7 1.4 2.4-1.6 1.3c.1.5.1 1 .1 1.5s0 1-.1 1.5l1.6 1.3-1.4 2.4-2-.7c-.5.4-1 .7-1.5.9l-.5 2H8.7l-.5-2a6.7 6.7 0 01-1.5-.9l-2 .7-1.4-2.4L4.9 12a7 7 0 010-3L3.3 7.7l1.4-2.4 2 .7c.5-.4 1-.7 1.5-.9l.5-2h2.6zM10 7.1A2.9 2.9 0 1010 13a2.9 2.9 0 000-5.8z" />
    </svg>
  );
}

function IconBilling() {
  return (
    <svg className="nav-icon" viewBox="0 0 20 20" fill="currentColor">
      <path d="M2 4a2 2 0 012-2h12a2 2 0 012 2v2H2V4zm0 4h16v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8zm3 3a1 1 0 000 2h2a1 1 0 000-2H5z" />
    </svg>
  );
}

function getInitials(name) {
  if (!name) return "AI";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export default function Layout({ children }) {
  const { user, activeAccountId, switchAccount, logout } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);

  const baseNavigation = [
    { to: "/", label: t("nav.dashboard"), icon: <IconDashboard />, end: true },
    { to: "/studio", label: t("nav.studio"), icon: <IconStudio /> },
    { to: "/calendar", label: t("nav.calendar"), icon: <IconCalendar /> },
    { to: "/posts", label: t("nav.posts"), icon: <IconPosts /> },
    { to: "/publish-logs", label: t("nav.logs"), icon: <IconLogs /> },
    { to: "/settings", label: t("nav.settings"), icon: <IconSettings /> },
  ];

  const navigation = user?.role === "subscriber_admin"
    ? [...baseNavigation.slice(0, -1), { to: "/billing", label: t("nav.billing"), icon: <IconBilling /> }, baseNavigation[baseNavigation.length - 1]]
    : baseNavigation;

  useEffect(() => {
    if (user?.role !== "platform_admin") return;
    apiRequest("/accounts")
      .then((data) => setAccounts(data))
      .catch(() => setAccounts([]));
  }, [user?.role, activeAccountId]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">FlowPilot AI</div>
          <p className="brand-subtitle">{t("layout.brandSubtitle")}</p>
        </div>

        <nav className="sidebar-nav">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          {user?.role === "platform_admin" && accounts.length > 0 && (
            <label className="stack-form" style={{ gap: "0.35rem" }}>
              <span style={{ color: "var(--sidebar-muted)", fontSize: "0.76rem", fontWeight: 700 }}>{t("layout.activeAccount")}</span>
              <select value={activeAccountId || ""} onChange={(event) => switchAccount(event.target.value)}>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    {account.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <LanguageSwitcher />
          <button
            type="button"
            className="user-summary"
            onClick={() => navigate("/profile")}
            style={{ background: "none", border: "none", cursor: "pointer", width: "100%", textAlign: "left", padding: 0 }}
          >
            <div className="user-avatar">{getInitials(user?.full_name)}</div>
            <div>
              <strong>{user?.full_name || t("layout.defaultOperator")}</strong>
              <p>{user?.account?.name || t("layout.platform")} · {user?.role || "editor"}</p>
            </div>
          </button>
          <button className="secondary-button" type="button" onClick={logout}>
            {t("layout.logout")}
          </button>
        </div>
      </aside>

      <main className="content-area">{children}</main>
    </div>
  );
}
