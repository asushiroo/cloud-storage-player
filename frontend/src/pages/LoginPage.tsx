import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { login } from "../api/client";
import { sessionQueryKey, useRedirectIfAuthenticated } from "../hooks/session";
import type { ApiError } from "../types/api";

export function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const session = useRedirectIfAuthenticated();

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionQueryKey });
      navigate(searchParams.get("next") || "/", { replace: true });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
    },
  });

  return (
    <div className="login-page">
      <div className="login-card">
        <p className="eyebrow">Kyoo code moved into frontend/</p>
        <h1>登录局域网影库</h1>
        <div className="form-stack">
          <input
            autoFocus
            className="text-input"
            onChange={(event) => {
              setPassword(event.target.value);
              setError(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && password.trim()) {
                mutation.mutate(password);
              }
            }}
            placeholder="输入管理员密码"
            type="password"
            value={password}
          />
          {error ? <p className="error-text">{error}</p> : null}
          <button className="primary-button" disabled={mutation.isPending || password.trim().length === 0 || session.isLoading} onClick={() => mutation.mutate(password)} type="button">
            {mutation.isPending ? "登录中..." : "登录"}
          </button>
        </div>
      </div>
    </div>
  );
}
