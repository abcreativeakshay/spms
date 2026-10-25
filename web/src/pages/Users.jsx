import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Icon } from "../components/Icon";
import {
  Badge,
  Card,
  CardHeader,
  EmptyState,
  ErrorBanner,
  Field,
  PageHeader,
  Spinner,
} from "../components/ui";

const EMPTY = {
  name: "",
  email: "",
  role: "trainer",
  password: "",
  collegeIds: [],
  collegeId: "",
  batchId: "",
  rollNo: "",
  degree: "",
  branch: "",
  gradYear: "",
  cgpa: "",
  superAdmin: false,
};

export default function Users() {
  const { me, isAdmin } = useAuth();
  const [roleFilter, setRoleFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const users = useAsync(
    () =>
      isAdmin
        ? api("/users", {
            query: {
              limit: 100,
              role: roleFilter || undefined,
              active: activeFilter === "" ? undefined : activeFilter === "true",
            },
          })
        : Promise.resolve(null),
    [isAdmin, roleFilter, activeFilter]
  );
  const colleges = useAsync(
    () => (isAdmin ? api("/colleges", { query: { limit: 100 } }) : Promise.resolve(null)),
    [isAdmin]
  );
  const batches = useAsync(
    () => (isAdmin ? api("/batches", { query: { limit: 100 } }) : Promise.resolve(null)),
    [isAdmin]
  );

  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  if (!isAdmin) {
    return (
      <Card>
        <CardHeader title="User management is admin-only" />
        <p className="p-5 text-sm text-slate-500">
          Ask an administrator to create trainers, students or other admins.
        </p>
      </Card>
    );
  }

  const isStudentRole = form.role === "student";

  async function create(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const body = {
        name: form.name,
        email: form.email,
        role: form.role,
        phone: null,
        superAdmin: form.role === "admin" ? form.superAdmin : false,
        password: form.password || null,
        sendSetupEmail: !form.password,
      };
      if (isStudentRole) {
        body.collegeId = form.collegeId;
        body.collegeIds = form.collegeId ? [form.collegeId] : [];
        body.batchId = form.batchId || null;
        body.rollNo = form.rollNo || null;
        body.degree = form.degree || null;
        body.branch = form.branch || null;
        body.gradYear = form.gradYear ? Number(form.gradYear) : null;
        body.cgpa = form.cgpa === "" ? null : Number(form.cgpa);
        body.skills = [];
      } else {
        body.collegeIds = form.collegeIds;
      }
      const result = await api("/users", { method: "POST", body });
      setForm(EMPTY);
      setShowCreate(false);
      setNotice(
        result?.setupLink
          ? `User created. Password setup link: ${result.setupLink}`
          : `User created (${result?.user?.email || body.email}).`
      );
      users.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggle(user) {
    setError("");
    setNotice("");
    try {
      await api(`/users/${user.uid}/${user.active ? "disable" : "enable"}`, { method: "POST" });
      users.reload();
    } catch (err) {
      setError(err.message);
    }
  }

  const items = users.data?.items || [];
  const collegeOptions = colleges.data?.items || [];
  const batchOptions = (batches.data?.items || []).filter(
    (batch) => !form.collegeId || batch.collegeId === form.collegeId
  );

  return (
    <div>
      <PageHeader title="People" subtitle="Trainers, admins and student accounts">
        <select className="input w-36" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)} aria-label="Filter role">
          <option value="">All roles</option>
          {["admin", "trainer", "student"].map((role) => (
            <option key={role} value={role}>
              {titleCase(role)}
            </option>
          ))}
        </select>
        <select className="input w-36" value={activeFilter} onChange={(event) => setActiveFilter(event.target.value)} aria-label="Filter status">
          <option value="">Any status</option>
          <option value="true">Active</option>
          <option value="false">Disabled</option>
        </select>
        <button type="button" className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Icon name="plus" className="h-4 w-4" />
          {showCreate ? "Close" : "New user"}
        </button>
      </PageHeader>

      <ErrorBanner
        error={users.error || colleges.error || batches.error || (error ? { message: error } : null)}
        onRetry={() => users.reload()}
      />
      {notice ? (
        <div className="mb-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {notice}
        </div>
      ) : null}

      {showCreate ? (
        <Card className="mb-5">
          <CardHeader
            title="Create user"
            subtitle="A password is optional; otherwise a setup link is generated when Firebase is configured"
          />
          <form onSubmit={create} className="grid gap-4 p-5 md:grid-cols-3">
            <Field label="Name">
              <input required className="input" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </Field>
            <Field label="Email">
              <input required type="email" className="input" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            </Field>
            <Field label="Role">
              <select className="input" value={form.role} onChange={(event) => setForm({ ...EMPTY, role: event.target.value })}>
                <option value="trainer">Trainer</option>
                {me?.superAdmin ? <option value="admin">Admin</option> : null}
                <option value="student">Student</option>
              </select>
            </Field>

            {isStudentRole ? (
              <>
                <Field label="College">
                  <select required className="input" value={form.collegeId} onChange={(event) => setForm({ ...form, collegeId: event.target.value, batchId: "" })}>
                    <option value="">Select a college</option>
                    {collegeOptions.map((college) => (
                      <option key={college.id} value={college.id}>{college.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Batch" hint="Optional; can be assigned later">
                  <select className="input" value={form.batchId} onChange={(event) => setForm({ ...form, batchId: event.target.value })}>
                    <option value="">No batch</option>
                    {batchOptions.map((batch) => (
                      <option key={batch.id} value={batch.id}>{batch.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Roll number">
                  <input className="input" value={form.rollNo} onChange={(event) => setForm({ ...form, rollNo: event.target.value })} />
                </Field>
                <Field label="Degree">
                  <input className="input" placeholder="B.Tech" value={form.degree} onChange={(event) => setForm({ ...form, degree: event.target.value })} />
                </Field>
                <Field label="Branch">
                  <input className="input" value={form.branch} onChange={(event) => setForm({ ...form, branch: event.target.value })} />
                </Field>
                <Field label="Graduation year">
                  <input type="number" min="1990" max="2100" className="input" value={form.gradYear} onChange={(event) => setForm({ ...form, gradYear: event.target.value })} />
                </Field>
                <Field label="CGPA">
                  <input type="number" min="0" max="10" step="0.01" className="input" value={form.cgpa} onChange={(event) => setForm({ ...form, cgpa: event.target.value })} />
                </Field>
              </>
            ) : (
              <Field label="Colleges" hint="Ctrl/Cmd click to select multiple">
                <select
                  multiple
                  required
                  className="input min-h-[92px]"
                  value={form.collegeIds}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      collegeIds: Array.from(event.target.selectedOptions, (option) => option.value),
                    })
                  }
                >
                  {collegeOptions.map((college) => (
                    <option key={college.id} value={college.id}>{college.name}</option>
                  ))}
                </select>
              </Field>
            )}

            <Field label="Password" hint="Optional; at least 8 characters">
              <input type="password" minLength="8" className="input" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
            </Field>

            {form.role === "admin" && me?.superAdmin ? (
              <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-slate-300 text-brand-600"
                  checked={form.superAdmin}
                  onChange={(event) => setForm({ ...form, superAdmin: event.target.checked })}
                />
                Super admin (all colleges)
              </label>
            ) : null}

            <div className="flex items-end md:col-span-3">
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? "Creating…" : "Create user"}
              </button>
            </div>
          </form>
        </Card>
      ) : null}

      <Card>
        {users.loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState title="No users match these filters" body="Create a trainer or student account to get started." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px]">
              <thead className="bg-slate-50">
                <tr>
                  <th className="th">User</th>
                  <th className="th">Role</th>
                  <th className="th">Colleges</th>
                  <th className="th">Status</th>
                  <th className="th">Created</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((user) => (
                  <tr key={user.uid} className="hover:bg-slate-50">
                    <td className="td">
                      <p className="font-semibold text-slate-900">{user.name}</p>
                      <p className="text-xs text-slate-500">{user.email}</p>
                    </td>
                    <td className="td">
                      <Badge tone={user.role === "admin" ? "brand" : user.role === "trainer" ? "blue" : "slate"}>
                        {titleCase(user.role)}
                      </Badge>
                      {user.superAdmin ? <Badge tone="amber" className="ml-1">Super</Badge> : null}
                    </td>
                    <td className="td text-xs">
                      {(user.collegeIds || []).map((id) => (
                        <span key={id} className="mr-1 inline-block rounded bg-slate-100 px-1.5 py-0.5">
                          {collegeOptions.find((college) => college.id === id)?.name || id}
                        </span>
                      ))}
                      {(user.collegeIds || []).length === 0 ? "—" : null}
                    </td>
                    <td className="td">
                      <Badge tone={user.active ? "green" : "rose"}>{user.active ? "Active" : "Disabled"}</Badge>
                    </td>
                    <td className="td text-xs text-slate-500">{formatDate(user.createdAt)}</td>
                    <td className="td text-right">
                      {user.uid === me?.uid ? (
                        <span className="text-xs text-slate-400">You</span>
                      ) : (
                        <button type="button" className="link" onClick={() => toggle(user)}>
                          {user.active ? "Disable" : "Enable"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <Badge tone="brand">{items.length}</Badge>
        users shown. Student accounts can also be imported from CSV on the Students page.
      </div>
    </div>
  );
}
