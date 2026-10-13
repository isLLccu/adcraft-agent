export interface User {
  id: number;
  username: string;
  email: string;
  role?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface Shop {
  id: number;
  user_id: number;
  name: string;
  industry?: string;
  brand_style?: string;
  target_audience?: string;
  main_platform?: string;
  description?: string;
  created_at: string;
  updated_at?: string;
}

export interface Product {
  id: number;
  shop_id: number;
  name: string;
  category: string;
  price: number;
  description?: string;
  selling_points?: string[];
  target_audience?: string;
  usage_scenario?: string;
  image_url?: string;
  tags?: string[];
  created_at: string;
  updated_at?: string;
}

export interface AdTask {
  id: number;
  user_id: number;
  shop_id: number;
  product_id: number;
  platform: 'xiaohongshu' | 'taobao' | 'douyin' | 'wechat';
  ad_type: string;
  style?: string;
  image_ratio?: string;
  copywriting_tone?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  error_message?: string;
  retry_count?: number;
  created_at: string;
  started_at?: string;
  finished_at?: string;
}

export interface AdCopy {
  id: number;
  task_id: number;
  title: string;
  body: string;
  slogan?: string;
  platform: string;
  version?: number;
  created_at: string;
}

export interface ImagePrompt {
  id: number;
  task_id: number;
  prompt: string;
  negative_prompt?: string;
  style?: string;
  ratio?: string;
  version?: number;
  created_at: string;
}

export interface Material {
  id: number;
  task_id: number;
  product_id: number;
  image_url: string;
  copy_id?: number;
  prompt_id?: number;
  status: string;
  is_favorite: boolean;
  created_at: string;
  copy?: AdCopy;
  prompt?: ImagePrompt;
  product?: Product;
  task?: AdTask;
}

export interface AuditResult {
  id: number;
  task_id: number;
  content_type: string;
  passed: boolean;
  risk_level?: string;
  issues?: string[];
  suggestions?: string[];
  created_at: string;
}

export interface StatsOverview {
  total_tasks: number;
  success_tasks: number;
  failed_tasks: number;
  success_rate: number;
  total_materials: number;
  avg_latency_ms: number;
  estimated_total_cost: number;
}

export interface TaskStats {
  today_tasks: number;
  week_tasks: number;
  month_tasks: number;
  platform_distribution: Record<string, number>;
}

export interface CostStats {
  today_cost: number;
  week_cost: number;
  month_cost: number;
  total_cost: number;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface ApiResponse<T = any> {
  data?: T;
  message?: string;
  error?: string;
}
