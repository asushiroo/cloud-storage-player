import { http } from "./http";
import type { ImportJob } from "../types/api";

export interface CreateImportPayload {
  source_path: string;
  folder_id?: number | null;
  title?: string | null;
}

export async function fetchImportJobs(): Promise<ImportJob[]> {
  const response = await http.get<ImportJob[]>("/api/imports");
  return response.data;
}

export async function createImport(payload: CreateImportPayload): Promise<ImportJob> {
  const response = await http.post<ImportJob>("/api/imports", payload);
  return response.data;
}
