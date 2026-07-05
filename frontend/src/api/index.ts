import axios from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 200000 })

export interface Task {
  id: number
  name: string
  keywords: string[]
  platforms: string[]
  start_time?: string
  end_time?: string
  description?: string
  status: 'running' | 'completed'
  analysis_enabled: boolean
  analysis_state: string
  collection_enabled: boolean
  collection_state: string
  collection_interval_seconds: number
  created_at: string
  updated_at: string
}

export interface Analysis {
  id: number
  revision_no: number
  sentiment: 'positive' | 'neutral' | 'negative'
  risk_level: 'low' | 'medium' | 'high'
  confidence?: number
  reason: string
  topics: string[]
  source: 'ai' | 'human'
}

export interface SourceItem {
  id: number
  task_id: number
  platform: string
  title: string
  author: string
  publish_time?: string
  content: string
  source_url?: string
  like_count: number
  comment_count: number
  share_count: number
  view_count: number
  interaction_count: number
  analysis_status: string
  analysis_error?: string
  current_analysis?: Analysis
  media: Array<{ id: number; media_type: 'image' | 'video'; original_name: string; storage_path: string }>
}

export interface CollectionRun {
  id: number
  task_id: number
  platform: string
  keyword: string
  status: string
  started_at?: string
  finished_at?: string
  imported_count: number
  skipped_count: number
  error_message?: string
  created_at: string
  updated_at: string
}

export interface CollectionPlatformStatus {
  platform: string
  state: string
  latest_run?: CollectionRun
  latest_success_at?: string
  next_run_at?: string
  imported_total: number
  skipped_total: number
  latest_imported: number
  error_message?: string
}

export interface CollectionStatus {
  task_id: number
  enabled: boolean
  state: string
  interval_seconds: number
  current_round_imported: number
  today_imported: number
  total_imported: number
  latest_success_at?: string
  next_run_at?: string
  platforms: CollectionPlatformStatus[]
}

export const getTasks = () => api.get<Task[]>('/tasks').then(r => r.data)
export const getTask = (id: number) => api.get<Task>(`/tasks/${id}`).then(r => r.data)
export const deleteTask = (id: number) => api.delete(`/tasks/${id}`)
export const completeTask = (id: number) => api.post<Task>(`/tasks/${id}/complete`).then(r => r.data)
export const reopenTask = (id: number) => api.post<Task>(`/tasks/${id}/reopen`).then(r => r.data)
export const pauseCollection = (id: number) => api.post(`/tasks/${id}/collection/pause`)
export const resumeCollection = (id: number) => api.post(`/tasks/${id}/collection/resume`)
export const runCollectionNow = (id: number) => api.post<{ queued: number; collection_state: string }>(`/tasks/${id}/collection/run-now`).then(r => r.data)
export const startAnalysis = (id: number) => api.post(`/tasks/${id}/analysis/start`)
export const stopAnalysis = (id: number) => api.post(`/tasks/${id}/analysis/stop`)
export const getItems = (id: number, pageSize = 100) =>
  api.get<{ total: number; items: SourceItem[] }>(`/tasks/${id}/items`, { params: { page_size: pageSize } }).then(r => r.data)
export const getCollectionStatus = (id: number) => api.get<CollectionStatus>(`/tasks/${id}/collection/status`).then(r => r.data)
export const getCollectionFeed = (id: number, pageSize = 30) =>
  api.get<{ total: number; items: SourceItem[] }>(`/tasks/${id}/collection/feed`, { params: { page_size: pageSize } }).then(r => r.data)
export const getGlobalCollectionFeed = (pageSize = 20) =>
  api.get<{ total: number; items: (SourceItem & { task_name?: string })[] }>(`/collection/feed`, { params: { page_size: pageSize } }).then(r => r.data)

export interface CollectionAccount {
  id: number
  platform: string
  status: string
  last_validated_at?: string
  validated_by?: string
  note?: string
  created_at: string
  updated_at: string
  has_cookie: boolean
}

export interface CollectionRecentRun {
  id: number
  status: string
  imported: number
  skipped: number
  keyword: string
  finished_at?: string
  error?: string
}

export interface CollectionAccountOverview {
  platform: string
  account_status: string
  account_count: number
  valid_count: number
  today_imported: number
  total_imported: number
  total_skipped: number
  last_success_at?: string
  recent_runs: CollectionRecentRun[]
}

export const getAccounts = () => api.get<CollectionAccount[]>('/collection/accounts').then(r => r.data)
export const getAccountsOverview = () => api.get<CollectionAccountOverview[]>('/collection/accounts/overview').then(r => r.data)
export const deleteAccount = (id: number) => api.delete(`/collection/accounts/${id}`)
export const validateAccount = (id: number) => api.post<{ valid: boolean }>(`/collection/accounts/${id}/validate`)
export const refreshAccount = (id: number) => api.post<{ refreshed: boolean }>(`/collection/accounts/${id}/refresh`)
