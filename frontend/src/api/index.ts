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

export const getTasks = () => api.get<Task[]>('/tasks').then(r => r.data)
export const getTask = (id: number) => api.get<Task>(`/tasks/${id}`).then(r => r.data)
export const getItems = (id: number, pageSize = 100) =>
  api.get<{ total: number; items: SourceItem[] }>(`/tasks/${id}/items`, { params: { page_size: pageSize } }).then(r => r.data)
