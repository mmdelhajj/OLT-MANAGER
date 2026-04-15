import axios, { AxiosError } from "axios";

/**
 * Single axios instance shared by every API package.
 *
 * The interceptor pulls the JWT from localStorage on each request and
 * redirects to /login on a 401, so individual route components don't need
 * to think about auth at all.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
  timeout: 30_000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("olt_jwt");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token expired or never set — purge and bounce.
      localStorage.removeItem("olt_jwt");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  }
);
