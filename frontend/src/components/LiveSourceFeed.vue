<script setup lang="ts">
import { ref } from 'vue'
import type { SourceItem } from '../api'

const props = withDefaults(defineProps<{
  items: SourceItem[]
  total: number
  highlighted?: number[]
  title?: string
  subtitle?: string
  emptyText?: string
  compact?: boolean
  taskNameMap?: Record<number, string>
}>(), {
  title: '实时舆情流',
  subtitle: '新采集内容会进入顶部，AI研判状态自动刷新',
  emptyText: '正在等待首轮持续监测结果，也可以通过 Excel 补充数据。',
  compact: false,
  taskNameMap: () => ({}),
})

const emit = defineEmits<{ open: [item: SourceItem] }>()
const mode = ref<'flow' | 'table'>('flow')
const sentimentText: Record<string, string> = { positive: '正面', neutral: '中性', negative: '负面' }
const riskText: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }
const statusText = (item: SourceItem) => item.analysis_status === 'analyzed'
  ? item.current_analysis
    ? `${sentimentText[item.current_analysis.sentiment]} · ${riskText[item.current_analysis.risk_level]}`
    : 'AI已研判'
  : item.analysis_status === 'analyzing'
    ? 'AI研判中'
    : item.analysis_status === 'failed'
      ? '研判异常'
      : '等待AI研判'
const formatNumber = (value = 0) => value >= 10000 ? `${(value / 10000).toFixed(1)}万` : value.toLocaleString()
const sourceLabel = (item: SourceItem) => item.current_analysis?.source === 'human' ? '人工修正' : item.analysis_status === 'analyzed' ? 'AI研判' : '待处理'
const platformClass = (p: string) => ({ 微博: 'weibo', 快手: 'kuaishou', bilibili: 'bilibili' } as Record<string, string>)[p] || 'other'
</script>

<template>
  <div :class="['data-panel live-feed-panel', { compact }]">
    <div class="panel-heading">
      <div><h3>{{ title }}</h3><p>{{ subtitle }}</p></div>
      <div v-if="!compact" class="view-switch"><button :class="{active:mode==='flow'}" @click="mode='flow'">流式视图</button><button :class="{active:mode==='table'}" @click="mode='table'">表格视图</button></div>
    </div>
    <div v-if="compact || mode === 'flow'" class="live-feed-list">
      <button v-for="item in items" :key="item.id" :class="['feed-card',{fresh:highlighted?.includes(item.id), compact}]" @click="emit('open', item)">
        <span :class="['platform-badge', platformClass(item.platform)]">{{ item.platform }}</span>
        <div class="feed-card-main">
          <div class="feed-title-line">
            <b>{{ item.title }}</b>
            <em v-if="taskNameMap[item.task_id]" class="task-tag">{{ taskNameMap[item.task_id] }}</em>
            <em v-else>{{ sourceLabel(item) }}</em>
          </div>
          <p v-if="!compact">{{ item.content }}</p>
          <div class="feed-meta-line">
            <small>{{ item.author }} · {{ item.publish_time ? new Date(item.publish_time).toLocaleString() : '时间未知' }}</small>
            <a v-if="item.source_url" :href="item.source_url" target="_blank" rel="noopener" class="source-link" @click.stop>原文 ↗</a>
          </div>
        </div>
        <div class="feed-metrics">
          <span>{{ formatNumber(item.view_count) }}<small>曝光</small></span>
          <span>{{ formatNumber(item.interaction_count) }}<small>互动</small></span>
          <span v-if="!compact">{{ formatNumber(item.comment_count) }}<small>评论</small></span>
        </div>
        <em v-if="!compact" :class="`judge-chip ${item.analysis_status} ${item.current_analysis?.risk_level || ''}`">{{ statusText(item) }}</em>
      </button>
      <div v-if="!items.length" class="empty-table">{{ emptyText }}</div>
    </div>
    <div v-else class="data-table">
      <div class="data-row head"><span>舆情信息</span><span>平台 / 时间</span><span>情感</span><span>风险</span><span>研判状态</span></div>
      <button v-for="item in items" :key="item.id" class="data-row" @click="emit('open', item)"><span><b>{{ item.title }}</b><small>{{ item.content.slice(0, 55) }}</small></span><span><b>{{ item.platform }}</b><small>{{ item.publish_time ? new Date(item.publish_time).toLocaleString() : '时间未知' }}</small></span><span><em v-if="item.current_analysis" :class="`sentiment ${item.current_analysis.sentiment}`">{{ {positive:'正面',neutral:'中性',negative:'负面'}[item.current_analysis.sentiment] }}</em><em v-else>—</em></span><span><em v-if="item.current_analysis" :class="`risk ${item.current_analysis.risk_level}`">{{ {low:'低风险',medium:'中风险',high:'高风险'}[item.current_analysis.risk_level] }}</em><em v-else>—</em></span><span><i :class="`judge ${item.analysis_status}`"></i>{{ statusText(item) }}</span></button>
      <div v-if="!items.length" class="empty-table">{{ emptyText }}</div>
    </div>
  </div>
</template>
