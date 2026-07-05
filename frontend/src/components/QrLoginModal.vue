<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

const props = defineProps<{ platform: string }>()
const emit = defineEmits<{ close: []; success: [] }>()

const qrImage = ref('')
const status = ref<'loading' | 'waiting' | 'success' | 'timeout' | 'error'>('loading')
const message = ref('正在生成二维码…')
const countdown = ref(180)
let eventSource: EventSource | undefined
let timer: number | undefined

const start = () => {
  status.value = 'loading'
  message.value = '正在生成二维码…'
  countdown.value = 180
  qrImage.value = ''
  eventSource = new EventSource(`/api/collection/accounts/login?platform=${encodeURIComponent(props.platform)}`)

  eventSource.addEventListener('qrcode', (e) => {
    const data = JSON.parse((e as MessageEvent).data)
    qrImage.value = data.image || ''
    status.value = 'waiting'
    message.value = '请使用手机扫码确认登录'
    timer = window.setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) { status.value = 'timeout'; message.value = '二维码已过期'; cleanup() }
    }, 1000)
  })

  eventSource.addEventListener('success', () => {
    status.value = 'success'
    message.value = '登录成功，账号已保存'
    cleanup()
    setTimeout(() => emit('success'), 1200)
  })

  eventSource.addEventListener('timeout', () => {
    status.value = 'timeout'
    message.value = '二维码已过期'
    cleanup()
  })

  eventSource.addEventListener('error', (e) => {
    if (e instanceof MessageEvent) {
      try {
        const data = JSON.parse(e.data || '{}')
        status.value = 'error'
        message.value = data.message || '登录失败'
      } catch {
        if (status.value === 'loading' || status.value === 'waiting') {
          status.value = 'error'; message.value = '连接中断，请重试'
        }
      }
    } else if (status.value === 'loading' || status.value === 'waiting') {
      status.value = 'error'
      message.value = '连接中断，请重试'
    }
    cleanup()
  })
}

const cleanup = () => {
  eventSource?.close()
  eventSource = undefined
  if (timer) { window.clearInterval(timer); timer = undefined }
}

onBeforeUnmount(cleanup)
start()
</script>

<template>
  <div class="modal-mask" @click.self="emit('close')">
    <div class="qr-modal">
      <button class="qr-close" @click="emit('close')">×</button>
      <h2>添加{{ platform }}账号</h2>
      <p class="qr-sub">使用{{ platform }} App 扫码登录</p>

      <div class="qr-box">
        <img v-if="qrImage" :src="`data:image/png;base64,${qrImage}`" alt="登录二维码" />
        <div v-else class="qr-loading">
          <span class="qr-spinner"></span>
          <small>生成中…</small>
        </div>
        <div v-if="status === 'success'" class="qr-overlay ok">
          <span class="ov-icon">✓</span>
        </div>
        <div v-if="status === 'timeout' || status === 'error'" class="qr-overlay fail">
          <span class="ov-icon">!</span>
          <button class="qr-retry" @click="start">重新生成</button>
        </div>
      </div>

      <p :class="['qr-status', status]">{{ message }}</p>
      <p v-if="status === 'waiting'" class="qr-count">{{ countdown }} 秒后过期</p>

      <p class="qr-hint">登录后 Cookie 将自动保存，用于持续监测采集。Cookie 失效时系统自动刷新，SSO 过期才需重新扫码。</p>
    </div>
  </div>
</template>

<style scoped>
.modal-mask {
  position: fixed; z-index: 50; inset: 0;
  background: rgba(15,23,42,0.45); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; padding: 30px;
}
.qr-modal {
  width: min(380px, calc(100vw - 32px)); background: #fff;
  border-radius: 16px; box-shadow: 0 20px 50px rgba(15,23,42,0.16);
  padding: 24px; position: relative;
}
.qr-close {
  position: absolute; top: 14px; right: 14px; width: 28px; height: 28px;
  border-radius: 50%; background: transparent; border: 0; font-size: 18px;
  color: #86909c; cursor: pointer; display: grid; place-items: center; transition: all 0.15s;
}
.qr-close:hover { background: #f2f3f5; color: #1d2129; }
.qr-modal h2 { font-size: 16px; font-weight: 600; color: #1d2129; margin: 0 0 4px; }
.qr-sub { font-size: 13px; color: #86909c; margin: 0 0 20px; }

.qr-box {
  width: 204px; height: 204px; margin: 0 auto 16px;
  border: 1px solid #f2f3f5; border-radius: 12px; background: #fafbfc;
  display: grid; place-items: center; position: relative; overflow: hidden;
}
.qr-box img { width: 184px; height: 184px; object-fit: contain; }
.qr-loading { display: flex; flex-direction: column; align-items: center; gap: 8px; color: #86909c; }
.qr-loading small { font-size: 11px; }
.qr-spinner {
  width: 28px; height: 28px; border: 2.5px solid #eef0f3; border-top-color: #4080ff;
  border-radius: 50%; animation: qr-spin 0.8s linear infinite;
}
@keyframes qr-spin { to { transform: rotate(360deg); } }

.qr-overlay {
  position: absolute; inset: 0; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 10px;
  background: rgba(255,255,255,0.95); border-radius: 12px;
}
.ov-icon {
  width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center;
  font-size: 18px; font-weight: 700; color: #fff;
}
.qr-overlay.ok .ov-icon { background: #00b42a; }
.qr-overlay.fail .ov-icon { background: #f53f3f; }
.qr-retry {
  border: 1px solid #e5e6eb; background: #fff; color: #4e5969;
  border-radius: 6px; padding: 5px 14px; font-size: 12px; cursor: pointer; transition: all 0.15s;
}
.qr-retry:hover { background: #f7f8fa; border-color: #4080ff; color: #4080ff; }

.qr-status { font-size: 13px; color: #1d2129; text-align: center; margin: 0 0 4px; font-weight: 500; }
.qr-status.success { color: #00b42a; }
.qr-status.timeout, .qr-status.error { color: #f53f3f; }
.qr-count { font-size: 12px; color: #a9aeb8; text-align: center; margin: 0 0 16px; }
.qr-hint {
  font-size: 12px; color: #a9aeb8; text-align: center; line-height: 1.6;
  margin: 16px 0 0; padding-top: 14px; border-top: 1px solid #f2f3f5;
}
</style>
