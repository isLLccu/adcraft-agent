import axios from 'axios';
import type { AxiosInstance, AxiosError } from 'axios';
import { message } from 'antd';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // 请求拦截器：自动添加 token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // 响应拦截器：处理错误
    this.client.interceptors.response.use(
      (response) => {
        return response;
      },
      (error: AxiosError) => {
        if (error.response) {
          const status = error.response.status;
          const data: any = error.response.data;

          switch (status) {
            case 401:
              // 未授权，清除 token 并跳转到登录页
              localStorage.removeItem('access_token');
              localStorage.removeItem('user');
              message.error('登录已过期，请重新登录');
              window.location.href = '/login';
              break;
            case 403:
              message.error('没有权限访问该资源');
              break;
            case 404:
              message.error('请求的资源不存在');
              break;
            case 500:
              message.error(data?.detail || '服务器错误，请稍后重试');
              break;
            default:
              message.error(data?.detail || '请求失败，请稍后重试');
          }
        } else if (error.request) {
          message.error('网络错误，请检查网络连接');
        } else {
          message.error('请求配置错误');
        }
        return Promise.reject(error);
      }
    );
  }

  public get<T = any>(url: string, config?: any) {
    return this.client.get<T>(url, config);
  }

  public post<T = any>(url: string, data?: any, config?: any) {
    return this.client.post<T>(url, data, config);
  }

  public put<T = any>(url: string, data?: any, config?: any) {
    return this.client.put<T>(url, data, config);
  }

  public patch<T = any>(url: string, data?: any, config?: any) {
    return this.client.patch<T>(url, data, config);
  }

  public delete<T = any>(url: string, config?: any) {
    return this.client.delete<T>(url, config);
  }
}

export const apiClient = new ApiClient();
export default apiClient;
