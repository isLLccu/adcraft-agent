import apiClient from './client';
import type { Material } from '../types';

export const materialsApi = {
  // 获取素材列表
  getMaterials: (params?: {
    skip?: number;
    limit?: number;
    product_id?: number;
    platform?: string;
    status?: string;
    is_favorite?: boolean;
  }) => {
    return apiClient.get<Material[]>('/api/v1/materials', { params });
  },

  // 获取素材详情
  getMaterial: (id: number) => {
    return apiClient.get<Material>(`/api/v1/materials/${id}`);
  },

  // 更新素材
  updateMaterial: (id: number, data: Partial<Material>) => {
    return apiClient.patch<Material>(`/api/v1/materials/${id}`, data);
  },

  // 收藏/取消收藏
  toggleFavorite: (id: number, is_favorite: boolean) => {
    return apiClient.patch<Material>(`/api/v1/materials/${id}`, { is_favorite });
  },

  // 删除素材
  deleteMaterial: (id: number) => {
    return apiClient.delete(`/api/v1/materials/${id}`);
  },

  // 下载素材
  downloadMaterial: (id: number) => {
    return apiClient.get(`/api/v1/materials/${id}/download`, {
      responseType: 'blob',
    });
  },

  // 获取素材统计
  getStats: () => {
    return apiClient.get('/api/v1/materials/stats');
  },
};
