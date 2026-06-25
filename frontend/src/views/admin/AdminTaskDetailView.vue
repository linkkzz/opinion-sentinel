<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../../components/AppHeader.vue'
import TaskConfigModal from '../../components/TaskConfigModal.vue'
import { api, getItems, getTask, type SourceItem, type Task } from '../../api'

const route = useRoute()
const id = Number(route.params.id)
const task = ref<Task>()
const items = ref<SourceItem[]>([])
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
const revision = reactive({ sentiment: 'neutral', risk_level: 'low', reason: '', topics: '', change_note: '' })
let timer: number | undefined

const stateText = computed(() => ({ running: '正在研判', waiting: '等待新数据', paused: '已暂停', error: '运行异常', not_started: '尚未启动', stopped: '已停止' }[task.value?.analysis_state || ''] || '尚未启动'))
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
  if (task.value.analysis_state === 'error' && !message.value) {
    const failed = data.items.find(item => item.analysis_status === 'failed')
    message.value = `AI分析已暂停：${failed?.analysis_error || 'Ollama服务调用失败，请检查模型服务后重新启动分析'}`
  }
  strategies.value = (await api.get(`/tasks/${id}/strategies`)).data
  reports.value = (await api.get(`/tasks/${id}/reports`)).data
  reportStatus.value = (await api.get(`/tasks/${id}/reports/status`)).data
  eligibility.value = (await api.get(`/tasks/${id}/strategies/eligibility`)).data
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
const saveRevision = async () => {
  if (!selected.value) return
  busy.value = 'revision'
  try {
    await api.put(`/items/${selected.value.id}/analysis`, { ...revision, topics: revision.topics.split(/[,，]+/).filter(Boolean) })
    selected.value = undefined; await load()
  } catch (e: any) { message.value = e.response?.data?.detail || '保存失败' }
  finally { busy.value = '' }
}
const openRevision = (item: SourceItem) => {
  selected.value = item
  Object.assign(revision, { sentiment: item.current_analysis?.sentiment || 'neutral', risk_level: item.current_analysis?.risk_level || 'low', reason: item.current_analysis?.reason || '', topics: item.current_analysis?.topics.join('，') || '', change_note: '' })
}
const generateStrategy = async () => { busy.value = 'strategy'; eligibility.value={state:'generating',eligible:false,reason:'应对策略正在生成中'}; try { await api.post(`/tasks/${id}/strategies`); await load() } catch (e: any) { message.value = e.response?.data?.detail || '生成失败'; await load() } finally { busy.value = '' } }
const complete = async () => { busy.value = 'complete'; try { await api.post(`/tasks/${id}/${task.value?.status === 'completed' ? 'reopen' : 'complete'}`); await load() } finally { busy.value = '' } }
const generateReport = async () => { busy.value = 'report'; reportStatus.value={state:'generating',reason:'任务报告正在生成中'}; try { await api.post(`/tasks/${id}/reports`); await load() } catch (e: any) { message.value = e.response?.data?.detail || '生成失败'; await load() } finally { busy.value = '' } }
const openEditor = (kind: 'strategy'|'report', value: any) => { editKind.value = kind; editId.value = value.id; editContent.value = value.content }
const saveEditor = async () => { await api.put(`/tasks/${id}/${editKind.value === 'strategy' ? 'strategies' : 'reports'}/${editId.value}`, { content: editContent.value }); editId.value = 0; await load() }
onMounted(async () => { await load(); timer = window.setInterval(load, 5000) })
onBeforeUnmount(() => window.clearInterval(timer))
</script>

<template>
  <div class="admin-shell" v-if="task">
    <AppHeader mode="admin" :title="task.name" />
    <main class="admin-content detail-content">
      <div class="detail-hero">
        <router-link to="/admin" class="back">← 返回任务</router-link>
        <div class="detail-title"><div><div class="status-line"><span :class="['status-dot', task.status]"></span>{{ task.status === 'running' ? '任务进行中' : '任务已完结' }}</div><h1>{{ task.name }}</h1><div class="tag-row"><span v-for="k in task.keywords" :key="k"># {{ k }}</span></div></div>
          <div class="hero-actions"><button @click="showTaskConfig=true">修改任务配置</button><button @click="complete">{{ task.status === 'completed' ? '重新开启' : '完结任务' }}</button></div>
        </div>
        <div class="run-strip"><div><span class="pulse"></span><small>AI研判引擎</small><strong>{{ stateText }}</strong></div><div><small>数据总量</small><strong>{{ total }}</strong></div><div><small>已完成研判</small><strong>{{ items.filter(x => x.analysis_status === 'analyzed').length }}</strong></div><button :class="task.analysis_enabled ? 'danger' : 'primary'" :disabled="task.status === 'completed' || busy === 'analysis'" @click="toggleAnalysis">{{ task.analysis_enabled ? '暂停分析' : '启动AI分析' }}</button></div>
      </div>
      <div v-if="message" class="notice">{{ message }}<button @click="message = ''">×</button></div>
      <div class="tabs"><button :class="{ active: tab === 'data' }" @click="tab='data'">舆情数据 <b>{{ total }}</b></button><button :class="{ active: tab === 'strategy' }" @click="tab='strategy'">应对策略 <b>{{ strategies.length }}</b></button><button :class="{ active: tab === 'report' }" @click="tab='report'">任务报告 <b>{{ reports.length }}</b></button></div>

      <section v-if="tab === 'data'" class="workspace">
        <aside class="import-panel"><span class="eyebrow">DATA INGESTION</span><h3>导入舆情数据</h3><p>使用标准 Excel 模板，媒体文件可通过 ZIP 包一并导入。<a href="/api/import-template">下载模板</a></p><label class="file-drop">📄<b>{{ excel?.name || '选择 Excel 文件' }}</b><input type="file" accept=".xlsx" @change="excel = ($event.target as HTMLInputElement).files?.[0]"></label><label class="file-drop minor">▧<b>{{ zip?.name || '选择媒体 ZIP（可选）' }}</b><input type="file" accept=".zip" @change="zip = ($event.target as HTMLInputElement).files?.[0]"></label><button class="primary full" :disabled="!excel || busy === 'upload'" @click="upload">{{ busy === 'upload' ? '正在导入…' : '开始导入' }}</button><small>必填列：平台、正文</small></aside>
        <div class="data-panel"><div class="panel-heading"><div><h3>数据研判台</h3><p>点击任意数据查看详情并进行人工修正</p></div><span class="live"><i></i> LIVE</span></div><div class="data-table"><div class="data-row head"><span>舆情信息</span><span>平台 / 时间</span><span>情感</span><span>风险</span><span>研判状态</span></div><button v-for="item in items" :key="item.id" class="data-row" @click="openRevision(item)"><span><b>{{ item.title }}</b><small>{{ item.content.slice(0, 55) }}</small></span><span><b>{{ item.platform }}</b><small>{{ item.publish_time ? new Date(item.publish_time).toLocaleString() : '时间未知' }}</small></span><span><em v-if="item.current_analysis" :class="`sentiment ${item.current_analysis.sentiment}`">{{ {positive:'正面',neutral:'中性',negative:'负面'}[item.current_analysis.sentiment] }}</em><em v-else>—</em></span><span><em v-if="item.current_analysis" :class="`risk ${item.current_analysis.risk_level}`">{{ {low:'低风险',medium:'中风险',high:'高风险'}[item.current_analysis.risk_level] }}</em><em v-else>—</em></span><span><i :class="`judge ${item.analysis_status}`"></i>{{ item.analysis_status === 'analyzed' ? (item.current_analysis?.source === 'human' ? '人工修正' : 'AI已研判') : item.analysis_status === 'analyzing' ? '分析中' : item.analysis_status === 'failed' ? '分析异常' : '未研判' }}</span></button><div v-if="!items.length" class="empty-table">暂无数据，请先导入 Excel</div></div></div>
      </section>

      <section v-if="tab === 'strategy'" class="strategy-view"><div class="section-action"><div><span class="eyebrow">AI RESPONSE STRATEGY</span><h2>智能应对策略</h2><p>{{ eligibility?.reason }}</p></div><button class="primary" :disabled="!eligibility?.eligible || busy === 'strategy'" @click="generateStrategy">{{ eligibility?.state === 'generating' || busy === 'strategy' ? '应对策略生成中…' : '✦ 生成新应对策略' }}</button></div><article v-if="generatingStrategy" class="document-card generating-document"><header><div><b>应对策略 V{{ generatingStrategy.version_no }}</b><span>AI生成中</span></div></header><div class="generation-progress"><i></i><strong>正在根据 {{ generatingStrategy.analyzed_count }} 条已研判数据生成应对策略</strong><small>记录已创建，生成完成后将在原记录上更新内容</small></div></article><article v-for="s in completedStrategies" :key="s.id" class="document-card"><header><div><b>应对策略 V{{ s.version_no }}</b><span>{{ s.is_manually_edited ? 'AI生成 · 人工已审核' : 'AI生成' }}</span></div><button @click="openEditor('strategy', s)">编辑应对策略</button></header><pre>{{ s.content }}</pre><footer>基于 {{ s.analyzed_count }} 条已研判数据 · {{ new Date(s.created_at).toLocaleString() }}</footer></article><article v-for="s in failedStrategies" :key="s.id" class="document-card failed-document"><header><div><b>应对策略 V{{ s.version_no }}</b><span>生成失败</span></div></header><p>{{ s.generation_error || '应对策略生成失败，可重新发起生成。' }}</p></article><div v-if="!strategies.length" class="empty-document">完成数据研判后，即可生成针对性的舆情应对策略。</div></section>

      <section v-if="tab === 'report'" class="strategy-view"><div class="section-action"><div><span class="eyebrow">ARCHIVE REPORT</span><h2>任务归档报告</h2><p>{{ reportStatus.reason || '任务完结后生成正式舆情分析报告并导出 PDF。' }}</p></div><button class="primary" :disabled="reportStatus.state !== 'available' || busy === 'report'" @click="generateReport">{{ reportStatus.state === 'generating' || busy === 'report' ? '报告生成中…' : reportStatus.state === 'ready' ? '报告已生成' : '✦ 生成任务报告' }}</button></div><article v-if="generatingReport" class="document-card generating-document"><header><div><b>任务报告 V{{ generatingReport.version_no }}</b><span>AI生成中</span></div></header><div class="generation-progress"><i></i><strong>AI正在撰写任务归档报告</strong><small>记录已创建，生成完成后将在原记录上更新内容</small></div></article><article v-for="r in completedReports" :key="r.id" class="document-card"><header><div><b>任务报告 V{{ r.version_no }}</b><span>{{ r.is_manually_edited ? 'AI生成 · 人工已审核' : 'AI生成' }}</span></div><div><button @click="openEditor('report', r)">编辑</button><a class="button-link" :href="`/api/tasks/${id}/reports/${r.id}/pdf`">导出 PDF</a></div></header><pre>{{ r.content }}</pre><footer>{{ new Date(r.created_at).toLocaleString() }}</footer></article><article v-for="r in failedReports" :key="r.id" class="document-card failed-document"><header><div><b>任务报告 V{{ r.version_no }}</b><span>生成失败</span></div></header><p>{{ r.generation_error || '任务报告生成失败，可重新发起生成。' }}</p></article><div v-if="!reports.length" class="empty-document">{{ task.status === 'completed' ? '点击上方按钮生成首份报告。' : '请先将任务设置为已完结。' }}</div></section>
    </main>

    <div v-if="selected" class="modal-mask" @click.self="selected = undefined"><div class="modal item-modal"><div class="modal-head"><div><span class="eyebrow">INTELLIGENCE DETAIL</span><h2>{{ selected.title }}</h2></div><button class="close" @click="selected = undefined">×</button></div><div class="item-meta"><span>{{ selected.platform }}</span><span>{{ selected.author }}</span><span>{{ selected.publish_time ? new Date(selected.publish_time).toLocaleString() : '时间未知' }}</span><a v-if="selected.source_url" :href="selected.source_url" target="_blank">查看源数据 ↗</a></div><div class="engagement-metrics"><span><b>{{ selected.view_count.toLocaleString() }}</b><small>阅读/播放</small></span><span><b>{{ selected.like_count.toLocaleString() }}</b><small>点赞</small></span><span><b>{{ selected.comment_count.toLocaleString() }}</b><small>评论</small></span><span><b>{{ selected.share_count.toLocaleString() }}</b><small>转发/分享</small></span><span><b>{{ selected.interaction_count.toLocaleString() }}</b><small>互动总量</small></span></div><p class="item-content">{{ selected.content }}</p><div v-if="selected.media.length" class="media-grid"><template v-for="m in selected.media" :key="m.id"><img v-if="m.media_type === 'image'" :src="m.storage_path"><video v-else :src="m.storage_path" controls></video></template></div><div class="review-box"><h3>人工研判修正</h3><div class="form-row"><label>情感倾向<select v-model="revision.sentiment"><option value="positive">正面</option><option value="neutral">中性</option><option value="negative">负面</option></select></label><label>风险等级<select v-model="revision.risk_level"><option value="low">低风险</option><option value="medium">中风险</option><option value="high">高风险</option></select></label></div><label>判断依据<textarea v-model="revision.reason" rows="3"></textarea></label><label>主题标签<input v-model="revision.topics" placeholder="多个标签用逗号分隔"></label><label>修改说明<input v-model="revision.change_note" required placeholder="请说明人工修改原因"></label><button class="primary full" :disabled="!revision.reason || !revision.change_note || busy === 'revision'" @click="saveRevision">保存人工研判</button></div></div></div>
    <div v-if="editId" class="modal-mask" @click.self="editId = 0"><div class="modal editor-modal"><div class="modal-head"><h2>编辑{{ editKind === 'strategy' ? '应对策略' : '任务报告' }}</h2><button class="close" @click="editId = 0">×</button></div><textarea v-model="editContent"></textarea><div class="modal-actions"><button @click="editId = 0">取消</button><button class="primary" @click="saveEditor">保存人工修订</button></div></div></div>
    <TaskConfigModal v-if="showTaskConfig" :task="task" @close="showTaskConfig=false" @saved="showTaskConfig=false; load()" />
  </div>
</template>
