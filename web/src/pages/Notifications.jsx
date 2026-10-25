import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { formatDateTime, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import { Badge, Card, EmptyState, ErrorBanner, PageHeader, Spinner } from "../components/ui";

export default function Notifications() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const notifications = useAsync(
    () => api("/notifications", { query: { limit: 50, unreadOnly: unreadOnly || undefined } }),
    [unreadOnly]
  );
  const [busy, setBusy] = useState(false);

  async function markAll() {
    setBusy(true);
    try {
      await api("/notifications/read-all", { method: "PATCH" });
      notifications.reload();
    } finally {
      setBusy(false);
    }
  }

  async function markOne(id) {
    try {
      await api(`/notifications/${id}/read`, { method: "PATCH" });
      notifications.reload();
    } catch {
      // Ignore; the list still shows the item.
    }
  }

  const items = notifications.data?.items || [];
  const unread = items.filter((item) => !item.read).length;

  return (
    <div>
      <PageHeader title="Notifications" subtitle={`${unread} unread in this view`}>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-slate-300 text-brand-600"
            checked={unreadOnly}
            onChange={(event) => setUnreadOnly(event.target.checked)}
          />
          Unread only
        </label>
        <button type="button" className="btn-secondary" onClick={markAll} disabled={busy || unread === 0}>
          <Icon name="check" className="h-4 w-4" />
          Mark all read
        </button>
      </PageHeader>

      <ErrorBanner error={notifications.error} onRetry={() => notifications.reload()} />

      <Card>
        {notifications.loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="You are all caught up" body="Drive, deadline, application and feedback updates appear here." />
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((item) => (
              <div key={item.id} className={`flex gap-3 px-5 py-4 ${item.read ? "" : "bg-brand-50/40"}`}>
                <span className={`mt-0.5 rounded-full p-2 ${item.read ? "bg-slate-100 text-slate-400" : "bg-brand-100 text-brand-700"}`}>
                  <Icon name="bell" className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                    <Badge tone={item.read ? "slate" : "brand"}>{titleCase(item.type)}</Badge>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-600">{item.body}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-slate-400">
                    <span>{formatDateTime(item.createdAt)}</span>
                    {item.link ? (
                      <Link
                        to={item.link}
                        className="font-semibold text-brand-700 hover:underline"
                        onClick={() => !item.read && markOne(item.id)}
                      >
                        Open
                      </Link>
                    ) : null}
                    {!item.read ? (
                      <button type="button" className="font-semibold text-brand-700 hover:underline" onClick={() => markOne(item.id)}>
                        Mark read
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
