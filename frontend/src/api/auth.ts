import { http } from "./http";
import type { AuthSession } from "../types/api";

export async function fetchSession(): Promise<AuthSession> {
  const response = await http.get<AuthSession>("/api/auth/session");
  return response.data;
}

export async function login(password: string): Promise<AuthSession> {
  const response = await http.post<AuthSession>("/api/auth/login", { password });
  return response.data;
}

export async function logout(): Promise<AuthSession> {
  const response = await http.post<AuthSession>("/api/auth/logout");
  return response.data;
}
