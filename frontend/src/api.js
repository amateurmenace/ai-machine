import axios from 'axios';

// API base URL configuration
// In development: uses proxy to localhost:8000 (configured in package.json)
// In production: uses REACT_APP_API_URL environment variable
const API_BASE_URL = process.env.REACT_APP_API_URL || '';

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 second timeout for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    // You can add auth tokens here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle specific error cases
    if (error.code === 'ECONNABORTED') {
      console.error('Request timeout');
    }
    if (!error.response) {
      console.error('Network error - backend may be offline');
    }
    return Promise.reject(error);
  }
);

export default api;
