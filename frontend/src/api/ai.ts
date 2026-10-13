import type { AIConfig, EvaluationReport, ImageJob, KnowledgeDocument, Platform, Product, Run } from '../types/ai'

const BASE = (import.meta.env.VITE_AI_API_BASE || '/api/v1/ai').replace(/\/$/, '')

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const body = await response.json() as { detail?: unknown; error?: unknown }
      const detail = body.detail || body.error
      if (typeof detail === 'string') message = detail
      else if (Array.isArray(detail)) message = detail.map((item: { msg?: string }) => item.msg || '输入不符合要求').join('；')
    } catch { /* A proxy may return a non-JSON error. */ }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const ai = {
  config: (signal?: AbortSignal) => request<AIConfig>('/config', { signal }),
  products: (signal?: AbortSignal) => request<Product[]>('/products', { signal }),
  createProduct: (body: Omit<Product, 'id' | 'image_url'>) => request<Product>('/products', { method: 'POST', body: JSON.stringify(body) }),
  uploadImage: (id: string, file: File) => { const body = new FormData(); body.append('file', file); return request<Product>(`/products/${encodeURIComponent(id)}/image`, { method: 'POST', body }); },
  documents: (brandId: string, signal?: AbortSignal) => request<KnowledgeDocument[]>(`/documents?brand_id=${encodeURIComponent(brandId)}`, { signal }),
  createDocument: (body: Omit<KnowledgeDocument, 'id'>) => request<KnowledgeDocument>('/documents', { method: 'POST', body: JSON.stringify(body) }),
  deleteDocument: (id: string) => request<void>(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  session: (signal?: AbortSignal) => request<{ id: string; created_at: string }>('/sessions', { method: 'POST', signal }),
  runs: (id: string, signal?: AbortSignal) => request<Run[]>(`/sessions/${encodeURIComponent(id)}/runs`, { signal }),
  createRun: (body: { session_id: string; product_id: string; message: string; platform: Platform; request_id: string }) => request<Run>('/runs', { method: 'POST', body: JSON.stringify(body) }),
  run: (id: string, signal?: AbortSignal) => request<Run>(`/runs/${encodeURIComponent(id)}`, { signal }),
  feedback: (id: string, body: { rating: number; comment: string; accepted: boolean }) => request<unknown>(`/runs/${encodeURIComponent(id)}/feedback`, { method: 'POST', body: JSON.stringify(body) }),
  generateImages: (id: string, indices: number[], requestId: string) => request<ImageJob>(`/runs/${encodeURIComponent(id)}/images`, { method: 'POST', body: JSON.stringify({ confirmed: true, indices, request_id: requestId }) }),
  imageJobs: (runId: string, signal?: AbortSignal) => request<ImageJob[]>(`/runs/${encodeURIComponent(runId)}/images`, { signal }),
  imageJob: (id: string, signal?: AbortSignal) => request<ImageJob>(`/image-jobs/${encodeURIComponent(id)}`, { signal }),
  latestEvaluation: (signal?: AbortSignal) => request<EvaluationReport | null>('/evaluations/latest', { signal }),
  evaluate: () => request<EvaluationReport>('/evaluations', { method: 'POST', body: JSON.stringify({ mode: 'demo' }) }),
}

export function assetUrl(url: string): string {
  if (/^(https?:|data:|blob:)/i.test(url)) return url
  if (/^https?:\/\//i.test(BASE)) return new URL(url, new URL(BASE).origin).href
  return url
}

export function requestId(): string { return globalThis.crypto?.randomUUID?.() || `request-${Date.now()}-${Math.random().toString(36).slice(2)}` }
export function errorMessage(error: unknown): string { return error instanceof Error ? error.message : '发生错误，请重试。' }
export function isAbort(error: unknown): boolean { return error instanceof DOMException && error.name === 'AbortError' }
