import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { fetchSession } from "../api/client";
import type { AuthSession } from "../types/api";

export const sessionQueryKey = ["session"] as const;
const SESSION_CACHE_KEY = "cloud-storage-player-authenticated";
const SESSION_TTL_MS = 10 * 60 * 1000;

interface CachedSessionPayload {
  authenticated: boolean;
  cached_at: number;
}

interface CachedSessionState {
  session: AuthSession;
  cachedAt: number;
}

const readCachedSession = (): CachedSessionState | undefined => {
  if (typeof window === "undefined") {
    return undefined;
  }
  const rawValue = window.localStorage.getItem(SESSION_CACHE_KEY);
  if (!rawValue) {
    return undefined;
  }

  try {
    const payload = JSON.parse(rawValue) as CachedSessionPayload;
    if (typeof payload.authenticated !== "boolean" || typeof payload.cached_at !== "number") {
      window.localStorage.removeItem(SESSION_CACHE_KEY);
      return undefined;
    }
    return {
      session: { authenticated: payload.authenticated },
      cachedAt: payload.cached_at,
    };
  } catch {
    window.localStorage.removeItem(SESSION_CACHE_KEY);
    return undefined;
  }
};

const writeCachedSession = (authenticated: boolean): void => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(
    SESSION_CACHE_KEY,
    JSON.stringify({
      authenticated,
      cached_at: Date.now(),
    } satisfies CachedSessionPayload),
  );
};

const fetchAndPersistSession = async (): Promise<AuthSession> => {
  const session = await fetchSession();
  writeCachedSession(session.authenticated);
  return session;
};

export const useSession = () =>
  useQuery({
    queryKey: sessionQueryKey,
    queryFn: fetchAndPersistSession,
    initialData: readCachedSession()?.session,
    initialDataUpdatedAt: readCachedSession()?.cachedAt,
    staleTime: SESSION_TTL_MS,
  });

export const useRequireSession = (): ReturnType<typeof useSession> => {
  const session = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (session.isLoading || session.data?.authenticated !== false) return;
    const next = encodeURIComponent(`${location.pathname}${location.search}`);
    navigate(`/login?next=${next}`, { replace: true });
  }, [location.pathname, location.search, navigate, session.data?.authenticated, session.isLoading]);

  return session;
};

export const useRedirectIfAuthenticated = (): ReturnType<typeof useSession> => {
  const session = useSession();
  const navigate = useNavigate();

  useEffect(() => {
    if (session.data?.authenticated) {
      navigate("/", { replace: true });
    }
  }, [navigate, session.data?.authenticated]);

  return session;
};

export const persistAuthenticatedSession = (): void => {
  writeCachedSession(true);
};

export const clearPersistedSession = (): void => {
  writeCachedSession(false);
};
