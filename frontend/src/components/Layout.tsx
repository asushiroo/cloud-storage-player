import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type PropsWithChildren } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import logoImage from "../../asserts/logo.png";
import { logout } from "../api/client";
import { clearPersistedSession, sessionQueryKey, useSession } from "../hooks/session";

export function Layout({ children }: PropsWithChildren) {
  const session = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [librarySearchInput, setLibrarySearchInput] = useState("");
  const isShowcasePage = location.pathname === "/library" || location.pathname === "/recommend";
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      clearPersistedSession();
      queryClient.setQueryData(sessionQueryKey, { authenticated: false });
      await queryClient.invalidateQueries({ queryKey: sessionQueryKey });
      navigate("/login", { replace: true });
    },
  });

  useEffect(() => {
    if (location.pathname !== "/library") {
      setLibrarySearchInput("");
      return;
    }
    const currentSearch = new URLSearchParams(location.search).get("q") ?? "";
    setLibrarySearchInput(currentSearch);
  }, [location.pathname, location.search]);

  const submitLibrarySearch = () => {
    const nextSearch = librarySearchInput.trim();
    navigate(
      {
        pathname: "/library",
        search: nextSearch ? `?q=${encodeURIComponent(nextSearch)}` : "",
      },
      { replace: location.pathname === "/library" },
    );
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-left">
          <Link aria-label="Cloud Storage Player" className="brand brand-logo-link" to="/recommend">
            <img alt="Cloud Storage Player" className="brand-logo" src={logoImage} />
          </Link>
          <nav className="header-nav">
            <NavLink className="nav-link" to="/recommend">
              推荐
            </NavLink>
            <NavLink className="nav-link" to="/library">
              媒体库
            </NavLink>
            <NavLink className="nav-link" to="/manage">
              导入与任务
            </NavLink>
            <NavLink className="nav-link" to="/settings">
              设置
            </NavLink>
          </nav>
        </div>
        <form
          className="header-search-form"
          onSubmit={(event) => {
            event.preventDefault();
            submitLibrarySearch();
          }}
        >
          <input
            className="header-search-input"
            onChange={(event) => setLibrarySearchInput(event.target.value)}
            placeholder="搜索媒体库片名 / 标签 / 路径"
            type="search"
            value={librarySearchInput}
          />
        </form>
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
      <main className={isShowcasePage ? "page-container page-container-library" : "page-container"}>{children}</main>
    </div>
  );
}
