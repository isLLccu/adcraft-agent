import apiClient from './client';
import type { LoginRequest, RegisterRequest, TokenResponse, User } from '../types';

export const authApi = {
  // 登录
  login: (data: LoginRequest) => {
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);

    return apiClient.post<TokenResponse>('/api/v1/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  },

  // 注册
  register: (data: RegisterRequest) => {
    return apiClient.post<User>('/api/v1/auth/register', data);
  },

  // 获取当前用户信息
  getCurrentUser: () => {
    return apiClient.get<User>('/api/v1/auth/me');
  },
};
