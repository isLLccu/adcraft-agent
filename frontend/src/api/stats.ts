import apiClient from './client';
import type { StatsOverview, TaskStats, CostStats } from '../types';

export const statsApi = {
  // 获取统计概览
  getOverview: () => {
    return apiClient.get<StatsOverview>('/api/v1/stats/overview');
  },

  // 获取任务统计
  getTaskStats: () => {
    return apiClient.get<TaskStats>('/api/v1/stats/tasks');
  },

  // 获取成本统计
  getCostStats: () => {
    return apiClient.get<CostStats>('/api/v1/stats/costs');
  },
};
