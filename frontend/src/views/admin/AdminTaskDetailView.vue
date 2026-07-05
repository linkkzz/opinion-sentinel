<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../../components/AppHeader.vue'
import CollectionStatusPanel from '../../components/CollectionStatusPanel.vue'
import LiveSourceFeed from '../../components/LiveSourceFeed.vue'
import TaskConfigModal from '../../components/TaskConfigModal.vue'
import { api, completeTask, deleteTask, getCollectionFeed, getCollectionStatus, getItems, getTask, reopenTask, type CollectionStatus, type SourceItem, type Task } from '../../api'
import { useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)
const task = ref<Task>()
const items = ref<SourceItem[]>([])
const feedItems = ref<SourceItem[]>([])
const collectionStatus = ref<CollectionStatus>()
const highlightedItems = ref<number[]>([])
const total = ref(0)
const selected = ref<SourceItem>()
const tab = ref<'data' | 'strategy' | 'report'>('data')
const excel = ref<File>()
const zip = ref<File>()
const busy = ref('')
const message = ref('')
const strategies = ref<any[]>([])
const reports = ref<any[]>([])
const reportStatus = ref<any>({ state: 'unavailable', reason: '' })
const eligibility = ref<any>()
const editContent = ref('')
const editKind = ref<'strategy' | 'report'>('strategy')
const editId = ref(0)
const showTaskConfig = ref(false)
const reviewOpen = ref(false)
const revision = reactive({ sentiment: 'neutral', risk_level: 'low', reason: '', topics: '', change_note: '' })
let timer: number | undefined
let stream: EventSource | undefined

const sentimentText: Record<string, string> = { positive: '正面', neutral: '中性', negative: '负面' }
const riskText: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }
const stateText = computed(() => ({ running: '正在研判', waiting: '等待新数据', paused: '已暂停', error: '运行异常', not_started: '尚未启动', stopped: '已停止' }[task.value?.analysis_state || ''] || '尚未启动'))
const collectionStateText = computed(() => ({ idle:'等待启动', queued:'排队中', collecting:'采集中', waiting:'等待下一轮', paused:'已暂停', error:'异常', stopped:'未启用', no_account:'无账号', disabled:'未启用', failed:'异常', running:'采集中', refreshing:'Cookie刷新中', expired:'需重新登录' }[collectionStatus.value?.state || task.value?.collection_state || 'idle'] || '等待启动'))
const collectionActive = computed(() => {
  const s = collectionStatus.value?.state || task.value?.collection_state
  return s === 'collecting' || s === 'running' || s === 'queued'
})
const selectedAnalysis = computed(() => selected.value?.current_analysis)
const completedStrategies = computed(() => strategies.value.filter(value => value.generation_status === 'completed'))
const generatingStrategy = computed(() => strategies.value.find(value => value.generation_status === 'generating'))
const failedStrategies = computed(() => strategies.value.filter(value => value.generation_status === 'failed'))
const completedReports = computed(() => reports.value.filter(value => value.generation_status === 'completed'))
const generatingReport = computed(() => reports.value.find(value => value.generation_status === 'generating'))
const failedReports = computed(() => reports.value.filter(value => value.generation_status === 'failed'))
const load = async () => {
  task.value = await getTask(id)
  const data = await getItems(id)
  items.value = data.items; total.value = data.total
  collectionStatus.value = await getCollectionStatus(id)
  const feed = await getCollectionFeed(id, 40)
  feedItems.value = feed.items
  if (task.value.analysis_state === 'error' && !message.value) {
    const failed = data.items.find(item => item.analysis_status === 'failed')
    message.value = `AI分析已暂停：${failed?.analysis_error || 'Ollama服务调用失败，请检查模型服务后重新启动分析'}`
  }
  strategies.value = (await api.get(`/tasks/${id}/strategies`)).data
  reports.value = (await api.get(`/tasks/${id}/reports`)).data
  reportStatus.value = (await api.get(`/tasks/${id}/reports/status`)).data
  eligibility.value = (await api.get(`/tasks/${id}/strategies/eligibility`)).data
}
const refreshCollection = async () => {
  collectionStatus.value = await getCollectionStatus(id)
  const feed = await getCollectionFeed(id, 40)
  feedItems.value = feed.items
}
const upload = async () => {
  if (!excel.value) return
  busy.value = 'upload'; message.value = ''
  const body = new FormData(); body.append('excel', excel.value); if (zip.value) body.append('media_zip', zip.value)
  try { const { data } = await api.post(`/tasks/${id}/import`, body); message.value = `成功导入 ${data.imported} 条，跳过 ${data.skipped} 条`; await load() }
  catch (e: any) { message.value = e.response?.data?.detail || '导入失败' }
  finally { busy.value = '' }
}
const toggleAnalysis = async () => {
  if (!task.value) return
  busy.value = 'analysis'
  const action = task.value.analysis_enabled ? 'stop' : 'start'
  try { await api.post(`/tasks/${id}/analysis/${action}`); await load() }
  catch (e: any) { message.value = e.response?.data?.detail || '操作失败' }
  finally { busy.value = '' }
}
const runCollectionNow = async () => {
  busy.value='collection'; message.value='';
  try {
    const { data } = await api.post(`/tasks/${id}/collection/run-now`);
    if (data.queued > 0) {
      message.value = '已触发采集，正在拉取数据…';
      await refreshCollection();
      setTimeout(() => refreshCollection(), 4000);
    } else {
      message.value = '暂无可采集平台，请在采集中心添加账号';
      await refreshCollection();
    }
  } catch(e:any) { message.value=e.response?.data?.detail || '触发采集失败' }
  finally { busy.value='' }
}
const pauseCollection = async () => { busy.value='collection'; message.value=''; try { await api.post(`/tasks/${id}/collection/pause`); await refreshCollection() } catch(e:any) { message.value=e.response?.data?.detail || '暂停监测失败' } finally { busy.value='' } }
const resumeCollection = async () => { busy.value='collection'; message.value=''; try { await api.post(`/tasks/${id}/collection/resume`); await refreshCollection() } catch(e:any) { message.value=e.response?.data?.detail || '恢复监测失败' } finally { busy.value='' } }
const saveRevision = async () => {
  if (!selected.value) return
  busy.value = 'revision'
  try {
    await api.put(`/items/${selected.value.id}/analysis`, { ...revision, topics: revision.topics.split(/[,，]+/).filter(Boolean) })
    reviewOpen.value = false; selected.value = undefined; await load()
  } catch (e: any) { message.value = e.response?.data?.detail || '保存失败' }
  finally { busy.value = '' }
}
const openRevision = (item: SourceItem) => {
  selected.value = item
  reviewOpen.value = false
  Object.assign(revision, { sentiment: item.current_analysis?.sentiment || 'neutral', risk_level: item.current_analysis?.risk_level || 'low', reason: item.current_analysis?.reason || '', topics: item.current_analysis?.topics.join('，') || '', change_note: '' })
}
const closeItem = () => { selected.value = undefined; reviewOpen.value = false }
const hasUsableSource = (url?: string) => Boolean(url && !url.includes('example.com'))
const analysisStatusText = (item: SourceItem) => item.analysis_status === 'analyzed'
  ? (item.current_analysis?.source === 'human' ? '人工已修正' : 'AI已研判')
  : item.analysis_status === 'analyzing'
    ? 'AI研判中'
    : item.analysis_status === 'failed'
      ? '研判异常'
      : '等待AI研判'
const analysisStatusHint = (item: SourceItem) => item.analysis_status === 'analyzed'
  ? '该内容已形成研判结论，可按需展开人工修正。'
  : item.analysis_status === 'analyzing'
    ? 'AI正在读取正文、互动量和任务上下文，完成后会自动刷新。'
    : item.analysis_status === 'failed'
      ? (item.analysis_error || 'AI研判失败，请检查模型服务或稍后重试。')
      : '新入库内容已进入待研判队列，启动AI分析后会自动生成情感、风险和依据。'
const formatNumber = (value = 0) => value.toLocaleString()
const generateStrategy = async () => { busy.value = 'strategy'; eligibility.value={state:'generating',eligible:false,reason:'应对策略正在生成中'}; try { await api.post(`/tasks/${id}/strategies`); await load() } catch (e: any) { message.value = e.response?.data?.detail || '生成失败'; await load() } finally { busy.value = '' } }
const complete = async () => { busy.value = 'complete'; try { await (task.value?.status === 'completed' ? reopenTask(id) : completeTask(id)); await load() } finally { busy.value = '' } }
const onDelete = async () => {
  if (!task.value || !confirm(`确定删除任务「${task.value.name}」？\n该任务的所有数据将一并删除，不可恢复。`)) return
  busy.value = 'delete'
  try { await deleteTask(id); router.push('/admin') }
  catch (e: any) { message.value = e.response?.data?.detail || '删除失败'; busy.value = '' }
}
const generateReport = async () => { busy.value = 'report'; reportStatus.value={state:'generating',reason:'任务报告正在生成中'}; try { await api.post(`/tasks/${id}/reports`); await load() } catch (e: any) { message.value = e.response?.data?.detail || '生成失败'; await load() } finally { busy.value = '' } }
const openEditor = (kind: 'strategy'|'report', value: any) => { editKind.value = kind; editId.value = value.id; editContent.value = value.content }
const saveEditor = async () => { await api.put(`/tasks/${id}/${editKind.value === 'strategy' ? 'strategies' : 'reports'}/${editId.value}`, { content: editContent.value }); editId.value = 0; await load() }
const connectStream = () => {
  stream?.close()
  stream = new EventSource(`/api/tasks/${id}/collection/stream`)
  stream.addEventListener('source_item.created', event => {
    const payload = JSON.parse((event as MessageEvent).data)
    const itemId = payload.payload?.item_id
    if (itemId) {
      highlightedItems.value = [itemId, ...highlightedItems.value].slice(0, 8)
      window.setTimeout(() => { highlightedItems.value = highlightedItems.value.filter(value => value !== itemId) }, 5000)
    }
    void refreshCollection()
  })
  stream.addEventListener('collection.status_changed', () => { void refreshCollection() })
  stream.addEventListener('collection.run_completed', () => { void refreshCollection() })
  stream.addEventListener('collection.run_failed', () => { void refreshCollection() })
  stream.onerror = () => {
    stream?.close()
    stream = undefined
    if (!stopped) setTimeout(() => { if (!stopped) connectStream() }, 3000)
  }
}
let stopped = false
onMounted(async () => { stopped = false; await load(); connectStream(); timer = window.setInterval(load, 5000) })
onBeforeUnmount(() => { stopped = true; window.clearInterval(timer); stream?.close() })
</script>

<template>
  <div class="admin-shell" v-if="task">
    <AppHeader mode="admin" :title="task.name" />
    <main class="admin-content detail-content">
      <div class="detail-hero">
        <router-link to="/admin" class="back">← 返回任务</router-link>
        <div class="detail-title"><div><div class="status-line"><span :class="['status-dot', task.status]"></span>{{ task.status === 'running' ? '任务进行中' : '任务已完结' }}</div><h1>{{ task.name }}</h1><div class="tag-row"><span v-for="k in task.keywords" :key="k"># {{ k }}</span></div></div>
          <div class="hero-actions">
            <button class="icon-btn" title="修改任务配置" @click="showTaskConfig=true"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg></button>
            <button class="icon-btn" :title="task.status === 'completed' ? '重新开启' : '完结任务'" @click="complete"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"></path><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg></button>
            <button class="icon-btn del" title="删除任务" :disabled="busy === 'delete'" @click="onDelete"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg></button>
          </div>
        </div>
        <div class="run-strip collection-run-strip"><div><span :class="['pulse', { idle: !collectionActive }]"></span><small>采集引擎</small><strong>{{ collectionStateText }}</strong></div><div><small>本轮新增</small><strong>{{ collectionStatus?.current_round_imported || 0 }}</strong></div><div><small>今日新增</small><strong>{{ collectionStatus?.today_imported || 0 }}</strong></div><div><small>AI研判引擎</small><strong>{{ stateText }}</strong></div><button :class="task.analysis_enabled ? 'danger' : 'primary'" :disabled="task.status === 'completed' || busy === 'analysis'" @click="toggleAnalysis">{{ task.analysis_enabled ? '暂停分析' : '启动AI分析' }}</button></div>
      </div>
      <div v-if="message" class="notice">{{ message }}<button @click="message = ''">×</button></div>
      <div class="tabs"><button :class="{ active: tab === 'data' }" @click="tab='data'">舆情数据 <b>{{ total }}</b></button><button :class="{ active: tab === 'strategy' }" @click="tab='strategy'">应对策略 <b>{{ strategies.length }}</b></button><button :class="{ active: tab === 'report' }" @click="tab='report'">任务报告 <b>{{ reports.length }}</b></button></div>

      <section v-if="tab === 'data'" class="workspace">
        <CollectionStatusPanel :status="collectionStatus" :busy="busy" @run-now="runCollectionNow" @pause="pauseCollection" @resume="resumeCollection"><div class="manual-import"><h4>Excel 补录</h4><p>用于微信公众号或线下补充数据。<a href="/api/import-template">下载模板</a></p><label class="file-drop"><b>{{ excel?.name || '选择 Excel 文件' }}</b><input type="file" accept=".xlsx" @change="excel = ($event.target as HTMLInputElement).files?.[0]"></label><label class="file-drop minor"><b>{{ zip?.name || '选择媒体 ZIP（可选）' }}</b><input type="file" accept=".zip" @change="zip = ($event.target as HTMLInputElement).files?.[0]"></label><button class="primary full" :disabled="!excel || busy === 'upload'" @click="upload">{{ busy === 'upload' ? '正在导入…' : '开始导入' }}</button><small>必填列：平台、正文</small></div></CollectionStatusPanel>
        <LiveSourceFeed :items="feedItems" :total="total" :highlighted="highlightedItems" @open="openRevision" />
      </section>

      <section v-if="tab === 'strategy'" class="strategy-view"><div class="section-action"><div><span class="eyebrow">AI RESPONSE STRATEGY</span><h2>智能应对策略</h2><p>{{ eligibility?.reason }}</p></div><button class="primary" :disabled="!eligibility?.eligible || busy === 'strategy'" @click="generateStrategy">{{ eligibility?.state === 'generating' || busy === 'strategy' ? '应对策略生成中…' : '生成新应对策略' }}</button></div><article v-if="generatingStrategy" class="document-card generating-document"><header><div><b>应对策略 V{{ generatingStrategy.version_no }}</b><span>AI生成中</span></div></header><div class="generation-progress"><i></i><strong>正在根据 {{ generatingStrategy.analyzed_count }} 条已研判数据生成应对策略</strong><small>记录已创建，生成完成后将在原记录上更新内容</small></div></article><article v-for="s in completedStrategies" :key="s.id" class="document-card"><header><div><b>应对策略 V{{ s.version_no }}</b><span>{{ s.is_manually_edited ? 'AI生成 · 人工已审核' : 'AI生成' }}</span></div><button @click="openEditor('strategy', s)">编辑应对策略</button></header><pre>{{ s.content }}</pre><footer>基于 {{ s.analyzed_count }} 条已研判数据 · {{ new Date(s.created_at).toLocaleString() }}</footer></article><article v-for="s in failedStrategies" :key="s.id" class="document-card failed-document"><header><div><b>应对策略 V{{ s.version_no }}</b><span>生成失败</span></div></header><p>{{ s.generation_error || '应对策略生成失败，可重新发起生成。' }}</p></article><div v-if="!strategies.length" class="empty-document">完成数据研判后，即可生成针对性的舆情应对策略。</div></section>

      <section v-if="tab === 'report'" class="strategy-view"><div class="section-action"><div><span class="eyebrow">ARCHIVE REPORT</span><h2>任务归档报告</h2><p>{{ reportStatus.reason || '任务完结后生成正式舆情分析报告并导出 PDF。' }}</p></div><button class="primary" :disabled="reportStatus.state !== 'available' || busy === 'report'" @click="generateReport">{{ reportStatus.state === 'generating' || busy === 'report' ? '报告生成中…' : reportStatus.state === 'ready' ? '报告已生成' : '生成任务报告' }}</button></div><article v-if="generatingReport" class="document-card generating-document"><header><div><b>任务报告 V{{ generatingReport.version_no }}</b><span>AI生成中</span></div></header><div class="generation-progress"><i></i><strong>AI正在撰写任务归档报告</strong><small>记录已创建，生成完成后将在原记录上更新内容</small></div></article><article v-for="r in completedReports" :key="r.id" class="document-card"><header><div><b>任务报告 V{{ r.version_no }}</b><span>{{ r.is_manually_edited ? 'AI生成 · 人工已审核' : 'AI生成' }}</span></div><div><button @click="openEditor('report', r)">编辑</button><a class="button-link" :href="`/api/tasks/${id}/reports/${r.id}/pdf`">导出 PDF</a></div></header><pre>{{ r.content }}</pre><footer>{{ new Date(r.created_at).toLocaleString() }}</footer></article><article v-for="r in failedReports" :key="r.id" class="document-card failed-document"><header><div><b>任务报告 V{{ r.version_no }}</b><span>生成失败</span></div></header><p>{{ r.generation_error || '任务报告生成失败，可重新发起生成。' }}</p></article><div v-if="!reports.length" class="empty-document">{{ task.status === 'completed' ? '点击上方按钮生成首份报告。' : '请先将任务设置为已完结。' }}</div></section>
    </main>

    <div v-if="selected" class="modal-mask" @click.self="closeItem">
      <div class="modal item-modal intel-modal">
        <div class="modal-head intel-modal-head">
          <div>
            <span class="eyebrow">情报详情</span>
            <h2>{{ selected.title }}</h2>
            <div class="item-meta">
              <span class="source-pill">{{ selected.platform }}</span>
              <span>{{ selected.author }}</span>
              <span>{{ selected.publish_time ? new Date(selected.publish_time).toLocaleString() : '时间未知' }}</span>
              <a v-if="hasUsableSource(selected.source_url)" :href="selected.source_url" target="_blank">打开原文</a>
            </div>
          </div>
          <button class="close" @click="closeItem">×</button>
        </div>

        <div class="intel-layout">
          <section class="intel-main">
            <p class="item-content">{{ selected.content }}</p>
            <div v-if="selected.media.length" class="media-grid">
              <template v-for="m in selected.media" :key="m.id">
                <img v-if="m.media_type === 'image'" :src="m.storage_path">
                <video v-else :src="m.storage_path" controls></video>
              </template>
            </div>
            <div class="analysis-card" :class="selected.analysis_status">
              <header>
                <span>研判状态</span>
                <b>{{ analysisStatusText(selected) }}</b>
              </header>
              <div v-if="selectedAnalysis" class="analysis-result">
                <div>
                  <small>情感倾向</small>
                  <em :class="`sentiment ${selectedAnalysis.sentiment}`">{{ sentimentText[selectedAnalysis.sentiment] }}</em>
                </div>
                <div>
                  <small>风险等级</small>
                  <em :class="`risk ${selectedAnalysis.risk_level}`">{{ riskText[selectedAnalysis.risk_level] }}</em>
                </div>
                <p>{{ selectedAnalysis.reason }}</p>
                <div v-if="selectedAnalysis.topics.length" class="analysis-topics">
                  <span v-for="topic in selectedAnalysis.topics" :key="topic">{{ topic }}</span>
                </div>
                <footer>{{ selectedAnalysis.source === 'human' ? '人工修正' : 'AI研判' }} · 第 {{ selectedAnalysis.revision_no }} 版</footer>
              </div>
              <p v-else>{{ analysisStatusHint(selected) }}</p>
            </div>
          </section>

          <aside class="intel-side">
            <div class="engagement-metrics compact-metrics">
              <span><b>{{ formatNumber(selected.view_count) }}</b><small>阅读/播放</small></span>
              <span><b>{{ formatNumber(selected.like_count) }}</b><small>点赞</small></span>
              <span><b>{{ formatNumber(selected.comment_count) }}</b><small>评论</small></span>
              <span><b>{{ formatNumber(selected.share_count) }}</b><small>转发/分享</small></span>
              <span><b>{{ formatNumber(selected.interaction_count) }}</b><small>互动总量</small></span>
            </div>
            <button class="review-toggle" @click="reviewOpen = !reviewOpen">
              {{ reviewOpen ? '收起人工修正' : selected.current_analysis ? '修正研判结论' : '补充人工研判' }}
            </button>
            <div v-if="reviewOpen" class="review-box review-box-open">
              <h3>人工研判</h3>
              <div class="form-row">
                <label>情感倾向<select v-model="revision.sentiment"><option value="positive">正面</option><option value="neutral">中性</option><option value="negative">负面</option></select></label>
                <label>风险等级<select v-model="revision.risk_level"><option value="low">低风险</option><option value="medium">中风险</option><option value="high">高风险</option></select></label>
              </div>
              <label>判断依据<textarea v-model="revision.reason" rows="4"></textarea></label>
              <label>主题标签<input v-model="revision.topics" placeholder="多个标签用逗号分隔"></label>
              <label>修改说明<input v-model="revision.change_note" required placeholder="说明本次人工调整原因"></label>
              <button class="primary full" :disabled="!revision.reason || !revision.change_note || busy === 'revision'" @click="saveRevision">保存人工研判</button>
            </div>
          </aside>
        </div>
      </div>
    </div>
    <div v-if="editId" class="modal-mask" @click.self="editId = 0"><div class="modal editor-modal"><div class="modal-head"><h2>编辑{{ editKind === 'strategy' ? '应对策略' : '任务报告' }}</h2><button class="close" @click="editId = 0">×</button></div><textarea v-model="editContent"></textarea><div class="modal-actions"><button @click="editId = 0">取消</button><button class="primary" @click="saveEditor">保存人工修订</button></div></div></div>
    <TaskConfigModal v-if="showTaskConfig" :task="task" @close="showTaskConfig=false" @saved="showTaskConfig=false; load()" />
  </div>
</template>
