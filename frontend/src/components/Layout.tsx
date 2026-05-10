import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { logout } from "../api/client";
import { sessionQueryKey, useSession } from "../hooks/session";

export function Layout({ children }: PropsWithChildren) {
  const session = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionQueryKey });
      navigate("/login", { replace: true });
    },
  });

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-left">
          <Link className="brand" to="/">
            Cloud Storage Player
          </Link>
          <nav className="header-nav">
            <NavLink className="nav-link" to="/">
              媒体库
            </NavLink>
            <NavLink className="nav-link" to="/settings">
              设置
            </NavLink>
          </nav>
        </div>
        <div className="header-right">
          {session.data?.authenticated ? (
            <button className="header-button" disabled={logoutMutation.isPending} onClick={() => logoutMutation.mutate()} type="button">
              {logoutMutation.isPending ? "退出中..." : "退出"}
            </button>
          ) : (
            <Link className="header-button" to="/login">
              登录
            </Link>
          )}
        </div>
      </header>
      <main className="page-container">{children}</main>
    </div>
  );
}
