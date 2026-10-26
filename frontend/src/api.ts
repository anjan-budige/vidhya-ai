import axios from 'axios';
import toast from 'react-hot-toast';

export const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

// Uses withCredentials to ensure HttpOnly cookies (session tokens) are passed correctly
const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // Crucial for HttpOnly cookie authentication
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getCookie = (name: string) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift();
  return null;
};

// Browsers refuse SameSite=None cookies on plain HTTP and can drop the CSRF
// cookie entirely. Make sure it exists before any state-changing request.
let csrfInFlight: Promise<void> | null = null;
export async function ensureCsrf() {
  if (getCookie('csrf_token')) return;
  if (!csrfInFlight) {
    csrfInFlight = axios
      .get(`${API_BASE}/auth/csrf`, { withCredentials: true })
      .then(() => undefined)
      .catch(() => undefined)
      .finally(() => {
        csrfInFlight = null;
      });
  }
  await csrfInFlight;
}

api.interceptors.request.use(async (config) => {
  // Only attach for state-changing requests
  if (config.method && ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
    await ensureCsrf();
    const csrfToken = getCookie('csrf_token');
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    // If the API returns HTML (e.g., from a SPA fallback when bypassing Nginx), reject it!
    const contentType = response.headers['content-type'];
    if (typeof contentType === 'string' && contentType.includes('text/html')) {
      return Promise.reject(new Error('Received HTML instead of JSON from API - proxy misconfiguration?'));
    }
    return response;
  },
  (error) => {
    // If we get a 401 Unauthorized, the user's session expired or is invalid
    if (error.response && error.response.status === 401) {
      const isLoginPage = window.location.pathname.includes('/login');
      if (!isLoginPage) {
        window.dispatchEvent(new Event('auth:unauthorized'));
        toast.error('Session expired. Please log in again.');
      }
    } else if (error.response && error.response.data && error.response.data.detail) {
      if (!(error.response.status === 401 && window.location.pathname.includes('/login'))) {
        const detail = error.response.data.detail;
        if (Array.isArray(detail)) {
          // FastAPI 422 Validation errors return an array of objects
          toast.error(detail[0].msg || 'Validation error');
        } else if (typeof detail === 'string') {
          toast.error(detail);
        } else {
          toast.error('An unexpected error occurred');
        }
      }
    } else if (!error.response) {
      toast.error('Network error. Please check your connection.');
    }
    return Promise.reject(error);
  }
);

export default api;
