import { Navigate, Route, Routes } from "react-router-dom";
import Protected, { AppLayout } from "./components/AppLayout";
import { useAuth } from "./context/AuthContext";
import Applications from "./pages/Applications";
import Audit from "./pages/Audit";
import BatchDetail from "./pages/BatchDetail";
import Batches from "./pages/Batches";
import Colleges from "./pages/Colleges";
import Companies from "./pages/Companies";
import Dashboard from "./pages/Dashboard";
import Drives from "./pages/Drives";
import Login from "./pages/Login";
import Notifications from "./pages/Notifications";
import Reports from "./pages/Reports";
import StudentDetail from "./pages/StudentDetail";
import Students from "./pages/Students";
import Users from "./pages/Users";

function ProfileRoute() {
  const { me } = useAuth();
  if (!me?.student?.id) return <Navigate to="/" replace />;
  return <StudentDetail studentId={me.student.id} />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected />}>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="students" element={<Students />} />
          <Route path="students/:studentId" element={<StudentDetail />} />
          <Route path="profile" element={<ProfileRoute />} />
          <Route path="batches" element={<Batches />} />
          <Route path="batches/:batchId" element={<BatchDetail />} />
          <Route path="drives" element={<Drives />} />
          <Route path="applications" element={<Applications />} />
          <Route path="colleges" element={<Colleges />} />
          <Route path="companies" element={<Companies />} />
          <Route path="users" element={<Users />} />
          <Route path="reports" element={<Reports />} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="audit" element={<Audit />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
