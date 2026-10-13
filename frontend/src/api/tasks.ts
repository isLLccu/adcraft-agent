import apiClient from './client';
import type { AdTask } from '../types';

export const tasksApi = {
  // 获取任务列表
  getTasks: (params?: { skip?: number; limit?: number; status?: string }) => {
    return apiClient.get<AdTask[]>('/api/v1/ad-tasks', { params });
  },

  // 获取任务详情
  getTask: (id: number) => {
    return apiClient.get<AdTask>(`/api/v1/ad-tasks/${id}`);
  },

  // 创建任务
  createTask: (data: Partial<AdTask>) => {
    return apiClient.post<AdTask>('/api/v1/ad-tasks', data);
  },

  // 重试任务
  retryTask: (id: number) => {
    return apiClient.post(`/api/v1/ad-tasks/${id}/retry`);
  },

  // 取消任务
  cancelTask: (id: number) => {
    return apiClient.post(`/api/v1/ad-tasks/${id}/cancel`);
  },

  // 删除任务
  deleteTask: (id: number) => {
    return apiClient.delete(`/api/v1/ad-tasks/${id}`);
  },
};
