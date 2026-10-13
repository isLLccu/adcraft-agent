import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { ai, assetUrl, errorMessage, isAbort, requestId } from '../../api/ai'
import type { AIConfig, EvaluationReport, ImageJob, KnowledgeDocument, Platform, Product, Run } from '../../types/ai'

type IconName = 'spark' | 'plus' | 'send' | 'file' | 'box' | 'chevron' | 'check' | 'image' | 'trash' | 'close' | 'copy' | 'chart' | 'arrow' | 'refresh'
const paths: Record<IconName, ReactNode> = {
  spark: <><path d="m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6Z" /><path d="m20 2 .5 1.5L22 4l-1.5.5L20 6l-.5-1.5L18 4l1.5-.5Z" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  send: <><path d="m4 4 17 8-17 8 3-8Z" /><path d="M7 12h14" /></>,
  file: <><path d="M14 3H5v18h14V8Z" /><path d="M14 3v5h5M8 12h8M8 16h6" /></>,
  box: <><path d="m12 3 9 5v9l-9 5-9-5V8Z" /><path d="m3 8 9 5 9-5M12 13v9M7 5.8l9 5" /></>,
  chevron: <path d="m8 10 4 4 4-4" />,
  check: <path d="m5 12 4 4 10-10" />,
  image: <><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8" cy="8" r="1.5" /><path d="m3 17 5-5 4 4 4-6 5 7" /></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  copy: <><rect x="8" y="8" width="12" height="13" rx="2" /><path d="M15 8V3H3v13h5" /></>,
  chart: <><path d="M4 3v17h17M8 16v-5M13 16V7M18 16V4" /></>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5" /><path d="M19 11a7 7 0 0 0-12-5L4 9m1 4a7 7 0 0 0 12 5l3-3" /></>,
}
function Icon({ name, size = 18 }: { name: IconName; size?: number }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg> }
const platforms: { id: Platform; label: string; short: string }[] = [{ id: 'xiaohongshu', label: '小红书', short: 'RED' }, { id: 'taobao', label: '淘宝', short: 'TB' }, { id: 'douyin', label: '抖音', short: 'DY' }]
const statusNames: Record<Run['status'], string> = { queued: '等待执行', running: '执行中', completed: '已完成', needs_clarification: '需要补充信息', failed: '执行失败' }
const suggestions = [
  { label: '生成一版上新文案', text: '根据商品事实和品牌指南，生成一版上新文案。卖点要有依据，不要编造功效。' },
  { label: '让文案更自然', text: '在上一版的基础上，把文案改得自然一些，少用夸张的广告表达，保留真实商品卖点。' },
  { label: '检查一句商品宣传', text: '我想写「保温24小时，绝对不会漏水」，请先核对商品资料，资料不足时告诉我。' },
]
const running = (status: string) => status === 'queued' || status === 'running'
function rememberSession(id: string, productId: string) { try { localStorage.setItem('adcraft-workspace-session', JSON.stringify({ id, productId })) } catch { /* The workbench also works when browser storage is unavailable. */ } }
function savedSession(): { id: string; productId: string } | null { try { return JSON.parse(localStorage.getItem('adcraft-workspace-session') || 'null') as { id: string; productId: string } | null } catch { return null } }

export default function Workbench() {
  const [config, setConfig] = useState<AIConfig | null>(null)
  const [products, setProducts] = useState<Product[]>([])
  const [productId, setProductId] = useState('')
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([])
  const [sessionId, setSessionId] = useState('')
  const [runs, setRuns] = useState<Run[]>([])
  const [focusedId, setFocusedId] = useState('')
  const [platform, setPlatform] = useState<Platform>('xiaohongshu')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [switching, setSwitching] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)
  const [modal, setModal] = useState<'product' | 'document' | 'evaluation' | null>(null)
  const [report, setReport] = useState<EvaluationReport | null>(null)
  const [evaluating, setEvaluating] = useState(false)
  const [imageJobs, setImageJobs] = useState<Record<string, ImageJob>>({})
  const [generatingImages, setGeneratingImages] = useState(false)
  const [activeImageJob, setActiveImageJob] = useState('')
  const [imageIndices, setImageIndices] = useState<number[]>([])
  const [rating, setRating] = useState(4)
  const [feedbackComment, setFeedbackComment] = useState('')
  const [accepted, setAccepted] = useState(false)
  const [feedbackSaved, setFeedbackSaved] = useState(false)
  const [feedbackSending, setFeedbackSending] = useState(false)
  const [copied, setCopied] = useState('')
  const chatScrollRef = useRef<HTMLDivElement>(null)
  const messageRef = useRef<HTMLTextAreaElement>(null)
  const uploadRef = useRef<HTMLInputElement>(null)
  const copyTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const busyRef = useRef(false)
  const runRequestRef = useRef<{ signature: string; key: string } | null>(null)
  const imageRequestRef = useRef<{ signature: string; key: string } | null>(null)
  const product = products.find(item => item.id === productId)
  const brandId = product?.brand_id
  const selectedRun = runs.find(run => run.id === focusedId) || runs.at(-1)
  const selectedRunId = selectedRun?.id
  const pendingRun = runs.find(run => running(run.status))
  const pendingRunId = pendingRun?.id
  const selectedImageCount = selectedRun?.draft?.image_prompts.length || 0
  const isBusy = sending || Boolean(pendingRun) || switching

  useEffect(() => {
    const controller = new AbortController()
    async function initialize() {
      setLoading(true); setError('')
      try {
        const [nextConfig, nextProducts, nextReport] = await Promise.all([ai.config(controller.signal), ai.products(controller.signal), ai.latestEvaluation(controller.signal)])
        const saved = savedSession()
        const firstId = nextProducts.some(item => item.id === saved?.productId) ? saved!.productId : nextProducts[0]?.id || ''
        let nextSession: { id: string } | null = null
        let previousRuns: Run[] = []
        if (saved && saved.productId === firstId) {
          try { previousRuns = await ai.runs(saved.id, controller.signal); nextSession = saved } catch (reason) { if (isAbort(reason)) throw reason }
        }
        if (!nextSession) nextSession = await ai.session(controller.signal)
        if (controller.signal.aborted) return
        setConfig(nextConfig); setProducts(nextProducts); setReport(nextReport); setProductId(firstId)
        setSessionId(nextSession.id); setRuns(previousRuns); setFocusedId(previousRuns.at(-1)?.id || '')
        rememberSession(nextSession.id, firstId)
      } catch (reason) { if (!isAbort(reason)) setError(`连接工作台失败：${errorMessage(reason)}。请确认后端已启动。`) }
      finally { if (!controller.signal.aborted) setLoading(false) }
    }
    void initialize()
    return () => controller.abort()
  }, [refreshKey])

  useEffect(() => {
    const controller = new AbortController()
    setDocuments([])
    if (brandId) void ai.documents(brandId, controller.signal).then(setDocuments).catch(reason => { if (!isAbort(reason)) setError(errorMessage(reason)) })
    return () => controller.abort()
  }, [brandId])

  useEffect(() => {
    if (!pendingRunId) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    async function poll() {
      try {
        const next = await ai.run(pendingRunId!, controller.signal)
        if (controller.signal.aborted) return
        failures = 0
        setRuns(current => current.map(item => item.id === next.id ? next : item))
        if (running(next.status)) timer = setTimeout(() => { void poll() }, 850)
      } catch (reason) {
        if (isAbort(reason)) return
        failures += 1
        if (failures >= 3) setError(`暂时无法同步任务进度：${errorMessage(reason)}。任务可能仍在后台执行，可刷新恢复。`)
        timer = setTimeout(() => { void poll() }, Math.min(5000, failures * 1200))
      }
    }
    void poll()
    return () => { controller.abort(); if (timer) clearTimeout(timer) }
  }, [pendingRunId])

  useEffect(() => {
    if (!activeImageJob) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    async function poll() {
      try {
        const next = await ai.imageJob(activeImageJob, controller.signal)
        if (controller.signal.aborted) return
        failures = 0
        setImageJobs(current => ({ ...current, [next.run_id]: next }))
        if (running(next.status)) timer = setTimeout(() => { void poll() }, 1000)
        else { setActiveImageJob(''); if (next.error) setError(next.error) }
      } catch (reason) {
        if (isAbort(reason)) return
        failures += 1
        if (failures >= 3) setError(`图片任务同步失败：${errorMessage(reason)}`)
        timer = setTimeout(() => { void poll() }, Math.min(5000, failures * 1200))
      }
    }
    void poll()
    return () => { controller.abort(); if (timer) clearTimeout(timer) }
  }, [activeImageJob])

  useEffect(() => {
    if (!selectedRunId) return
    const controller = new AbortController()
    // Restore persisted image jobs when a conversation or a previous turn is reopened.
    void ai.imageJobs(selectedRunId, controller.signal).then(jobs => {
      if (controller.signal.aborted) return
      const latest = jobs.at(-1)
      if (latest) {
        setImageJobs(current => ({ ...current, [latest.run_id]: latest }))
        if (running(latest.status)) setActiveImageJob(latest.id)
      }
    }).catch(reason => { if (!isAbort(reason)) setError(`恢复图片记录失败：${errorMessage(reason)}`) })
    return () => controller.abort()
  }, [selectedRunId])

  useEffect(() => {
    setImageIndices(Array.from({ length: Math.min(selectedImageCount, 3) }, (_, index) => index))
    setRating(4); setFeedbackComment(''); setAccepted(false); setFeedbackSaved(false)
  }, [selectedRun?.id, selectedImageCount])
  useEffect(() => {
    const container = chatScrollRef.current
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    container?.scrollTo({ top: container.scrollHeight, behavior: reducedMotion ? 'instant' : 'smooth' })
  }, [runs.length, pendingRun?.status])
  useEffect(() => () => { if (copyTimer.current) clearTimeout(copyTimer.current) }, [])

  async function newConversation(nextProductId = productId) {
    if (isBusy) return
    setSwitching(true); setError('')
    try {
      const next = await ai.session()
      setSessionId(next.id); setProductId(nextProductId); setRuns([]); setFocusedId(''); setMessage('')
      rememberSession(next.id, nextProductId)
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setSwitching(false) }
  }
  async function send(event?: FormEvent) {
    event?.preventDefault()
    if (!message.trim() || !product || !sessionId || isBusy || busyRef.current) return
    busyRef.current = true; setSending(true); setError('')
    const text = message.trim()
    const signature = JSON.stringify({ sessionId, productId: product.id, text, platform })
    if (runRequestRef.current?.signature !== signature) runRequestRef.current = { signature, key: requestId() }
    const key = runRequestRef.current.key
    try {
      const next = await ai.createRun({ session_id: sessionId, product_id: product.id, message: text, platform, request_id: key })
      runRequestRef.current = null
      setRuns(current => [...current, next]); setFocusedId(next.id); setMessage('')
    } catch (reason) { setError(errorMessage(reason)) }
    finally { busyRef.current = false; setSending(false) }
  }
  async function upload(file: File | undefined) {
    if (!file || !product) return
    if (!file.type.startsWith('image/')) { setError('请选择 PNG、JPEG 或 WebP 图片。'); return }
    setUploading(true); setError('')
    try { const next = await ai.uploadImage(product.id, file); setProducts(current => current.map(item => item.id === next.id ? next : item)) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setUploading(false); if (uploadRef.current) uploadRef.current.value = '' }
  }
  async function removeDocument(id: string) {
    setError('')
    try { await ai.deleteDocument(id); setDocuments(current => current.filter(item => item.id !== id)) }
    catch (reason) { setError(errorMessage(reason)) }
  }
  async function generateImages() {
    if (!selectedRun || !imageIndices.length || generatingImages || activeImageJob) return
    setGeneratingImages(true); setError('')
    const indices = [...imageIndices].sort((a, b) => a - b)
    const signature = JSON.stringify({ runId: selectedRun.id, indices })
    if (imageRequestRef.current?.signature !== signature) imageRequestRef.current = { signature, key: requestId() }
    const key = imageRequestRef.current.key
    try {
      const job = await ai.generateImages(selectedRun.id, indices, key)
      imageRequestRef.current = null
      setImageJobs(current => ({ ...current, [job.run_id]: job })); if (running(job.status)) setActiveImageJob(job.id)
    } catch (reason) { setError(errorMessage(reason)) }
    finally { setGeneratingImages(false) }
  }
  async function saveFeedback() {
    if (!selectedRun || feedbackSending) return
    setFeedbackSending(true); setError('')
    try { await ai.feedback(selectedRun.id, { rating, comment: feedbackComment, accepted }); setFeedbackSaved(true) }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setFeedbackSending(false) }
  }
  async function evaluate() {
    setEvaluating(true); setError('')
    try { setReport(await ai.evaluate()); setModal('evaluation') }
    catch (reason) { setError(errorMessage(reason)) }
    finally { setEvaluating(false) }
  }
  async function copyDraft(run: Run) {
    if (!run.draft) return
    try {
      await navigator.clipboard.writeText(`${run.draft.title}\n\n${run.draft.body}\n\n${run.draft.slogan}`)
      setCopied(run.id); if (copyTimer.current) clearTimeout(copyTimer.current)
      copyTimer.current = setTimeout(() => setCopied(''), 1800)
    } catch { setError('浏览器没有允许复制，请选中文案手动复制。') }
  }
  function chooseImage(index: number) { setImageIndices(current => current.includes(index) ? current.filter(item => item !== index) : current.length < 3 ? [...current, index] : current) }

  return <div className="workbench">
    <header className="topbar">
      <a className="brand" href="/" aria-label="AdCraft 首页"><span className="brand-mark"><Icon name="spark" size={23} /></span><span>AdCraft<span className="brand-dot">.</span></span><span className="brand-caption">AI 内容工作台</span></a>
      <div className="topbar-actions">
        <span className={`mode-tag ${config?.mode === 'live' ? 'live' : ''}`}><i />{config ? config.mode === 'live' ? 'LIVE · 真实模型' : 'DEMO · 演示模式' : '正在连接'}</span>
        <button className="quiet-button evaluation-link" onClick={() => { if (report) setModal('evaluation'); else void evaluate() }} disabled={loading || evaluating}><Icon name="chart" />{evaluating ? '评测中…' : '评测报告'}</button>
        <span className="workspace-avatar" title="本地单用户工作空间">A</span>
      </div>
    </header>
    <div className="workspace-banner"><span className="banner-label">LOCAL WORKSPACE</span><span>{config?.mode === 'live' ? '已连接模型服务。文案生成会调用真实模型；图片生成需单独确认。' : '演示模式会重放固定流程，无需 API Key。可检查检索证据与校验结果；不代表真实模型效果。'}</span></div>
    {error && <div className="global-error" role="alert"><span>{error}</span><button aria-label="关闭错误提示" onClick={() => setError('')}><Icon name="close" size={17} /></button>{!config && <button className="quiet-button" onClick={() => setRefreshKey(value => value + 1)}>重新连接</button>}</div>}
    <main className="workspace-grid">
      <aside className="context-panel">
        <div className="panel-eyebrow">CONTEXT</div>
        <div className="panel-title-row"><h2>创作上下文</h2><span className="small-count">01</span></div>
        <p className="panel-description">让每一个卖点都有据可依。</p>
        <div className="section-label"><Icon name="box" size={16} /><span>当前商品</span><button className="icon-button" title="添加商品" aria-label="添加商品" onClick={() => setModal('product')} disabled={loading || isBusy}><Icon name="plus" size={17} /></button></div>
        <label className="sr-only" htmlFor="product-selector">选择商品</label>
        <select id="product-selector" className="product-select" value={productId} disabled={loading || isBusy} onChange={event => { void newConversation(event.target.value) }}><option value="" disabled>{loading ? '正在加载…' : '请选择商品'}</option>{products.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        {product && <div className="product-card">
          <div className="product-photo">{product.image_url ? <img src={assetUrl(product.image_url)} alt={product.name} /> : <div className="product-placeholder"><Icon name="box" size={43} /><span>上传商品原图</span></div>}<button className="photo-upload" disabled={uploading || isBusy} onClick={() => uploadRef.current?.click()}><Icon name="image" size={14} />{uploading ? '上传中…' : product.image_url ? '更换原图' : '上传原图'}</button><input ref={uploadRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={event => { void upload(event.target.files?.[0]) }} /></div>
          <div className="product-card-content"><span className="product-category">{product.category || '商品'}</span><h3>{product.name}</h3><p>{product.description}</p></div>
        </div>}
        {product && <div className="facts-section"><div className="section-label"><span>商品事实</span><span className="muted">{product.facts.length} 项</span></div><dl>{product.facts.map(fact => <div key={fact.id}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>{product.selling_points.length > 0 && <div className="selling-points">{product.selling_points.map((point, index) => <span key={index}>{point}</span>)}</div>}</div>}
        <div className="section-label knowledge-label"><Icon name="file" size={16} /><span>品牌知识</span><span className="muted">{documents.length}</span><button className="icon-button" title="导入品牌资料" aria-label="导入品牌资料" onClick={() => setModal('document')} disabled={!product || loading || isBusy}><Icon name="plus" size={17} /></button></div>
        <div className="knowledge-list">{documents.map(document => <div className="knowledge-item" key={document.id}><span className="file-icon"><Icon name="file" size={17} /></span><div><strong>{document.title}</strong><small>v{document.version} · {document.content.length.toLocaleString()} 字</small></div><button className="icon-button delete-document" aria-label={`删除 ${document.title}`} title="删除资料" disabled={isBusy} onClick={() => { void removeDocument(document.id) }}><Icon name="trash" size={15} /></button></div>)}{!documents.length && <p className="empty-note">添加品牌语气、内容规范或产品说明，生成时会检索相关片段。</p>}</div>
        <button className="import-button" onClick={() => setModal('document')} disabled={!product || loading || isBusy}><Icon name="plus" size={15} />导入品牌资料</button>
        <div className="context-footnote"><span className="tiny-check"><Icon name="check" size={12} /></span><p>商品事实用于核对规格，品牌资料用于检索内容要求。</p></div>
      </aside>

      <section className="conversation-panel">
        <div className="conversation-heading"><div><div className="panel-eyebrow">CREATE WITH CONFIDENCE</div><h1>从一个想法，到一份好内容<span>.</span></h1></div><button className="quiet-button new-chat" disabled={loading || isBusy} onClick={() => { void newConversation() }}><Icon name="plus" size={16} />新对话</button></div>
        <div className="channel-bar"><span>发布平台</span><div className="platform-options">{platforms.map(item => <button className={platform === item.id ? 'active' : ''} key={item.id} disabled={isBusy} onClick={() => setPlatform(item.id)}><span className={`platform-icon ${item.id}`}>{item.short}</span>{item.label}</button>)}</div><span className="channel-note">支持连续修改</span></div>
        <div ref={chatScrollRef} className="chat-scroll" aria-live="polite" aria-busy={isBusy}>
          {loading ? <div className="chat-empty"><span className="loading-dot" /><h2>正在准备工作台</h2><p>加载商品与品牌资料…</p></div> : !runs.length ? <div className="chat-empty"><div className="welcome-symbol"><Icon name="spark" size={34} /></div><span className="welcome-kicker">YOUR CONTENT COPILOT</span><h2>告诉我，你想为商品写些什么？</h2><p>我会结合商品资料与品牌要求，<br />生成文案，并展示使用的依据和检查结果。</p><div className="welcome-examples">{suggestions.map((suggestion, index) => <button key={suggestion.label} onClick={() => { setMessage(suggestion.text); messageRef.current?.focus() }}><span className="example-number">0{index + 1}</span><span>{suggestion.label}</span><Icon name="arrow" size={16} /></button>)}</div></div> : runs.map(run => <article className={`conversation-turn ${selectedRun?.id === run.id ? 'focused-turn' : ''}`} key={run.id}>
            <div className="user-message"><span className="message-avatar user-avatar">你</span><div><div className="message-meta">你<span>{platforms.find(item => item.id === run.platform)?.label}</span></div><p>{run.message}</p></div></div>
            <div className="assistant-message"><span className="message-avatar assistant-avatar"><Icon name="spark" size={17} /></span><div className="assistant-content"><div className="message-meta">AdCraft<span className={`run-status ${run.status}`}><i />{statusNames[run.status]}</span><button className="inspect-button" onClick={() => setFocusedId(run.id)}>{selectedRun?.id === run.id ? '正在查看依据' : '查看依据'}<Icon name="arrow" size={12} /></button></div>
              {running(run.status) && <div className="working-message"><span className="loading-dot" /><span>{run.trace.at(-1)?.message || '正在读取商品资料与品牌知识…'}</span></div>}
              {run.answer && <p className="assistant-answer">{run.answer}</p>}
              {run.status === 'needs_clarification' && <div className="clarification-note">补充所需资料后，可以在下方继续回复。</div>}
              {run.error && <div className="inline-error">{run.error}</div>}
              {run.draft && <div className="draft-card"><div className="draft-topline"><span><span className="draft-marker" />文案草稿</span><button className="quiet-button" onClick={() => { void copyDraft(run) }}><Icon name={copied === run.id ? 'check' : 'copy'} size={14} />{copied === run.id ? '已复制' : '复制'}</button></div><h3>{run.draft.title}</h3><p className="draft-body">{run.draft.body}</p>{run.draft.slogan && <div className="draft-slogan">{run.draft.slogan}</div>}<div className="draft-footer"><span className={run.validation.passed ? 'validation-good' : 'validation-bad'}><Icon name={run.validation.passed ? 'check' : 'file'} size={14} />{run.validation.passed ? '通过当前规则检查' : '发现待处理问题'}</span><span>{run.evidence.length} 个资料片段 · {run.draft.claims.length} 个事实声明</span></div></div>}
              {run.mode === 'demo' && !running(run.status) && <span className="demo-output-note">演示输出 · 固定重放，非真实模型生成</span>}
            </div></div>
          </article>)}
        </div>
        <form className="composer" onSubmit={event => { void send(event) }}><textarea ref={messageRef} value={message} onChange={event => setMessage(event.target.value)} placeholder={product ? `为「${product.name}」生成内容，或继续修改上一版…` : '请先添加商品…'} disabled={loading || isBusy || !product || !sessionId} maxLength={3000} aria-label="创作需求" onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() } }} /><div className="composer-bottom"><span><Icon name="spark" size={13} />{isBusy ? '任务执行中，请稍候' : 'Enter 发送 · Shift + Enter 换行'}</span><button className="send-button" type="submit" disabled={!message.trim() || loading || isBusy || !product || !sessionId}>{sending ? '提交中' : '发送'}<Icon name="send" size={16} /></button></div></form>
        <p className="composer-note">内容仍需人工审核。当前规则检查不等于完整事实证明。</p>
      </section>

      <aside className="inspector-panel">
        <div className="panel-eyebrow">INSPECT & REFINE</div><div className="panel-title-row"><h2>依据与执行</h2><span className="small-count">02</span></div><p className="panel-description">了解这份内容是如何完成的。</p>
        <div className="inspector-section"><div className="section-label"><span>执行记录</span>{selectedRun && <span className="muted">{selectedRun.trace.length} 步</span>}</div>{selectedRun?.trace.length ? <ol className="trace-list">{selectedRun.trace.map((event, index) => <li key={event.id}><span className={`trace-dot ${index === selectedRun.trace.length - 1 && running(selectedRun.status) ? 'trace-pending' : ''}`}>{index + 1}</span><div><strong>{event.message}</strong><small>{event.stage} · {(event.elapsed_ms / 1000).toFixed(1)}s</small>{Object.keys(event.data || {}).length > 0 && <details className="trace-data"><summary>查看记录数据</summary><pre>{JSON.stringify(event.data, null, 2)}</pre></details>}</div></li>)}</ol> : <div className="inspector-empty"><Icon name="spark" size={20} /><p>提交需求后，这里会显示实际行动与结果。</p></div>}<p className="subtle-note">展示行动与观察记录。</p></div>
        <div className="inspector-section"><div className="section-label"><Icon name="file" size={15} /><span>检索依据</span><span className="muted">{selectedRun?.evidence.length || 0}</span></div>{selectedRun?.evidence.length ? selectedRun.evidence.map((evidence, index) => <details className="evidence-card" key={evidence.id} open={index === 0}><summary><span className="evidence-index">{index + 1}</span><span>{evidence.title}<small>v{evidence.version} · 片段 {evidence.chunk_index + 1}</small></span><Icon name="chevron" size={14} /></summary><p>{evidence.text}</p><code>{evidence.id}</code></details>) : <p className="empty-note">尚无检索片段。商品事实也可作为生成依据。</p>}</div>
        {selectedRun?.draft && <div className="inspector-section"><div className="section-label"><Icon name="check" size={15} /><span>商品事实声明</span><span className="muted">{selectedRun.draft.claims.length}</span></div>{selectedRun.draft.claims.length ? selectedRun.draft.claims.map((claim, index) => <details className="evidence-card claim-card" key={`${selectedRun.id}-claim-${index}`}><summary><span className="evidence-index">{index + 1}</span><span>{claim.text}<small>{claim.fact_ids.length} 项关联事实</small></span><Icon name="chevron" size={14} /></summary><div className="claim-facts">{claim.fact_ids.length ? claim.fact_ids.map((factId, factIndex) => { const fact = product?.facts.find(item => item.id === factId); return <div key={`${factId}-${factIndex}`} className={fact ? '' : 'missing-fact'}><strong>{fact ? `${fact.label}：${fact.value}` : '未找到引用的商品事实'}</strong><code>{factId}</code></div> }) : <p className="empty-note">这条声明未关联商品事实，发布前请人工核对。</p>}</div></details>) : <p className="empty-note">当前草稿未单独列出商品事实声明。</p>}</div>}
        <div className="inspector-section"><div className="section-label"><span>内容检查</span>{selectedRun?.draft && <span className={`check-tag ${selectedRun.validation.passed ? 'pass' : 'warn'}`}>{selectedRun.validation.passed ? '通过' : '待处理'}</span>}</div>{selectedRun?.validation.issues.length ? <ul className="validation-list">{selectedRun.validation.issues.map((issue, index) => <li className={issue.severity} key={`${issue.code}-${index}`}><strong>{issue.severity === 'error' ? '需修正' : '注意'} · {issue.code}</strong><p>{issue.message}</p></li>)}</ul> : <p className="empty-note">{selectedRun?.draft ? '当前规则未发现问题，发布前仍需人工检查。' : '生成草稿后，将核对格式、商品声明与引用。'}</p>}</div>
        {selectedRun && !running(selectedRun.status) && <div className="usage-card"><div><strong>{(selectedRun.usage.latency_ms / 1000).toFixed(1)}<small>s</small></strong><span>本次耗时</span></div><div><strong>{selectedRun.usage.total_calls}</strong><span>模型调用</span></div><div><strong>{(selectedRun.usage.input_tokens + selectedRun.usage.output_tokens).toLocaleString()}</strong><span>Tokens</span></div></div>}
        {selectedRun?.draft && !running(selectedRun.status) && <div className="inspector-section image-section"><div className="section-label"><Icon name="image" size={16} /><span>广告图片方案</span><span className="muted">最多 3 张</span></div><div className="image-options">{selectedRun.draft.image_prompts.map((prompt, index) => <label className={imageIndices.includes(index) ? 'checked' : ''} key={index}><input type="checkbox" checked={imageIndices.includes(index)} disabled={Boolean(activeImageJob) || generatingImages || (!imageIndices.includes(index) && imageIndices.length >= 3)} onChange={() => chooseImage(index)} /><span>{prompt.label}<small>{prompt.prompt}</small></span></label>)}</div>{config?.image_provider !== 'demo' && <p className="image-charge-note">确认后会调用图片服务，可能产生费用。</p>}<button className="primary-button image-confirm" disabled={!imageIndices.length || Boolean(activeImageJob) || generatingImages || !selectedRun.validation.passed} onClick={() => { void generateImages() }}><Icon name="image" size={16} />{generatingImages || activeImageJob ? '正在生成图片…' : `确认并生成 ${imageIndices.length} 张`}</button>{!selectedRun.validation.passed && <p className="empty-note">先修改文案中的校验错误，再确认图片方案。</p>}{imageJobs[selectedRun.id] && <ImageResults job={imageJobs[selectedRun.id]} />}</div>}
        {selectedRun && !running(selectedRun.status) && <div className="inspector-section feedback-section"><div className="section-label"><span>这次结果有用吗？</span>{feedbackSaved && <span className="check-tag pass">已记录</span>}</div><div className="rating-buttons" role="group" aria-label="结果评分">{[1, 2, 3, 4, 5].map(value => <button className={rating === value ? 'selected' : ''} onClick={() => { setRating(value); setFeedbackSaved(false) }} key={value} aria-label={`${value} 分`}>{value}</button>)}</div><textarea className="feedback-input" placeholder="哪些内容需要改善？（选填）" value={feedbackComment} maxLength={1000} aria-label="评价意见" onChange={event => { setFeedbackComment(event.target.value); setFeedbackSaved(false) }} /><label className="accepted-label"><input type="checkbox" checked={accepted} onChange={event => { setAccepted(event.target.checked); setFeedbackSaved(false) }} />我会采用这份结果</label><button className="secondary-button" disabled={feedbackSending || feedbackSaved} onClick={() => { void saveFeedback() }}>{feedbackSending ? '保存中…' : feedbackSaved ? '反馈已保存' : '提交反馈'}</button></div>}
        <button className="evaluation-card" onClick={() => { void evaluate() }} disabled={evaluating || loading}><span className="evaluation-symbol"><Icon name="chart" size={20} /></span><span><strong>{evaluating ? '正在运行离线评测…' : '运行离线评测'}</strong><small>固定测试集 · 无付费模型调用</small></span><Icon name="arrow" size={17} /></button>
      </aside>
    </main>
    {modal === 'product' && <ProductModal onClose={() => setModal(null)} onCreated={async next => { setProducts(current => [...current, next]); setModal(null); await newConversation(next.id) }} />}
    {modal === 'document' && product && <DocumentModal brandId={product.brand_id} onClose={() => setModal(null)} onCreated={next => { setDocuments(current => [...current, next]); setModal(null) }} />}
    {modal === 'evaluation' && <EvaluationModal report={report} busy={evaluating} onClose={() => setModal(null)} onRun={() => { void evaluate() }} />}
  </div>
}

function ImageResults({ job }: { job: ImageJob }) {
  return <div className="image-results">{running(job.status) && <p className="empty-note">图片任务已提交，完成后会自动显示。</p>}{job.status === 'partial' && <div className="inline-error">部分图片已完成，其余方案生成失败。可查看下方结果与错误记录。</div>}{job.error && <div className="inline-error">{job.error}</div>}{job.images.map((image, index) => <div key={`${image.url}-${index}`} className="generated-image"><a href={assetUrl(image.url)} target="_blank" rel="noreferrer"><img src={assetUrl(image.url)} alt={image.label} /><span>{image.label}<Icon name="arrow" size={14} /></span></a><small>{image.mode === 'demo' ? '演示排版 · 非 AI 生图' : '真实图片服务生成'}{image.product_preserved ? ' · 保留商品主体' : ''}</small>{image.warning && <p>{image.warning}</p>}</div>)}</div>
}
function Modal({ title, description, children, onClose, wide = false }: { title: string; description: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    function keyHandler(event: KeyboardEvent) {
      if (event.key === 'Escape') onCloseRef.current()
      if (event.key === 'Tab') {
        const focusable = contentRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href]')
        if (!focusable?.length) return
        const first = focusable[0]; const last = focusable[focusable.length - 1]
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', keyHandler)
    return () => { document.removeEventListener('keydown', keyHandler); previousFocus?.focus() }
  }, [])
  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><div ref={contentRef} className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby="modal-title"><button ref={closeRef} className="icon-button modal-close" onClick={onClose} aria-label="关闭对话框"><Icon name="close" size={20} /></button><div className="panel-eyebrow">ADCRAFT WORKSPACE</div><h2 id="modal-title">{title}</h2><p className="modal-description">{description}</p>{children}</div></div>
}
function ProductModal({ onClose, onCreated }: { onClose: () => void; onCreated: (product: Product) => Promise<void> }) {
  const [name, setName] = useState(''); const [category, setCategory] = useState(''); const [brandId, setBrandId] = useState('my-brand')
  const [description, setDescription] = useState(''); const [factsText, setFactsText] = useState(''); const [points, setPoints] = useState('')
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('')
    const lines = factsText.split('\n').filter(line => line.trim())
    if (!lines.length) { setError('请至少填写一项已确认的商品事实，例如：容量 = 400 mL。'); return }
    const facts = lines.map((line, index) => { const delimiter = line.indexOf('='); return { id: `fact-${index + 1}`, label: line.slice(0, delimiter).trim(), value: line.slice(delimiter + 1).trim() } })
    if (lines.some(line => !line.includes('=')) || facts.some(fact => !fact.label || !fact.value)) { setError('每行事实请使用「名称 = 数值」格式，例如：容量 = 400 mL'); return }
    setBusy(true)
    try { const next = await ai.createProduct({ name: name.trim(), category: category.trim(), brand_id: brandId.trim(), description: description.trim(), facts, selling_points: points.split('\n').map(point => point.trim()).filter(Boolean) }); await onCreated(next) }
    catch (reason) { setError(errorMessage(reason)) } finally { setBusy(false) }
  }
  return <Modal title="添加商品" description="准确填写商品规格。只有确认过的事实才适合成为宣传依据。" onClose={onClose}><form className="modal-form" onSubmit={event => { void submit(event) }}><label>商品名称<input value={name} required maxLength={100} onChange={event => setName(event.target.value)} placeholder="例如：400 mL 随行保温杯" /></label><div className="form-columns"><label>商品分类<input value={category} required maxLength={50} onChange={event => setCategory(event.target.value)} placeholder="例如：生活用品" /></label><label>品牌标识<input value={brandId} required maxLength={80} onChange={event => setBrandId(event.target.value)} /></label></div><label>商品说明<textarea rows={2} value={description} maxLength={2000} onChange={event => setDescription(event.target.value)} placeholder="描述商品及使用场景" /></label><label>商品事实<span className="field-hint">每行一项，格式：名称 = 数值</span><textarea rows={4} value={factsText} maxLength={5000} onChange={event => setFactsText(event.target.value)} placeholder={'容量 = 400 mL\n材质 = 304 不锈钢\n颜色 = 奶油白'} /></label><label>已确认卖点<span className="field-hint">每行一项，避免夸大宣传</span><textarea rows={2} value={points} maxLength={4000} onChange={event => setPoints(event.target.value)} placeholder={'轻便易携带\n可重复使用'} /></label>{error && <div className="inline-error" role="alert">{error}</div>}<div className="modal-actions"><button className="secondary-button" type="button" onClick={onClose} disabled={busy}>取消</button><button className="primary-button" disabled={busy} type="submit">{busy ? '添加中…' : '添加并开始创作'}<Icon name="arrow" size={16} /></button></div></form></Modal>
}
function DocumentModal({ brandId, onClose, onCreated }: { brandId: string; onClose: () => void; onCreated: (document: KnowledgeDocument) => void }) {
  const [title, setTitle] = useState(''); const [content, setContent] = useState(''); const [version, setVersion] = useState('1')
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function readFile(file?: File) {
    if (!file) return
    if (!/\.(txt|md)$/i.test(file.name)) { setError('目前支持 UTF-8 的 .txt 或 .md 文件。'); return }
    if (file.size > 1024 * 1024) { setError('资料文件请控制在 1 MB 以内。'); return }
    try {
      const text = await file.text()
      if (text.length > 30000) { setError('资料内容超过 30,000 个字符，请拆分为多份资料后再导入。'); return }
      setContent(text); if (!title) setTitle(file.name.replace(/\.[^.]+$/, '').slice(0, 150)); setError('')
    } catch { setError('无法读取文件，请直接粘贴资料内容。') }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true)
    try { onCreated(await ai.createDocument({ title: title.trim(), content: content.trim(), brand_id: brandId, version: version.trim(), source: 'manual' })) }
    catch (reason) { setError(errorMessage(reason)) } finally { setBusy(false) }
  }
  return <Modal title="导入品牌资料" description="资料会加入当前品牌的知识库，后续生成时检索相关内容。" onClose={onClose}><form className="modal-form" onSubmit={event => { void submit(event) }}><div className="form-columns"><label>资料标题<input required maxLength={150} value={title} onChange={event => setTitle(event.target.value)} placeholder="例如：品牌内容指南" /></label><label>版本<input required maxLength={30} value={version} onChange={event => setVersion(event.target.value)} /></label></div><label className="document-upload"><Icon name="file" size={20} /><span>选择 .txt / .md 文件，或在下方粘贴资料</span><input type="file" accept=".txt,.md" onChange={event => { void readFile(event.target.files?.[0]) }} /></label><label>资料内容<textarea rows={10} required maxLength={30000} value={content} onChange={event => setContent(event.target.value)} placeholder="品牌语气、目标用户、允许使用的表达、避免出现的承诺…" /></label><p className="empty-note">归属品牌：{brandId} · 导入后可在左侧删除资料</p>{error && <div className="inline-error" role="alert">{error}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose} disabled={busy}>取消</button><button type="submit" className="primary-button" disabled={busy}>{busy ? '导入中…' : '加入知识库'}<Icon name="plus" size={16} /></button></div></form></Modal>
}
function EvaluationModal({ report, busy, onClose, onRun }: { report: EvaluationReport | null; busy: boolean; onClose: () => void; onRun: () => void }) {
  const metricNames: Record<string, string> = { retrieval: '资料检索', validation: '内容校验', workflow: '任务流程' }
  return <Modal title="离线评测报告" description="固定测试集检验检索、格式校验和失败处理。演示评测不衡量真实模型生成质量，也不会调用付费模型。" wide onClose={onClose}>{report ? <><div className="report-metrics"><div><strong>{report.cases_total}</strong><span>测试样例</span></div><div><strong>{report.passed}</strong><span>通过样例</span></div><div><strong>{report.failed}</strong><span>失败样例</span></div><div><strong>{(report.pass_rate * 100).toFixed(0)}%</strong><span>离线测试通过率</span></div></div><div>{report.metrics.map(metric => <div className="report-metric-row" key={metric.name}><span>{metricNames[metric.name] || metric.name}</span><strong>{metric.passed} / {metric.total}<span className="muted"> · {(metric.value * 100).toFixed(0)}%</span></strong></div>)}</div><div className="report-table-wrap"><table className="report-table"><thead><tr><th>类别</th><th>测试输入与预期</th><th>结果</th></tr></thead><tbody>{report.cases.map(item => <tr key={item.id}><td>{metricNames[item.category] || item.category}<br /><small>{item.id}</small></td><td>{item.input}<details><summary>查看预期与实际结果</summary><pre>{JSON.stringify({ expected: item.expected, actual: item.actual }, null, 2)}</pre></details></td><td><span className={`check-tag ${item.passed ? 'pass' : 'warn'}`}>{item.passed ? '通过' : '失败'}</span></td></tr>)}</tbody></table></div><ul className="report-notes">{report.notes.map((note, index) => <li key={index}>{note}</li>)}</ul><details className="report-json"><summary>查看完整报告 JSON</summary><pre>{JSON.stringify(report, null, 2)}</pre></details><p className="empty-note">生成时间：{new Date(report.created_at).toLocaleString('zh-CN')} · 以报告的样本范围与测试定义为准。</p></> : <div className="inspector-empty"><Icon name="chart" size={30} /><p>还没有评测报告，运行后将展示逐项结果。</p></div>}<div className="modal-actions"><button className="secondary-button" onClick={onClose}>关闭</button><button className="primary-button" onClick={onRun} disabled={busy}><Icon name="refresh" size={16} />{busy ? '评测中…' : '运行离线评测'}</button></div></Modal>
}
