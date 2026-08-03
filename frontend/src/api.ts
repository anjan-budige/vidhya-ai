import axios from 'axios';
import toast from 'react-hot-toast';

// Centralized Axios instance
// Uses withCredentials to ensure HttpOnly cookies (session tokens) are passed correctly
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  withCredentials: true, // Crucial for HttpOnly cookie authentication
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper to get cookie by name
const getCookie = (name: string) => {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift();
  return null;
};

// Request interceptor to attach CSRF token
api.interceptors.request.use((config) => {
  // Only attach for state-changing requests
  if (config.method && ['post', 'put', 'patch', 'delete'].includes(config.method.toLowerCase())) {
    const csrfToken = getCookie('csrf_token');
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

// Response interceptor for global error handling
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
      const isUserRoute = window.location.pathname.startsWith('/user');
      const isLoginPage = window.location.pathname.includes('/login');
      // Don't auto-redirect or toast on /user routes (they handle auth inline)
      if (!isLoginPage && !isUserRoute) {
        window.dispatchEvent(new Event('auth:unauthorized'));
        toast.error('Session expired. Please log in again.');
      }
    } else if (error.response && error.response.data && error.response.data.detail) {
      // Show backend error detail if available, except for 401s on login page (which component handles)
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
