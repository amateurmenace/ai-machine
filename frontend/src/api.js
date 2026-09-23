import axios from 'axios';

// Where the API is, decided when the console is built (REACT_APP_API_URL):
//
//   a URL    that API: a console on the web talking to a tunnel.
//   unset    the API that served this page: the container, and npm start's
//            proxy in development.
//   "none"   no API on the web. The public site: the landing page, the guide
//            and the rules work, and nothing reaches for an API that is not
//            there. The same build served by the API on its own machine is the
//            operator's console, so there it uses the API it came from.
const CONFIGURED_API = (process.env.REACT_APP_API_URL || '').trim();
const NO_PUBLIC_API = CONFIGURED_API.toLowerCase() === 'none';
const LOOPBACK_HOSTNAMES = ['localhost', '127.0.0.1', '[::1]', '::1'];
const servedFromThisMachine =
  typeof window !== 'undefined' && LOOPBACK_HOSTNAMES.includes(window.location.hostname);

export const apiAvailable = !NO_PUBLIC_API || servedFromThisMachine;
export const NO_PUBLIC_API_MESSAGE =
  'This assistant is not open to the public yet. Its API runs on a machine that is not on the internet.';

const API_BASE_URL = NO_PUBLIC_API ? '' : CONFIGURED_API;

// The admin token. The API answers administrative requests (create, configure,
// ingest, delete) from its own machine without asking; from anywhere else,
// including this console when it is served from the web, it refuses them
// unless they carry the token set on the server as COMMUNITY_ADMIN_TOKEN.
// Residents' questions never need it. It lives in this browser only.
const ADMIN_TOKEN_KEY = 'civic_admin_token';

export function getAdminToken() {
  try {
    return window.localStorage.getItem(ADMIN_TOKEN_KEY) || '';
  } catch (e) {
    return '';
  }
}

export function setAdminToken(token) {
  try {
    if (token) {
      window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
    } else {
      window.localStorage.removeItem(ADMIN_TOKEN_KEY);
    }
  } catch (e) {
    // Private mode, or storage blocked: the token lasts as long as the page.
  }
}

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 60 second timeout for long operations
  headers: {
    'Content-Type': 'application/json',
  },
});

// Every request carries the admin token when one has been entered. On public
// routes the API ignores it.
api.interceptors.request.use(
  (config) => {
    if (!apiAvailable) {
      // Refused here, before it leaves: the static host answers every path
      // with the landing page's HTML, which reads as a broken API, not no API.
      const error = new Error(NO_PUBLIC_API_MESSAGE);
      error.noPublicApi = true;
      return Promise.reject(error);
    }
    const token = getAdminToken();
    if (token) {
      config.headers['X-Admin-Token'] = token;
    }
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
    if (error.noPublicApi) {
      return Promise.reject(error);
    }
    // Handle specific error cases
    if (error.code === 'ECONNABORTED') {
      console.error('Request timeout');
    }
    if (!error.response) {
      console.error('Network error - backend may be offline');
    }
    if (error.response && error.response.data && error.response.data.admin_required) {
      // Not an outage: the API is up and has said no. Its reason names the fix.
      console.warn(error.response.data.detail);
    }
    return Promise.reject(error);
  }
);

// The resolved backend origin. Components that link directly to a
// backend-served document (the constitution, the system facts, the OpenAPI
// docs) need this: in production the frontend and the API are on different
// hosts, so a root-relative path would resolve against the frontend.
export const apiBaseUrl = API_BASE_URL;

export default api;
