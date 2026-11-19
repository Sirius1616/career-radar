import { Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { getToken, setToken } from "./api";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardLayout from "./pages/DashboardLayout";
import PreferencesPage from "./pages/PreferencesPage";

function RequireAuth() {
  return getToken() ? <Outlet /> : <Navigate to="/login" replace />;
}

export default function AppRoutes() {
  const navigate = useNavigate();
  const handleAuthed = () => navigate("/");
  return (
    <Routes>
      <Route
        path="/login"
        element={
          getToken() ? (
            <Navigate to="/" replace />
          ) : (
            <LoginPage onAuthed={handleAuthed} />
          )
        }
      />
      <Route
        path="/register"
        element={
          getToken() ? (
            <Navigate to="/" replace />
          ) : (
            <RegisterPage onAuthed={handleAuthed} />
          )
        }
      />
      <Route element={<RequireAuth />}>
        <Route element={<DashboardLayout />}>
          <Route index element={<Placeholder title="Overview" />} />
          <Route path="profile" element={<Placeholder title="Profile" />} />
          <Route path="preferences" element={<PreferencesPage />} />
          <Route path="jobs" element={<Placeholder title="Jobs" />} />
          <Route path="applications" element={<Placeholder title="Applications" />} />
          <Route path="activity" element={<Placeholder title="Activity" />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <section>
      <h2>{title}</h2>
      <p>Coming in a later milestone.</p>
    </section>
  );
}

export { setToken };
