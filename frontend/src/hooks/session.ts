import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { fetchSession } from "../api/client";

export const sessionQueryKey = ["session"] as const;

export const useSession = () =>
  useQuery({
    queryKey: sessionQueryKey,
    queryFn: fetchSession,
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
