import apiClient from './client';
import type { Shop } from '../types';

export const shopsApi = {
  // 获取店铺列表
  getShops: (params?: { skip?: number; limit?: number }) => {
    return apiClient.get<Shop[]>('/api/v1/shops', { params });
  },

  // 获取店铺详情
  getShop: (id: number) => {
    return apiClient.get<Shop>(`/api/v1/shops/${id}`);
  },

  // 创建店铺
  createShop: (data: Partial<Shop>) => {
    return apiClient.post<Shop>('/api/v1/shops', data);
  },

  // 更新店铺
  updateShop: (id: number, data: Partial<Shop>) => {
    return apiClient.put<Shop>(`/api/v1/shops/${id}`, data);
  },

  // 删除店铺
  deleteShop: (id: number) => {
    return apiClient.delete(`/api/v1/shops/${id}`);
  },
};
