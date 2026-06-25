<script setup lang="ts">
import { reactive, ref } from 'vue'
import { api, type Task } from '../api'

const props = defineProps<{ task?: Task }>()
const emit = defineEmits<{ close: []; saved: [task: Task] }>()
const platforms = ['微博', '小红书', '快手', '抖音', '微信公众号']
const saving = ref(false)
const error = ref('')
const form = reactive({
  name: props.task?.name || '',
  keywords: props.task?.keywords.join('，') || '',
  platforms: [...(props.task?.platforms || ['微博', '小红书'])],
  start_time: props.task?.start_time?.slice(0, 16) || '',
  end_time: props.task?.end_time?.slice(0, 16) || '',
  description: props.task?.description || '',
})

const submit = async () => {
  saving.value = true; error.value = ''
  try {
    const payload = {
      ...form,
      keywords: form.keywords.split(/[,，\s]+/).filter(Boolean),
      start_time: form.start_time || null,
      end_time: form.end_time || null,
    }
    const response = props.task
      ? await api.patch<Task>(`/tasks/${props.task.id}`, payload)
      : await api.post<Task>('/tasks', payload)
    emit('saved', response.data)
  } catch (e: any) { error.value = e.response?.data?.detail || '任务配置保存失败' }
  finally { saving.value = false }
}
</script>

<template>
  <div class="modal-mask" @click.self="emit('close')">
    <form class="modal" @submit.prevent="submit">
      <div class="modal-head"><div><span class="eyebrow">TASK CONFIGURATION</span><h2>{{ task ? '修改任务配置' : '创建任务' }}</h2></div><button type="button" class="close" @click="emit('close')">×</button></div>
      <label>任务名称<input v-model="form.name" required placeholder="例如：校园食品安全舆情监测"></label>
      <label>数据采集关键词<input v-model="form.keywords" required placeholder="多个关键词用逗号分隔"></label>
      <label>数据采集平台<div class="checks"><span v-for="p in platforms" :key="p"><input v-model="form.platforms" type="checkbox" :value="p">{{ p }}</span></div></label>
      <div class="form-row"><label>采集开始时间<input v-model="form.start_time" type="datetime-local"></label><label>采集结束时间<input v-model="form.end_time" type="datetime-local"></label></div>
      <label>任务说明<textarea v-model="form.description" rows="3" placeholder="可选"></textarea></label>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="modal-actions"><button type="button" @click="emit('close')">取消</button><button class="primary" :disabled="saving || !form.platforms.length">{{ saving ? '保存中…' : '保存任务配置' }}</button></div>
    </form>
  </div>
</template>

