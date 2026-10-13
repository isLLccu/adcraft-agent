export type Platform = 'xiaohongshu' | 'taobao' | 'douyin'
export type Mode = 'demo' | 'live'
export interface AIConfig { mode: Mode; model: string; embedding_mode: string; image_provider: string; max_agent_steps: number; version: string }
export interface Fact { id: string; label: string; value: string }
export interface Product { id: string; name: string; category: string; description: string; brand_id: string; facts: Fact[]; selling_points: string[]; image_url: string | null }
export interface KnowledgeDocument { id: string; title: string; content: string; brand_id: string; source: string; version: string | number }
export interface Evidence { id: string; document_id: string; title: string; text: string; score: number; source: string; version: string | number; chunk_index: number }
export interface TraceEvent { id: string; type: string; stage: string; message: string; data: Record<string, unknown>; elapsed_ms: number; created_at: string }
export interface Draft { title: string; body: string; slogan: string; selling_points: string[]; claims: { text: string; fact_ids: string[] }[]; evidence_ids: string[]; image_prompts: { label: string; prompt: string; negative_prompt: string }[]; platform: Platform }
export interface Run { id: string; session_id: string; product_id: string; message: string; platform: Platform; status: 'queued' | 'running' | 'completed' | 'needs_clarification' | 'failed'; mode: Mode; answer: string; draft: Draft | null; evidence: Evidence[]; trace: TraceEvent[]; validation: { passed: boolean; issues: { code: string; message: string; severity: 'warning' | 'error' }[] }; usage: { input_tokens: number; output_tokens: number; total_calls: number; latency_ms: number }; error: string | null; created_at: string; updated_at: string }
export interface GeneratedImage { url: string; label: string; mode: Mode; product_preserved: boolean; warning: string | null }
export interface ImageJob { id: string; run_id: string; status: 'queued' | 'running' | 'completed' | 'failed' | 'partial'; images: GeneratedImage[]; error: string | null }
export interface EvaluationReport { id: string; mode: 'offline'; created_at: string; cases_total: number; passed: number; failed: number; pass_rate: number; metrics: { name: string; value: number; total: number; passed: number }[]; cases: { id: string; category: string; input: string; expected: unknown; actual: unknown; passed: boolean }[]; notes: string[] }
