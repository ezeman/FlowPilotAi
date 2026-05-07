import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Spinner from "./components/Spinner";
import { useAuth } from "./context/AuthContext";
import BillingPage from "./pages/BillingPage";
import ContentCalendarPage from "./pages/ContentCalendarPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import PostEditorPage from "./pages/PostEditorPage";
import PostsPage from "./pages/PostsPage";
import ProfilePage from "./pages/ProfilePage";
import PublishLogsPage from "./pages/PublishLogsPage";
import RegisterPage from "./pages/RegisterPage";
import SchedulePostPage from "./pages/SchedulePostPage";
import SettingsPage from "./pages/SettingsPage";
import StudioPage from "./pages/StudioPage";

function ProtectedRoute({ children }) {
  const { token, loading, activeAccountId } = useAuth();

  if (loading) {
    return (
      <div className="full-screen-panel">
        <Spinner />
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <Layout key={activeAccountId || "default-account"}>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/studio"
        element={
          <ProtectedRoute>
            <StudioPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/calendar"
        element={
          <ProtectedRoute>
            <ContentCalendarPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/posts"
        element={
          <ProtectedRoute>
            <PostsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/posts/:postId/edit"
        element={
          <ProtectedRoute>
            <PostEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/posts/:postId/schedule"
        element={
          <ProtectedRoute>
            <SchedulePostPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/publish-logs"
        element={
          <ProtectedRoute>
            <PublishLogsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/billing"
        element={
          <ProtectedRoute>
            <BillingPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
