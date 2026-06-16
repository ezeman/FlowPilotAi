import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";

import Card from "../components/Card";
import Spinner from "../components/Spinner";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../services/api";
import { isPlatformOwner, roleLabel } from "../utils/roles";

function formatPlan(account) {
  const subscription = account?.active_subscription;
  const plan = subscription?.plan;
  if (!plan) return "No active plan";
  return `${plan.name} (${subscription?.status || "inactive"})`;
}

export default function UsersPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accounts, setAccounts] = useState([]);
  const [users, setUsers] = useState([]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      try {
        const [accountsData, usersData] = await Promise.all([
          apiRequest("/accounts"),
          apiRequest("/users"),
        ]);
        setAccounts(accountsData || []);
        setUsers(usersData || []);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const groupedAccounts = useMemo(() => {
    const usersByAccount = users.reduce((acc, item) => {
      if (!item.account_id) return acc;
      if (!acc[item.account_id]) acc[item.account_id] = [];
      acc[item.account_id].push(item);
      return acc;
    }, {});

    return accounts.map((account) => ({
      ...account,
      tenantUsers: (usersByAccount[account.id] || []).sort((left, right) => {
        const leftRank = left.role === "subscriber_admin" ? 0 : 1;
        const rightRank = right.role === "subscriber_admin" ? 0 : 1;
        if (leftRank !== rightRank) return leftRank - rightRank;
        return left.full_name.localeCompare(right.full_name);
      }),
    }));
  }, [accounts, users]);

  if (!isPlatformOwner(user)) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="page-stack">
      <section className="hero-banner">
        <div>
          <div className="eyebrow">Platform Users</div>
          <h1>Users by Subscription</h1>
          <p>ดู subscriber admin และ editor ของแต่ละ account พร้อมสถานะ subscription ในหน้าเดียว</p>
        </div>
      </section>

      {error && <div className="inline-error">{error}</div>}

      {loading ? (
        <div className="loading-center">
          <Spinner />
        </div>
      ) : groupedAccounts.length === 0 ? (
        <Card title="Users" subtitle="No subscriber accounts yet." variant="glass">
          <div className="empty-state centered">
            <p>No subscriber accounts yet.</p>
          </div>
        </Card>
      ) : (
        groupedAccounts.map((account) => (
          <Card
            key={account.id}
            title={account.name}
            subtitle={`${formatPlan(account)} · ${account.tenantUsers.length} users`}
            variant="glass"
          >
            <div className="surface-row" style={{ paddingLeft: 0, paddingRight: 0 }}>
              <div>
                <strong>{account.slug}</strong>
                <p className="muted-label">
                  Pages {account.usage?.pages_used ?? 0} · Users {account.usage?.users_used ?? 0}
                </p>
              </div>
              <span className="status-pill">{account.active_subscription?.status || "no subscription"}</span>
            </div>

            {account.tenantUsers.length === 0 ? (
              <div className="empty-state centered" style={{ paddingTop: "1rem" }}>
                <p>No subscriber admin or editor in this account.</p>
              </div>
            ) : (
              <div className="table-shell">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Status</th>
                      <th>Assigned Pages</th>
                    </tr>
                  </thead>
                  <tbody>
                    {account.tenantUsers.map((managedUser) => (
                      <tr key={managedUser.id}>
                        <td>
                          <strong>{managedUser.full_name}</strong>
                        </td>
                        <td>{managedUser.email}</td>
                        <td>{roleLabel(managedUser.role)}</td>
                        <td>
                          <span className="status-pill">
                            {managedUser.is_active ? "active" : "inactive"}
                            {managedUser.is_email_verified ? " · verified" : " · pending"}
                          </span>
                        </td>
                        <td>{managedUser.assigned_page_ids?.length || 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        ))
      )}
    </div>
  );
}