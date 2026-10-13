import apiClient from './client';
import type { Product } from '../types';

export const productsApi = {
  // 获取商品列表
  getProducts: (params?: { skip?: number; limit?: number; shop_id?: number }) => {
    return apiClient.get<Product[]>('/api/v1/products', { params });
  },

  // 获取商品详情
  getProduct: (id: number) => {
    return apiClient.get<Product>(`/api/v1/products/${id}`);
  },

  // 创建商品
  createProduct: (data: Partial<Product>) => {
    return apiClient.post<Product>('/api/v1/products', data);
  },

  // 更新商品
  updateProduct: (id: number, data: Partial<Product>) => {
    return apiClient.put<Product>(`/api/v1/products/${id}`, data);
  },

  // 删除商品
  deleteProduct: (id: number) => {
    return apiClient.delete(`/api/v1/products/${id}`);
  },

  // 上传商品图片
  uploadImage: (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<{ image_url: string }>(`/api/v1/products/${id}/upload-image`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};
