<script setup lang="ts">
import { computed } from 'vue'
import type { CollectionStatus } from '../api'

const props = defineProps<{ status?: CollectionStatus; busy?: string; message?: string }>()
const emit = defineEmits<{ runNow: []; pause: []; resume: [] }>()

const stateText: Record<string, string> = {
  idle: '等待启动',
  queued: '排队中',
  collecting: '采集中',
  waiting: '等待下一轮',
  paused: '已暂停',
  error: '异常',
  stopped: '未启用',
  running: '采集中',
  completed: '已完成',
  failed: '异常',
  unsupported: '暂未接入',
  no_account: '未接入账号',
  disabled: '未启用',
  refreshing: 'Cookie刷新中',
  expired: '需重新登录',
}

const engine = computed(() => {
  const s = props.status?.state || 'idle'
  if (s === 'collecting' || s === 'running') return { text: '正在采集', hint: '引擎正在拉取最新数据', cls: 'active' }
  if (s === 'queued') return { text: '排队中', hint: '等待采集引擎调度', cls: 'queued' }
  if (s === 'waiting') return { text: '等待下一轮', hint: nextRunHint.value, cls: 'waiting' }
  if (s === 'paused') return { text: '已暂停', hint: '点击恢复监测继续采集', cls: 'paused' }
  if (s === 'error' || s === 'failed') return { text: '采集异常', hint: '请检查账号或网络', cls: 'error' }
  if (s === 'stopped' || s === 'disabled') return { text: '未启用', hint: '点击立即采集启动监测', cls: 'idle' }
  return { text: '等待启动', hint: '点击立即采集启动监测', cls: 'idle' }
})

const nextRunHint = computed(() => {
  const next = props.status?.next_run_at
  if (!next) return '即将自动采集'
  const diff = new Date(next).getTime() - Date.now()
  if (diff <= 0) return '即将自动采集'
  if (diff < 60000) return `${Math.ceil(diff / 1000)} 秒后自动采集`
  return `${Math.ceil(diff / 60000)} 分钟后自动采集`
})

const isCollecting = computed(() => {
  const s = props.status?.state
  return s === 'collecting' || s === 'running' || s === 'queued'
})

const canPause = computed(() => props.status?.enabled && !isCollecting.value)

const formatTime = (value?: string) => value ? new Date(value).toLocaleString() : '暂无'
</script>

<template>
  <aside class="import-panel collection-panel">
    <span class="eyebrow">DATA ACCESS</span>
    <h3>数据接入中心</h3>
    <p>持续监测围绕当前任务的关键词和平台采集。</p>

    <!-- 引擎状态 -->
    <div :class="['engine-status', engine.cls]">
      <span class="engine-dot"></span>
      <div>
        <b>{{ engine.text }}</b>
        <small>{{ engine.hint }}</small>
      </div>
    </div>

    <!-- 数据指标 -->
    <div class="data-metrics">
      <div><b>{{ status?.today_imported || 0 }}</b><small>今日新增</small></div>
      <div><b>{{ status?.total_imported || 0 }}</b><small>累计入库</small></div>
      <div><b>{{ status?.current_round_imported || 0 }}</b><small>本轮新增</small></div>
    </div>

    <!-- 操作 -->
    <div class="collector-actions">
      <button class="primary" :disabled="busy==='collection'" @click="emit('runNow')">
        {{ isCollecting ? '采集中…' : '立即采集' }}
      </button>
      <button v-if="status?.state === 'paused'" :disabled="busy==='collection'" @click="emit('resume')">恢复监测</button>
      <button v-else :disabled="busy==='collection' || !canPause" @click="emit('pause')">暂停监测</button>
    </div>

    <!-- 平台状态 -->
    <div class="platform-status-list">
      <article v-for="p in status?.platforms || []" :key="p.platform" :class="['platform-status-card', p.state]">
        <header>
          <b>{{ p.platform }}</b>
          <em>{{ stateText[p.state] || p.state }}</em>
        </header>
        <div v-if="p.state !== 'no_account'">
          <span>累计入库</span><strong>{{ p.imported_total }}</strong>
        </div>
        <div v-if="p.state !== 'no_account'">
          <span>最近新增</span><strong>{{ p.latest_imported }}</strong>
        </div>
        <small v-if="p.state !== 'no_account'">最近成功：{{ formatTime(p.latest_success_at) }}</small>
        <p v-if="p.state === 'no_account'" class="hint-link">
          无可用采集账号，<router-link to="/admin/accounts">前往采集中心添加 →</router-link>
        </p>
        <p v-else-if="p.error_message" class="hint-err">{{ p.error_message }}</p>
      </article>
      <article v-if="!status?.platforms?.length" class="platform-status-card unsupported">
        <header><b>暂无平台</b><em>仅导入</em></header>
        <small>请在任务配置中选择微博、快手或 bilibili。</small>
      </article>
    </div>

    <slot />
  </aside>
</template>

<style scoped>
/* 引擎状态指示器 */
.engine-status {
  display: flex;
  align-items: center;
  gap: 10px;
  border-radius: 10px;
  padding: 13px 14px;
  margin: 14px 0 12px;
  border: 1px solid #dbe8f4;
  background: #f6fbff;
}
.engine-status.active { background: #eafaf4; border-color: #b8ebd4; }
.engine-status.queued, .engine-status.waiting { background: #eef5ff; border-color: #c5dcfa; }
.engine-status.paused, .engine-status.idle { background: #f7f8fb; border-color: #e0e6f0; }
.engine-status.error { background: #fff5f6; border-color: #ffd2d8; }

.engine-dot {
  width: 10px; height: 10px; border-radius: 50%;
  flex: none; background: #a7b4c5;
}
.engine-status.active .engine-dot {
  background: #20d5a4; box-shadow: 0 0 0 4px rgba(32,213,164,.18), 0 0 12px #20d5a4;
  animation: pulse 1.4s ease-in-out infinite;
}
.engine-status.queued .engine-dot, .engine-status.waiting .engine-dot { background: #219cff; }
.engine-status.error .engine-dot { background: #ef526b; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }

.engine-status b { display: block; font-size: 14px; color: #1c3f65; }
.engine-status small { display: block; font-size: 11px; color: #7890aa; margin-top: 2px; }

/* 数据指标 */
.data-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}
.data-metrics > div {
  text-align: center;
  background: #f8fbff;
  border: 1px solid #e6eef7;
  border-radius: 8px;
  padding: 10px 4px;
}
.data-metrics b { display: block; font-size: 18px; color: #1c7fd9; font-variant-numeric: tabular-nums; }
.data-metrics small { display: block; font-size: 10px; color: #8193aa; margin-top: 3px; }

/* 平台卡 */
.platform-status-card.no_account { border-color: #ffd2d8; background: #fff8f9; }
.platform-status-card.no_account header em { color: #d83d58; background: #ffeaf0; }
.platform-status-card.refreshing { border-color: #ffe4b8; background: #fffbf3; }
.platform-status-card.refreshing header em { color: #d48516; background: #fff2dc; }
.platform-status-card.expired { border-color: #ffd2d8; background: #fff8f9; }
.platform-status-card.expired header em { color: #d83d58; background: #ffeaf0; }
.hint-link {
  font-size: 11px; color: #c23b52; line-height: 1.5; margin: 8px 0 0;
}
.hint-link a { color: #1683e9; font-weight: 500; }
.hint-err {
  font-size: 11px; color: #c23b52; background: #fff0f3;
  border-radius: 7px; padding: 8px; line-height: 1.5; margin: 8px 0 0;
}
</style>
