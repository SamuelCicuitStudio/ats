// Lightweight cache of parsed files, persisted in localStorage.
// Keys are based on filename + size + lastModified. This avoids hashing content and keeps it fast.

const STORAGE_KEY = "ats_parse_cache_v1";

function safeStorage() {
  if (typeof window === "undefined" || !window.localStorage) return null;
  return window.localStorage;
}

function loadCache() {
  const storage = safeStorage();
  if (!storage) return { jd: {}, cv: {} };
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return { jd: {}, cv: {} };
    const parsed = JSON.parse(raw);
    return {
      jd: parsed.jd || {},
      cv: parsed.cv || {},
    };
  } catch (e) {
    return { jd: {}, cv: {} };
  }
}

function saveCache(cache) {
  const storage = safeStorage();
  if (!storage) return;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(cache));
  } catch (_) {
    // ignore write errors
  }
}

function keyFromFile(file) {
  if (!file) return null;
  const parts = [file.name, file.size, file.lastModified];
  return parts.join("|");
}

export const parseCache = {
  get(type, file) {
    const key = keyFromFile(file);
    if (!key) return null;
    const cache = loadCache();
    return cache[type]?.[key] || null;
  },
  set(type, file, payload) {
    const key = keyFromFile(file);
    if (!key) return;
    const cache = loadCache();
    const bucket = cache[type] || {};
    bucket[key] = {
      payload,
      meta: {
        name: file.name,
        size: file.size,
        lastModified: file.lastModified,
        storedAt: Date.now(),
      },
    };
    cache[type] = bucket;
    saveCache(cache);
  },
  clear() {
    const storage = safeStorage();
    if (!storage) return;
    storage.removeItem(STORAGE_KEY);
  },
};
