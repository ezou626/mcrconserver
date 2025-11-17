// eslint-disable-next-line @typescript-eslint/no-explicit-any
const API_BASE_URL = (window as any).__APP_CONFIG__.API_BASE_URL;

export interface User {
  username: string;
  role: number;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  access_token?: string;
  token_type?: string;
  username?: string;
  role?: number;
}

export interface CommandResponse {
  success: boolean;
  message?: string;
  error?: string;
  command?: string;
}

export interface ApiError {
  detail: string;
}

export interface ApiKey {
  api_key: string;
  created_at: string;
  username?: string; // Only present in all keys response for owners
}

export interface PaginationInfo {
  page: number;
  limit: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface ApiKeysResponse {
  success: boolean;
  api_keys: ApiKey[];
  pagination: PaginationInfo;
}

// JWT Token Management
class TokenManager {
  private static readonly TOKEN_KEY = 'jwt_access_token';

  static setToken(token: string): void {
    localStorage.setItem(this.TOKEN_KEY, token);
  }

  static getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  static removeToken(): void {
    localStorage.removeItem(this.TOKEN_KEY);
  }

  static isTokenExpired(token: string): boolean {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const exp = payload.exp * 1000; // Convert to milliseconds
      return Date.now() >= exp;
    } catch {
      return true; // If we can't parse it, consider it expired
    }
  }
}

class ApiService {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    // Get token and add Authorization header if available
    const token = TokenManager.getToken();
    const defaultHeaders: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (token && !TokenManager.isTokenExpired(token)) {
      defaultHeaders.Authorization = `Bearer ${token}`;
    }

    const defaultOptions: RequestInit = {
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, defaultOptions);

      if (!response.ok) {
        // If 401 and we have a token, it might be expired - remove it
        if (response.status === 401 && token) {
          TokenManager.removeToken();
        }

        const errorData: ApiError = await response.json().catch(() => ({
          detail: `HTTP ${response.status}: ${response.statusText}`,
        }));
        throw new Error(errorData.detail || 'Unknown error occurred');
      }

      return await response.json();
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Network error occurred');
    }
  }

  private async requestWithFormData<T>(
    endpoint: string,
    formData: FormData,
    method: string = 'POST'
  ): Promise<T> {
    // Get token for auth header
    const token = TokenManager.getToken();
    const authHeaders: HeadersInit = {};

    if (token && !TokenManager.isTokenExpired(token)) {
      authHeaders.Authorization = `Bearer ${token}`;
    }

    return this.request<T>(endpoint, {
      method,
      headers: authHeaders, // Only include auth header, let browser set Content-Type for FormData
      body: formData,
    });
  }

  async login(username: string, password: string): Promise<LoginResponse> {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const response = await this.requestWithFormData<LoginResponse>(
      '/auth/login',
      formData
    );

    // Store JWT token if login was successful
    if (response.success && response.access_token) {
      TokenManager.setToken(response.access_token);
    }

    return response;
  }

  async logout(): Promise<{ success: boolean; message: string }> {
    const response = await this.request<{ success: boolean; message: string }>(
      '/auth/logout',
      {
        method: 'POST',
      }
    );

    // Remove token from storage
    TokenManager.removeToken();

    return response;
  }

  async getAccountInfo(): Promise<{
    success: boolean;
    username: string;
    role: number;
  }> {
    return this.request<{ success: boolean; username: string; role: number }>(
      '/auth/account'
    );
  }

  async executeCommand(
    command: string,
    requireResult: boolean = true
  ): Promise<CommandResponse> {
    const params = new URLSearchParams();
    params.append('command', command);
    params.append('require_result', requireResult.toString());

    return this.request<CommandResponse>(`/rcon/session/command?${params}`, {
      method: 'POST',
    });
  }

  async checkSession(): Promise<boolean> {
    try {
      const token = TokenManager.getToken();

      // If no token or token is expired, return false
      if (!token || TokenManager.isTokenExpired(token)) {
        TokenManager.removeToken();
        return false;
      }

      // Verify token by calling account info
      await this.getAccountInfo();
      return true;
    } catch {
      TokenManager.removeToken();
      return false;
    }
  }

  // Manually clear authentication state
  clearAuth(): void {
    TokenManager.removeToken();
  }

  // API Key management
  async createApiKey(): Promise<{ success: boolean; api_key: string }> {
    return this.request<{ success: boolean; api_key: string }>(
      '/auth/api-key',
      {
        method: 'PUT',
      }
    );
  }

  async listApiKeys(
    page: number = 1,
    limit: number = 10
  ): Promise<ApiKeysResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    return this.request<ApiKeysResponse>(`/auth/api-key?${params}`);
  }

  async listAllApiKeys(
    page: number = 1,
    limit: number = 10
  ): Promise<ApiKeysResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      limit: limit.toString(),
    });
    return this.request<ApiKeysResponse>(`/auth/api-key/all?${params}`);
  }

  async revokeApiKey(
    apiKey: string
  ): Promise<{ success: boolean; message: string }> {
    const formData = new FormData();
    formData.append('api_key', apiKey);
    return this.requestWithFormData<{ success: boolean; message: string }>(
      '/auth/api-key',
      formData,
      'DELETE'
    );
  }
}

export const apiService = new ApiService();
