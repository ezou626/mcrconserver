const API_BASE_URL = 'http://localhost:8000';

export interface User {
  username: string;
  role: number;
}

export interface LoginResponse {
  success: boolean;
  message: string;
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

class ApiService {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const defaultOptions: RequestInit = {
      credentials: 'include', // Include cookies for session management
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, defaultOptions);

      if (!response.ok) {
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
    return this.request<T>(endpoint, {
      method,
      headers: {}, // Let browser set Content-Type for FormData
      body: formData,
    });
  }

  async login(username: string, password: string): Promise<LoginResponse> {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    return this.requestWithFormData<LoginResponse>('/auth/login', formData);
  }

  async logout(): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>('/auth/logout', {
      method: 'POST',
    });
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
      await this.getAccountInfo();
      return true;
    } catch {
      return false;
    }
  }
}

export const apiService = new ApiService();
