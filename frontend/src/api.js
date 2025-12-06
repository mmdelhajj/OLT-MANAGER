import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Add auth token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors (token expired)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

// Auth
export const login = (username, password) =>
  api.post('/api/auth/login', { username, password });

// Dashboard
export const getDashboardStats = () => api.get('/api/dashboard');

// OLTs
export const getOLTs = () => api.get('/api/olts');
export const getOLT = (id) => api.get(`/api/olts/${id}`);
export const createOLT = (data) => api.post('/api/olts', data);
export const updateOLT = (id, data) => api.put(`/api/olts/${id}`, data);
export const deleteOLT = (id) => api.delete(`/api/olts/${id}`);
export const pollOLT = (id) => api.post(`/api/olts/${id}/poll`);

// ONUs
export const getONUs = (params) => api.get('/api/onus', { params });
export const getONU = (id) => api.get(`/api/onus/${id}`);
export const getONUsByOLT = (oltId) => api.get(`/api/olts/${oltId}/onus`);
export const searchONUs = (query) => api.get('/api/onus/search', { params: { q: query } });
export const updateONU = (id, data) => api.put(`/api/onus/${id}`, data);
export const deleteONU = (id) => api.delete(`/api/onus/${id}`);
export const uploadONUImage = (id, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/api/onus/${id}/image`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
};
export const deleteONUImage = (id, imageIndex = 0) => api.delete(`/api/onus/${id}/image?image_index=${imageIndex}`);

// Regions
export const getRegions = () => api.get('/api/regions');
export const getRegion = (id) => api.get(`/api/regions/${id}`);
export const createRegion = (data) => api.post('/api/regions', data);
export const updateRegion = (id, data) => api.put(`/api/regions/${id}`, data);
export const deleteRegion = (id) => api.delete(`/api/regions/${id}`);

// Users
export const getUsers = () => api.get('/api/users');
export const getUser = (id) => api.get(`/api/users/${id}`);
export const createUser = (data) => api.post('/api/users', data);
export const updateUser = (id, data) => api.put(`/api/users/${id}`, data);
export const deleteUser = (id) => api.delete(`/api/users/${id}`);
export const changePassword = (data) => api.post('/api/auth/change-password', data);

// Settings
export const getSettings = () => api.get('/api/settings');
export const updateSettings = (data) => api.put('/api/settings', data);

// License
export const getLicenseInfo = () => api.get('/api/license');

// Traffic
export const getOltTraffic = (oltId) => api.get(`/api/olts/${oltId}/traffic`);
export const getAllTraffic = () => api.get('/api/traffic/all');

// Traffic History (for graphs)
export const getOnuTrafficHistory = (onuId, range) => api.get(`/api/traffic/history/onu/${onuId}?range=${range}`);
export const getPonTrafficHistory = (oltId, ponPort, range) => api.get(`/api/traffic/history/pon/${oltId}/${ponPort}?range=${range}`);
export const getOltTrafficHistory = (oltId, range) => api.get(`/api/traffic/history/olt/${oltId}?range=${range}`);

// Diagrams (Splitter Simulator)
export const getDiagrams = () => api.get('/api/diagrams');
export const getDiagram = (id) => api.get(`/api/diagrams/${id}`);
export const createDiagram = (data) => api.post('/api/diagrams', data);
export const updateDiagram = (id, data) => api.put(`/api/diagrams/${id}`, data);
export const deleteDiagram = (id) => api.delete(`/api/diagrams/${id}`);

// Generic get function
export const get = (url) => api.get(url);

export default api;
