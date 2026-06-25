<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import AppHeader from '../../components/AppHeader.vue'
import { api, getTasks, type Task } from '../../api'

const tasks = ref<Task[]>([])
const showForm = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({ name: '', keywords: '', platforms: ['微博', '小红书'], start_time: '', end_time: '', description: '' })
const platforms = ['微博', '小红书', '快手', '抖音', '微信公众号']
const load = async () => { tasks.value = await getTasks() }
const submit = async () => {
  saving.value = true; error.value = ''
  try {
    await api.post('/tasks', {
      ...form,
      keywords: form.keywords.split(/[,，\s]+/).filter(Boolean),
      start_time: form.start_time || null,
      end_time: form.end_time || null,
    })
    showForm.value = false
    Object.assign(form, { name: '', keywords: '', platforms: ['微博', '小红书'], start_time: '', end_time: '', description: '' })
    await load()
  } catch (e: any) { error.value = e.response?.data?.detail || '创建失败' }
  finally { saving.value = false }
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
        <router-link v-for="task in tasks" :key="task.id" :to="`/admin/tasks/${task.id}`" class="task-card">
          <div class="task-card-top"><span :class="['status-dot', task.status]"></span><span>{{ task.status === 'running' ? '进行中' : '已完结' }}</span><time>{{ new Date(task.updated_at).toLocaleDateString() }}</time></div>
          <h3>{{ task.name }}</h3>
          <p>{{ task.description || '持续追踪相关平台信息，洞察舆情变化与潜在风险。' }}</p>
          <div class="tag-row"><span v-for="key in task.keywords.slice(0, 4)" :key="key"># {{ key }}</span></div>
          <div class="platform-row"><b v-for="p in task.platforms" :key="p">{{ p }}</b></div>
          <div class="task-card-foot"><span>AI研判</span><strong>{{ {running:'分析中',waiting:'等待数据',paused:'已暂停',error:'异常'}[task.analysis_state] || '未启动' }}</strong><i>→</i></div>
        </router-link>
        <button v-if="!tasks.length" class="empty-card" @click="showForm = true">＋<b>创建第一个舆情任务</b><span>从定义关键词和监测平台开始</span></button>
      </div>
    </main>
    <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
      <form class="modal" @submit.prevent="submit">
        <div class="modal-head"><div><span class="eyebrow">NEW MISSION</span><h2>创建舆情任务</h2></div><button type="button" class="close" @click="showForm = false">×</button></div>
        <label>任务名称<input v-model="form.name" required placeholder="例如：校园食品安全舆情监测"></label>
        <label>监测关键词<input v-model="form.keywords" required placeholder="多个关键词用逗号分隔"></label>
        <label>监测平台<div class="checks"><span v-for="p in platforms" :key="p"><input v-model="form.platforms" type="checkbox" :value="p">{{ p }}</span></div></label>
        <div class="form-row"><label>开始时间<input v-model="form.start_time" type="datetime-local"></label><label>结束时间<input v-model="form.end_time" type="datetime-local"></label></div>
        <label>任务说明<textarea v-model="form.description" rows="3" placeholder="可选"></textarea></label>
        <p v-if="error" class="error">{{ error }}</p>
        <div class="modal-actions"><button type="button" @click="showForm = false">取消</button><button class="primary" :disabled="saving">{{ saving ? '创建中…' : '创建任务' }}</button></div>
      </form>
    </div>
  </div>
</template>

