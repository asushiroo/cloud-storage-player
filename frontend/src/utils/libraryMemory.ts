const STORAGE_KEY = "cloud-storage-player:library-memory";
const TTL_MS = 10 * 60 * 1000;

export interface LibraryPageMemory {
  search: string;
  activePrimaryTag?: string;
  activeSecondaryTag?: string;
  visibleCount: number;
  scrollY: number;
  savedAt: number;
}

export function loadLibraryPageMemory(search: string): LibraryPageMemory | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as LibraryPageMemory;
    if (!parsed || parsed.search !== search) {
      return null;
    }
    if (Date.now() - parsed.savedAt > TTL_MS) {
      window.sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveLibraryPageMemory(memory: Omit<LibraryPageMemory, "savedAt">) {
  window.sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      ...memory,
      savedAt: Date.now(),
    } satisfies LibraryPageMemory),
  );
}
