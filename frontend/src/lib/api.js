/**
 * StockPilot WMS - API client
 *
 * A thin, dependency-free wrapper around fetch() that:
 *  - prefixes every call with the versioned API base URL
 *  - attaches the bearer token and the X-Tenant-Id header (multi-tenancy)
 *  - normalises the backend error envelope { detail, code, details }
 *  - supports Idempotency-Key on mutating requests
 */

const RAW_BASE = process.env.REACT_APP_BACKEND_URL || '';
const API_VERSION = process.env.REACT_APP_API_VERSION || '/api/v1';

export const API_BASE = `${RAW_BASE}${API_VERSION}`;

const ACCESS_KEY = 'sp.access_token';
const REFRESH_KEY = 'sp.refresh_token';
const TENANT_KEY = 'sp.tenant_id';

function safeStorage() {
  try {
    return window.localStorage;
  } catch (e) {
    return null;
  }
}

const storage = safeStorage();

export const tokenStore = {
  getAccess: () => (storage ? storage.getItem(ACCESS_KEY) : null),
  getRefresh: () => (storage ? storage.getItem(REFRESH_KEY) : null),
  getTenant: () => (storage ? storage.getItem(TENANT_KEY) : null),
  set({ accessToken, refreshToken, tenantId }) {
    if (!storage) return;
    if (accessToken !== undefined) {
      if (accessToken) storage.setItem(ACCESS_KEY, accessToken);
      else storage.removeItem(ACCESS_KEY);
    }
    if (refreshToken !== undefined) {
      if (refreshToken) storage.setItem(REFRESH_KEY, refreshToken);
      else storage.removeItem(REFRESH_KEY);
    }
    if (tenantId !== undefined) {
      if (tenantId) storage.setItem(TENANT_KEY, tenantId);
      else storage.removeItem(TENANT_KEY);
    }
  },
  clear() {
    if (!storage) return;
    storage.removeItem(ACCESS_KEY);
    storage.removeItem(REFRESH_KEY);
    storage.removeItem(TENANT_KEY);
  },
};

export class ApiError extends Error {
  constructor(message, status, code, details) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function buildQuery(params) {
  if (!params) return '';
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      value.forEach((v) => {
        if (v !== undefined && v !== null && v !== '') search.append(key, v);
      });
    } else {
      search.append(key, value);
    }
  });
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

function extractError(status, payload) {
  if (payload && typeof payload === 'object') {
    const details = payload.details;
    let message = payload.detail || payload.message || 'Request failed';
    if (Array.isArray(details) && details.length && details[0].message) {
      message = details
        .map((d) => (d.field ? `${d.field}: ${d.message}` : d.message))
        .join('; ');
    } else if (Array.isArray(payload.detail) && payload.detail.length) {
      message = payload.detail
        .map((d) => `${(d.loc || []).join('.')}: ${d.msg}`)
        .join('; ');
    }
    return new ApiError(message, status, payload.code || 'error', details);
  }
  return new ApiError('Request failed', status, 'error', payload);
}

let onUnauthorized = null;
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

const IDEMPOTENT_METHODS = new Set(['POST', 'PUT', 'PATCH']);

async function request(method, path, options = {}) {
  const { body, params, idempotencyKey, auth = true, raw = false } = options;

  const headers = { Accept: 'application/json' };
  if (body !== undefined && !raw) headers['Content-Type'] = 'application/json';

  if (auth) {
    const token = tokenStore.getAccess();
    if (token) headers.Authorization = `Bearer ${token}`;
    const tenantId = tokenStore.getTenant();
    if (tenantId) headers['X-Tenant-Id'] = tenantId;
  }

  let key = idempotencyKey;
  if (!key && IDEMPOTENT_METHODS.has(method)) {
    key = `${method}:${path}:${Date.now()}:${Math.random().toString(36).slice(2)}`;
  }
  if (key) headers['Idempotency-Key'] = key;

  let response;
  try {
    response = await fetch(`${API_BASE}${path}${buildQuery(params)}`, {
      method,
      headers,
      body:
        body === undefined
          ? undefined
          : raw
          ? body
          : JSON.stringify(body),
    });
  } catch (error) {
    throw new ApiError(
      navigator.onLine
        ? 'Unable to reach the server. Please try again.'
        : 'You are offline. This action needs a connection.',
      0,
      'network_error'
    );
  }

  if (response.status === 204) return null;

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (e) {
      payload = text;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && auth && onUnauthorized) onUnauthorized();
    throw extractError(response.status, payload);
  }

  return payload;
}

export const api = {
  get: (path, params, options) => request('GET', path, { ...options, params }),
  post: (path, body, options) => request('POST', path, { ...options, body }),
  patch: (path, body, options) => request('PATCH', path, { ...options, body }),
  put: (path, body, options) => request('PUT', path, { ...options, body }),
  del: (path, options) => request('DELETE', path, options),
  raw: request,
};

export default api;
