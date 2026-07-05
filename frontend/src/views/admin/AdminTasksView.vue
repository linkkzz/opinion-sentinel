<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import AppHeader from '../../components/AppHeader.vue'
import { api, deleteTask, getTasks, type Task } from '../../api'

const tasks = ref<Task[]>([])
const showForm = ref(false)
const saving = ref(false)
const error = ref('')
const toast = ref('')
const form = reactive({ name: '', keywords: '', platforms: ['微博', '快手'], start_time: '', end_time: '', description: '', collection_enabled: true, collection_interval_seconds: 300 })
const platforms = ['微博', '快手', 'bilibili', '小红书', '抖音', '微信公众号']
const platformHints: Record<string, string> = { 微博: '支持持续监测', 快手: '支持持续监测', bilibili: '支持持续监测', 小红书: '即将接入', 抖音: '即将接入', 微信公众号: 'Excel导入' }

const collectionStateText: Record<string, string> = { collecting:'采集中', queued:'排队中', waiting:'等待下一轮', paused:'已暂停', error:'异常', idle:'等待启动', stopped:'已停止' }

const showToast = (msg: string) => { toast.value = msg; setTimeout(() => { if (toast.value === msg) toast.value = '' }, 2500) }
const load = async () => { tasks.value = await getTasks() }
const submit = async () => {
  saving.value = true; error.value = ''
  try {
    await api.post('/tasks', {
      ...form,
      keywords: form.keywords.split(/[,，\s]+/).filter(Boolean),
      start_time: form.start_time || null,
      end_time: form.end_time || null,
      collection_enabled: form.collection_enabled,
      collection_interval_seconds: Number(form.collection_interval_seconds) || 300,
    })
    showForm.value = false
    Object.assign(form, { name: '', keywords: '', platforms: ['微博', '快手'], start_time: '', end_time: '', description: '', collection_enabled: true, collection_interval_seconds: 300 })
    await load()
  } catch (e: any) { error.value = e.response?.data?.detail || '创建失败' }
  finally { saving.value = false }
}

const onDelete = async (task: Task) => {
  if (!confirm(`确定删除任务「${task.name}」？\n该任务的所有数据将一并删除，不可恢复。`)) return
  try { await deleteTask(task.id); showToast('任务已删除'); await load() }
  catch { showToast('删除失败') }
}

onMounted(load)
</script>

<template>
  <div class="admin-shell">
    <AppHeader mode="admin" />
    <main class="admin-content">
      <div class="page-heading">
        <div><span class="eyebrow">MISSION CONTROL</span><h1>舆情任务</h1><p>配置监测范围，导入数据并启动智能研判。</p></div>
        <button class="primary" @click="showForm = true">＋ 创建任务</button>
      </div>
      <div class="task-grid">
        <div v-for="task in tasks" :key="task.id" class="task-card-wrap">
          <router-link :to="`/admin/tasks/${task.id}`" class="task-card">
            <div class="task-card-top"><span :class="['status-dot', task.status]"></span><span>{{ task.status === 'running' ? '进行中' : '已完结' }}</span><time>{{ new Date(task.updated_at).toLocaleDateString() }}</time></div>
            <h3>{{ task.name }}</h3>
            <p>{{ task.description || '持续追踪相关平台信息，洞察舆情变化与潜在风险。' }}</p>
            <div class="tag-row"><span v-for="key in task.keywords.slice(0, 4)" :key="key"># {{ key }}</span></div>
            <div class="platform-row"><b v-for="p in task.platforms" :key="p">{{ p }}</b></div>
            <div class="task-card-foot"><span>持续监测</span><strong>{{ collectionStateText[task.collection_state] || '未启动' }}</strong><i>→</i></div>
          </router-link>
          <button class="card-del" title="删除任务" @click.prevent="onDelete(task)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
          </button>
        </div>
        <button v-if="!tasks.length" class="empty-card" @click="showForm = true">＋<b>创建第一个舆情任务</b><span>从定义关键词和监测平台开始</span></button>
      </div>
    </main>
    <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
      <form class="modal" @submit.prevent="submit">
        <div class="modal-head"><div><span class="eyebrow">NEW MISSION</span><h2>创建舆情任务</h2></div><button type="button" class="close" @click="showForm = false">×</button></div>
        <label>任务名称<input v-model="form.name" required placeholder="例如：校园食品安全舆情监测"></label>
        <label>监测关键词<input v-model="form.keywords" required placeholder="多个关键词用逗号分隔"></label>
        <label>监测平台<div class="checks platform-checks"><span v-for="p in platforms" :key="p"><input v-model="form.platforms" type="checkbox" :value="p"><b>{{ p }}</b><small>{{ platformHints[p] }}</small></span></div></label>
        <label class="switch-line"><input v-model="form.collection_enabled" type="checkbox">持续监测<small>任务运行期间按关键词和平台持续采集新增内容</small></label>
        <label v-if="form.collection_enabled">采集频率<select v-model="form.collection_interval_seconds"><option :value="180">每 3 分钟</option><option :value="300">每 5 分钟</option><option :value="600">每 10 分钟</option><option :value="1800">每 30 分钟</option></select></label>
        <div class="form-row"><label>开始时间<input v-model="form.start_time" type="datetime-local"></label><label>结束时间<input v-model="form.end_time" type="datetime-local"></label></div>
        <label>任务说明<textarea v-model="form.description" rows="3" placeholder="可选"></textarea></label>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="modal-actions"><button type="button" @click="showForm = false">取消</button><button class="primary" :disabled="saving">{{ saving ? '创建中…' : '创建任务' }}</button></div>
      </form>
    </div>
    <transition name="toast"><div v-if="toast" class="floating-toast">{{ toast }}</div></transition>
  </div>
</template>

<style scoped>
/* wrap 作为 grid 子项承载卡片视觉，内部 router-link 透明撑满 */
.task-card-wrap {
  position: relative;
  background: white;
  border: 1px solid #e2e9f3;
  border-radius: 15px;
  min-height: 270px;
  box-shadow: 0 8px 28px rgba(34, 59, 94, .05);
  transition: transform .2s, box-shadow .2s, border-color .2s;
}
.task-card-wrap:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 40px rgba(34, 78, 137, .12);
  border-color: #bcdcff;
}
/* 覆盖 global .task-card 的重复背景/边框，让 wrap 统一承载 */
.task-card-wrap .task-card {
  background: transparent;
  border: 0;
  box-shadow: none;
  min-height: 270px;
  height: 100%;
  display: block;
}

.card-del {
  position: absolute; top: 14px; right: 14px;
  width: 30px; height: 30px; border-radius: 8px;
  border: 0; background: rgba(255, 255, 255, 0.85); color: #9aa9bd;
  display: grid; place-items: center; cursor: pointer;
  opacity: 0; transition: all 0.18s; z-index: 5;
}
.task-card-wrap:hover .card-del { opacity: 1; }
.card-del:hover { background: #fff0f2; color: #e8385a; }

.floating-toast {
  position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
  background: rgba(31, 41, 55, 0.92); color: #fff; padding: 10px 20px;
  border-radius: 8px; font-size: 13px; z-index: 9999; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}
.toast-enter-active, .toast-leave-active { transition: all 0.25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translate(-50%, 8px); }
</style>
