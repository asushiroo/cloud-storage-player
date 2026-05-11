import { Outlet, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { useRequireSession } from "./hooks/session";
import { LibraryPage } from "./pages/LibraryPage";
import { LoginPage } from "./pages/LoginPage";
import { ManagementPage } from "./pages/ManagementPage";
import { PlayerPage } from "./pages/PlayerPage";
import { SettingsPage } from "./pages/SettingsPage";
import { VideoDetailPage } from "./pages/VideoDetailPage";

function ProtectedRoutes() {
  const session = useRequireSession();

  if (!session.data && session.isLoading) {
    return <p className="state-text">正在检查登录状态...</p>;
  }

  if (session.isError && !session.data) {
    return <p className="state-text">无法连接后端接口，请先确认 8000 端口后端已启动。</p>;
  }

  if (!session.data?.authenticated) {
    return null;
  }

  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<LoginPage />} path="/login" />
      <Route element={<ProtectedRoutes />}> 
        <Route element={<LibraryPage />} path="/" />
        <Route element={<ManagementPage />} path="/manage" />
        <Route element={<SettingsPage />} path="/settings" />
        <Route element={<VideoDetailPage />} path="/videos/:videoId" />
        <Route element={<PlayerPage />} path="/videos/:videoId/play" />
      </Route>
      <Route element={<Navigate replace to="/" />} path="*" />
    </Routes>
  );
}
