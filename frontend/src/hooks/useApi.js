import { useCallback, useEffect, useRef, useState } from 'react';
import api, { ApiError } from '../lib/api';

/** Track browser connectivity with a small delay to avoid flapping. */
export function useOnlineStatus() {
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);
    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  return online;
}

/**
 * Declarative GET resource with loading / error / empty states and refetch.
 * Pages use this for every list and detail view.
 */
export function useApiResource(path, params, options = {}) {
  const { enabled = true, initialData = null, keepPrevious = true } = options;
  const [data, setData] = useState(initialData);
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(Boolean(enabled && path));
  const [error, setError] = useState(null);
  const paramsKey = JSON.stringify(params || {});
  const requestId = useRef(0);

  const fetchData = useCallback(async () => {
    if (!path) return undefined;
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get(path, params);
      if (id !== requestId.current) return undefined;
      if (result && typeof result === 'object' && Array.isArray(result.items)) {
        setData(result.items);
        setMeta(result.meta || null);
      } else {
        setData(result);
        setMeta(result?.meta || null);
      }
      return result;
    } catch (err) {
      if (id !== requestId.current) return undefined;
      if (err.name !== 'AbortError') setError(err);
      return undefined;
    } finally {
      if (id === requestId.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, paramsKey]);

  useEffect(() => {
    if (!enabled || !path) {
      setLoading(false);
      return;
    }
    if (!keepPrevious) {
      setData(initialData);
      setMeta(null);
    }
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, path, paramsKey]);

  return { data, meta, loading, error, refetch: fetchData, setData, setMeta };
}

/** Debounce a rapidly changing value (e.g. a search input). */
export function useDebounced(value, delay = 350) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/** Convenience wrapper for imperative actions with toast + loading state. */
export function useAction() {
  const [loading, setLoading] = useState(false);
  const run = useCallback(async (fn) => {
    setLoading(true);
    try {
      return await fn();
    } finally {
      setLoading(false);
    }
  }, []);
  return { loading, run };
}

export { ApiError };
