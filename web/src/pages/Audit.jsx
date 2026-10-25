import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDateTime, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Badge, Card, CardHeader, EmptyState, ErrorBanner, PageHeader, Spinner } from "../components/ui";

const ENTITIES = ["", "student", "batch", "college", "session", "attendance", "assessment", "application", "drive", "feedback", "user"];

export default function Audit() {
  const { isAdmin } = useAuth();
  const [entity, setEntity] = useState("");
  const logs = useAsync(
    () => (isAdmin ? api("/audit-logs", { query: { limit: 100, entity: entity || undefined } }) : Promise.resolve(null)),
    [entity, isAdmin]
  );

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="Audit log is admin-only" />
        <p className="p-5 text-sm text-slate-500">
          Super admins and college admins can review mutation history.
        </p>
      </Card>
    );
  }

  const items = logs.data?.items || [];

  return (
    <div>
      <PageHeader title="Audit log" subtitle="Attendance, scores, outcomes, roles and imports">
        <select className="input w-48" value={entity} onChange={(event) => setEntity(event.target.value)} aria-label="Filter entity">
          {ENTITIES.map((value) => (
            <option key={value || "all"} value={value}>
              {value ? titleCase(value) : "All entities"}
            </option>
          ))}
        </select>
      </PageHeader>

      <ErrorBanner error={logs.error} onRetry={() => logs.reload()} />

      <Card>
        {logs.loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="No audit entries in scope" body="Mutations made through the API appear here." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">When</th>
                  <th className="th">Actor</th>
                  <th className="th">Action</th>
                  <th className="th">Entity</th>
                  <th className="th">College</th>
                  <th className="th">Request</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-50">
                    <td className="td text-xs text-slate-500">{formatDateTime(entry.timestamp)}</td>
                    <td className="td">
                      <p className="font-semibold text-slate-800">{entry.actorName || entry.actorId}</p>
                      <p className="text-xs text-slate-500">{entry.actorId}</p>
                    </td>
                    <td className="td">
                      <Badge tone="brand">{entry.action}</Badge>
                    </td>
                    <td className="td text-xs">
                      {entry.entity}
                      <span className="text-slate-400">/{entry.entityId}</span>
                    </td>
                    <td className="td text-xs">{entry.collegeId || "—"}</td>
                    <td className="td text-xs text-slate-500">{entry.requestId || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="mt-4 text-xs text-slate-500">
        Showing up to 100 entries, newest first. Audit entries are immutable and college-scoped.
      </p>
    </div>
  );
}
