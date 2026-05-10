import { http } from "./http";
import type { PublicSettings } from "../types/api";

export async function fetchSettings(): Promise<PublicSettings> {
  const response = await http.get<PublicSettings>("/api/settings");
  return response.data;
}

export async function updateSettings(payload: Partial<PublicSettings>): Promise<PublicSettings> {
  const response = await http.post<PublicSettings>("/api/settings", payload);
  return response.data;
}

export async function authorizeBaidu(code: string): Promise<PublicSettings> {
  const response = await http.post<PublicSettings>("/api/settings/baidu/oauth", { code });
  return response.data;
}
