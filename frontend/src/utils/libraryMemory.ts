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

function parseStoredMemory(raw: string | null, search: string): LibraryPageMemory | null {
  if (!raw) {
    return null;
  }
  const parsed = JSON.parse(raw) as LibraryPageMemory;
  if (!parsed || parsed.search !== search) {
    return null;
  }
  if (Date.now() - parsed.savedAt > TTL_MS) {
    return null;
  }
  return parsed;
}

export function loadLibraryPageMemory(search: string): LibraryPageMemory | null {
  try {
    const fromSession = parseStoredMemory(window.sessionStorage.getItem(STORAGE_KEY), search);
    if (fromSession) {
      return fromSession;
    }
    const fromLocal = parseStoredMemory(window.localStorage.getItem(STORAGE_KEY), search);
    if (fromLocal) {
      return fromLocal;
    }
  } catch {
    return null;
  }

  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore storage cleanup failures
  }
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore storage cleanup failures
  }
  return null;
}

export function saveLibraryPageMemory(memory: Omit<LibraryPageMemory, "savedAt">) {
  const payload = JSON.stringify({
    ...memory,
    savedAt: Date.now(),
  } satisfies LibraryPageMemory);

  try {
    window.sessionStorage.setItem(STORAGE_KEY, payload);
  } catch {
    // ignore sessionStorage failures and continue to localStorage fallback
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, payload);
  } catch {
    // ignore localStorage failures
  }
}
