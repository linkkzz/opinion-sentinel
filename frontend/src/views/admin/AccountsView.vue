<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import QrLoginModal from '../../components/QrLoginModal.vue'
import {
  deleteAccount,
  getAccounts,
  getAccountsOverview,
  getGlobalCollectionFeed,
  refreshAccount,
  validateAccount,
  type CollectionAccount,
  type CollectionAccountOverview,
  type SourceItem,
} from '../../api'

const accounts = ref<CollectionAccount[]>([])
const overviews = ref<CollectionAccountOverview[]>([])
const feedItems = ref<SourceItem[]>([])
const feedTotal = ref(0)
const feedTaskNames = ref<Record<number, string>>({})
const showLogin = ref<string | null>(null)
const busy = ref('')
const toast = ref('')
const loading = ref(true)
let timer: number | undefined

const alertPlatforms = computed(() =>
  overviews.value.filter(o => o.account_status === 'expired' || o.account_status === 'pending_refresh')
)
const hasAlert = computed(() => alertPlatforms.value.length > 0)
const todayTotal = computed(() => overviews.value.reduce((s, o) => s + o.today_imported, 0))
const validAccounts = computed(() => overviews.value.reduce((s, o) => s + o.valid_count, 0))
const totalAccounts = computed(() => overviews.value.reduce((s, o) => s + o.account_count, 0))
const engineText = computed(() => {
  if (hasAlert.value) return '账号异常'
  if (validAccounts.value === 0) return '等待接入'
  return '运行中'
})
const engineColor = computed(() => hasAlert.value ? '#f53f3f' : (validAccounts.value > 0 ? '#00b42a' : '#86909c'))

const showToast = (msg: string) => { toast.value = msg; setTimeout(() => { if (toast.value === msg) toast.value = '' }, 3000) }

const formatNum = (v: number) => v >= 10000 ? `${(v / 10000).toFixed(1)}万` : v.toLocaleString()
const formatTime = (v?: string) => {
  if (!v) return '—'
  const diff = Date.now() - new Date(v).getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return new Date(v).toLocaleDateString()
}
const platformDotClass = (p: string) => ({ 微博: 'weibo', 快手: 'kuaishou', bilibili: 'bilibili' } as Record<string, string>)[p] || 'other'
const stateText: Record<string, string> = { valid: '正常', pending_refresh: '刷新中', expired: '需登录', none: '未接入', login_pending: '登录中' }
const stateClass: Record<string, string> = { valid: 'ok', pending_refresh: 'warn', expired: 'err', none: 'idle', login_pending: 'warn' }
const isAlert = (s: string) => s === 'expired' || s === 'pending_refresh'

const load = async () => {
  try {
    const [acc, ov, feed] = await Promise.all([getAccounts(), getAccountsOverview(), getGlobalCollectionFeed(20)])
    accounts.value = acc
    overviews.value = ov
    feedItems.value = feed.items
    feedTotal.value = feed.total
    feedTaskNames.value = {}
    feed.items.forEach(i => { if (i.task_name) feedTaskNames.value[i.task_id] = i.task_name })
  } catch (e: any) {
    showToast(e.response?.data?.detail || '加载失败')
  } finally { loading.value = false }
}

const onAdd = (platform: string) => { showLogin.value = platform }
const onLoginSuccess = () => { showLogin.value = null; showToast('账号添加成功'); load() }

const onValidate = async (id: number) => {
  busy.value = 'validate'
  try {
    const { data } = await validateAccount(id)
    showToast(data.valid ? 'Cookie 有效' : 'Cookie 已失效，已标记刷新')
    await load()
  } catch { showToast('校验失败') }
  finally { busy.value = '' }
}

const onRefresh = async (id: number) => {
  busy.value = 'refresh'
  showToast('正在刷新 Cookie…')
  try {
    const { data } = await refreshAccount(id)
    showToast(data.refreshed ? 'Cookie 刷新成功' : 'SSO 已过期，需重新扫码登录')
    await load()
  } catch { showToast('刷新失败') }
  finally { busy.value = '' }
}

const onDelete = async (id: number) => {
  if (!confirm('确定删除该采集账号？')) return
  try { await deleteAccount(id); showToast('账号已删除'); await load() }
  catch { showToast('删除失败') }
}

onMounted(() => { load(); timer = window.setInterval(load, 8000) })
onBeforeUnmount(() => { if (timer) window.clearInterval(timer) })
</script>

<template>
  <div class="cc-page">
    <!-- 极简顶栏 -->
    <header class="cc-topbar">
      <div class="cc-topbar-inner">
        <router-link to="/admin" class="cc-brand">
          <span class="cc-brand-mark"></span>
          <span class="cc-brand-name">舆情智析</span>
          <span class="cc-brand-sep">/</span>
          <span class="cc-brand-current">采集中心</span>
        </router-link>
        <div class="cc-topbar-actions">
          <button class="cc-act" @click="load">刷新</button>
          <button class="cc-act" @click="onAdd('微博')"><span class="dot weibo"></span>添加微博</button>
          <button class="cc-act" @click="onAdd('快手')"><span class="dot kuaishou"></span>添加快手</button>
          <button class="cc-act" @click="onAdd('bilibili')"><span class="dot bilibili"></span>添加bilibili</button>
        </div>
      </div>
    </header>

    <!-- 主内容 -->
    <main class="cc-main">
      <div v-if="loading" class="cc-loading">加载中…</div>

      <template v-else>
        <!-- 标题 + 摘要 -->
        <div class="cc-hero">
          <h1>采集中心</h1>
          <p class="cc-hero-sub">管理微博、快手、bilibili 采集账号，查看最新入库内容。</p>
          <div class="cc-summary">
            <span><b>{{ validAccounts }}</b><small>/{{ totalAccounts }} 可用账号</small></span>
            <em class="cc-sep">·</em>
            <span><b :style="`color:${engineColor}`">{{ engineText }}</b></span>
            <em class="cc-sep">·</em>
            <span><b>{{ todayTotal }}</b><small> 今日入库</small></span>
          </div>
        </div>

        <!-- 风控告警 -->
        <div v-if="hasAlert" class="cc-alert">
          <span class="cc-alert-dot"></span>
          {{ alertPlatforms.map(p => p.platform).join('、') }} 账号 Cookie 异常，采集可能已暂停。系统正在自动刷新，若长时间未恢复请重新扫码登录。
        </div>

        <!-- 平台账号 -->
        <section class="cc-section">
          <h2 class="cc-section-title">平台账号</h2>
          <div class="cc-platform-list">
            <div v-for="ov in overviews" :key="ov.platform" :class="['cc-plat', { alert: isAlert(ov.account_status) }]">
              <div class="cc-plat-head">
                <span :class="['cc-plat-dot', platformDotClass(ov.platform)]"></span>
                <span class="cc-plat-name">{{ ov.platform }}</span>
                <span :class="['cc-plat-state', stateClass[ov.account_status]]">{{ stateText[ov.account_status] }}</span>
                <span class="cc-plat-meta">{{ ov.valid_count }}/{{ ov.account_count }} 可用 · 最近成功 {{ formatTime(ov.last_success_at) }}</span>
                <button class="cc-text-btn" @click="onAdd(ov.platform)">+ 添加</button>
              </div>
              <div v-if="accounts.filter(a => a.platform === ov.platform).length" class="cc-plat-accounts">
                <div v-for="acc in accounts.filter(a => a.platform === ov.platform)" :key="acc.id" class="cc-acc-row">
                  <span :class="['cc-acc-dot', acc.status]"></span>
                  <span class="cc-acc-name">{{ acc.note || `账号 #${acc.id}` }}</span>
                  <span class="cc-acc-time">校验 {{ formatTime(acc.last_validated_at) }}</span>
                  <div class="cc-acc-actions">
                    <button class="cc-text-btn sm" :disabled="busy !== ''" @click="onValidate(acc.id)">校验</button>
                    <button class="cc-text-btn sm" :disabled="busy !== ''" @click="onRefresh(acc.id)">刷新</button>
                    <button class="cc-text-btn sm danger" :disabled="busy !== ''" @click="onDelete(acc.id)">删除</button>
                  </div>
                </div>
              </div>
              <div v-else class="cc-plat-empty">
                暂无{{ ov.platform }}采集账号
                <button class="cc-text-btn" @click="onAdd(ov.platform)">扫码登录 →</button>
              </div>
            </div>
          </div>
        </section>

        <!-- 最新入库 -->
        <section class="cc-section">
          <div class="cc-section-head">
            <h2 class="cc-section-title">最新入库</h2>
            <small class="cc-section-sub">共 {{ feedTotal }} 条</small>
          </div>
          <div class="cc-feed">
            <button v-for="item in feedItems" :key="item.id" class="cc-feed-row">
              <span :class="['cc-feed-dot', platformDotClass(item.platform)]"></span>
              <span class="cc-feed-platform">{{ item.platform }}</span>
              <div class="cc-feed-content">
                <b class="cc-feed-title">{{ item.title }}</b>
                <div class="cc-feed-meta-row">
                  <small class="cc-feed-meta">{{ item.author }}<template v-if="feedTaskNames[item.task_id]"> · {{ feedTaskNames[item.task_id] }}</template></small>
                  <a v-if="item.source_url" :href="item.source_url" target="_blank" rel="noopener" class="cc-feed-link" @click.stop>原文 ↗</a>
                </div>
              </div>
              <div class="cc-feed-stats">
                <span v-if="item.view_count">{{ formatNum(item.view_count) }}<small>曝光</small></span>
                <span>{{ formatNum(item.interaction_count) }}<small>互动</small></span>
                <small class="cc-feed-time">{{ item.publish_time ? new Date(item.publish_time).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '' }}</small>
              </div>
            </button>
            <div v-if="!feedItems.length" class="cc-feed-empty">
              等待运行中任务采集首批内容。
            </div>
          </div>
        </section>
      </template>
    </main>

    <transition name="toast">
      <div v-if="toast" class="floating-toast">{{ toast }}</div>
    </transition>

    <QrLoginModal
      v-if="showLogin"
      :platform="showLogin"
      @close="showLogin = null"
      @success="onLoginSuccess"
    />
  </div>
</template>

<style scoped>
.cc-page { min-height: 100vh; background: #f7f8fa; }

/* 顶栏 */
.cc-topbar {
  position: sticky; top: 0; z-index: 50;
  background: rgba(255,255,255,0.85); backdrop-filter: blur(12px);
  border-bottom: 1px solid #e5e6eb;
}
.cc-topbar-inner {
  max-width: 1000px; margin: 0 auto; height: 52px; padding: 0 32px;
  display: flex; align-items: center; justify-content: space-between;
}
.cc-brand { display: flex; align-items: center; gap: 8px; font-size: 14px; color: #1d2129; text-decoration: none; }
.cc-brand-mark { width: 18px; height: 18px; border-radius: 5px; background: linear-gradient(135deg,#4080ff,#165dff); flex: none; }
.cc-brand-name { font-weight: 600; }
.cc-brand-sep { color: #c9cdd4; margin: 0 2px; }
.cc-brand-current { color: #4e5969; font-weight: 500; }
.cc-topbar-actions { display: flex; gap: 8px; align-items: center; }
.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; margin-right: 5px; vertical-align: middle; }
.dot.weibo { background: #ff7d00; }
.dot.kuaishou { background: #f53f3f; }
.dot.bilibili { background: #00a1d6; }

/* 按钮：圆角文字按钮，非方块 */
.cc-act {
  height: 32px; padding: 0 14px; border-radius: 16px;
  border: 1px solid #e5e6eb; background: #fff; color: #4e5969;
  font-size: 13px; cursor: pointer; transition: all 0.15s;
  display: inline-flex; align-items: center;
}
.cc-act:hover { border-color: #4080ff; color: #4080ff; background: #f2f7ff; }
.cc-text-btn {
  border: 0; background: transparent; color: #4080ff; font-size: 13px;
  cursor: pointer; padding: 4px 8px; border-radius: 4px; transition: background 0.15s;
}
.cc-text-btn:hover { background: #f2f7ff; }
.cc-text-btn.sm { font-size: 12px; padding: 2px 6px; }
.cc-text-btn.danger { color: #f53f3f; }
.cc-text-btn.danger:hover { background: #fff2f0; }
.cc-text-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* 主内容 */
.cc-main { max-width: 1000px; margin: 0 auto; padding: 48px 32px 80px; }
.cc-loading { text-align: center; padding: 120px 0; color: #86909c; font-size: 14px; }

/* 标题区 */
.cc-hero { margin-bottom: 40px; }
.cc-hero h1 { font-size: 24px; font-weight: 600; color: #1d2129; margin: 0 0 6px; letter-spacing: -0.3px; }
.cc-hero-sub { font-size: 14px; color: #86909c; margin: 0 0 16px; }
.cc-summary { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: #86909c; }
.cc-summary b { font-size: 15px; font-weight: 600; color: #1d2129; font-variant-numeric: tabular-nums; }
.cc-summary small { font-size: 12px; color: #a9aeb8; }
.cc-sep { color: #e5e6eb; font-style: normal; }

/* 告警 */
.cc-alert {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background: #fff2f0; border: 1px solid #ffd4cd;
  border-radius: 8px; font-size: 13px; color: #cb2634; margin-bottom: 32px;
}
.cc-alert-dot { width: 6px; height: 6px; border-radius: 50%; background: #f53f3f; flex: none; }

/* 区块 */
.cc-section { margin-bottom: 40px; }
.cc-section-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 16px; }
.cc-section-title { font-size: 15px; font-weight: 600; color: #1d2129; margin: 0 0 16px; }
.cc-section-sub { font-size: 12px; color: #a9aeb8; }

/* 平台卡 */
.cc-plat { background: #fff; border: 1px solid #e5e6eb; border-radius: 10px; overflow: hidden; margin-bottom: 10px; }
.cc-plat.alert { border-color: #ffd4cd; }
.cc-plat-head { display: flex; align-items: center; gap: 8px; padding: 12px 16px; }
.cc-plat-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.cc-plat-dot.weibo { background: #ff7d00; }
.cc-plat-dot.kuaishou { background: #f53f3f; }
.cc-plat-dot.bilibili { background: #00a1d6; }
.cc-plat-name { font-size: 14px; font-weight: 600; color: #1d2129; }
.cc-plat-state { font-size: 11px; font-weight: 500; padding: 1px 7px; border-radius: 4px; flex: none; }
.cc-plat-state.ok { color: #00b42a; background: #e8ffea; }
.cc-plat-state.warn { color: #ff7d00; background: #fff7e8; }
.cc-plat-state.err { color: #f53f3f; background: #ffece8; }
.cc-plat-state.idle { color: #86909c; background: #f2f3f5; }
.cc-plat-meta { font-size: 12px; color: #86909c; margin-left: auto; margin-right: 8px; }
.cc-plat-accounts { border-top: 1px solid #f2f3f5; }
.cc-acc-row { display: flex; align-items: center; gap: 8px; padding: 10px 16px; border-bottom: 1px solid #f7f8fa; }
.cc-acc-row:last-child { border-bottom: 0; }
.cc-acc-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.cc-acc-dot.valid { background: #00b42a; }
.cc-acc-dot.pending_refresh { background: #ff7d00; }
.cc-acc-dot.expired { background: #f53f3f; }
.cc-acc-dot.login_pending { background: #4080ff; }
.cc-acc-name { font-size: 13px; font-weight: 500; color: #1d2129; }
.cc-acc-time { font-size: 12px; color: #a9aeb8; margin-left: auto; margin-right: 8px; }
.cc-acc-actions { display: flex; gap: 2px; }
.cc-plat-empty { padding: 14px 16px; font-size: 13px; color: #a9aeb8; display: flex; align-items: center; gap: 4px; }

/* Feed 列表 */
.cc-feed { background: #fff; border: 1px solid #e5e6eb; border-radius: 10px; overflow: hidden; }
.cc-feed-row {
  display: grid; grid-template-columns: auto 36px minmax(0,1fr) auto; gap: 10px; align-items: center;
  width: 100%; padding: 12px 16px; border: 0; border-bottom: 1px solid #f2f3f5;
  background: transparent; text-align: left; cursor: pointer; transition: background 0.12s;
}
.cc-feed-row:last-child { border-bottom: 0; }
.cc-feed-row:hover { background: #f7f8fa; }
.cc-feed-dot { width: 6px; height: 6px; border-radius: 50%; flex: none; }
.cc-feed-dot.weibo { background: #ff7d00; }
.cc-feed-dot.kuaishou { background: #f53f3f; }
.cc-feed-dot.bilibili { background: #00a1d6; }
.cc-feed-dot.other { background: #86909c; }
.cc-feed-platform { font-size: 12px; color: #86909c; flex: none; }
.cc-feed-content { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.cc-feed-title { font-size: 13px; font-weight: 500; color: #1d2129; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cc-feed-meta { font-size: 12px; color: #a9aeb8; }
.cc-feed-meta-row { display: flex; align-items: center; gap: 8px; }
.cc-feed-link { font-size: 11px; color: #4080ff; text-decoration: none; }
.cc-feed-link:hover { text-decoration: underline; }
.cc-feed-stats { display: flex; align-items: center; gap: 12px; flex: none; }
.cc-feed-stats > span { font-size: 12px; color: #86909c; font-variant-numeric: tabular-nums; display: flex; flex-direction: column; align-items: flex-end; gap: 1px; }
.cc-feed-stats > span small { font-size: 10px; color: #c9cdd4; }
.cc-feed-time { font-size: 11px; color: #c9cdd4; }
.cc-feed-empty { padding: 48px 16px; text-align: center; font-size: 13px; color: #a9aeb8; }

/* toast */
.floating-toast {
  position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
  background: rgba(31,41,55,0.92); color: #fff; padding: 10px 20px;
  border-radius: 8px; font-size: 13px; z-index: 9999; box-shadow: 0 8px 24px rgba(0,0,0,0.18);
}
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 8px); }
</style>
