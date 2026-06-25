<script setup lang="ts">
defineProps<{ mode: 'admin' | 'dashboard'; title?: string }>()
</script>

<template>
  <header class="app-header">
    <router-link :to="mode === 'admin' ? '/admin' : '/dashboard'" class="brand">
      <span class="brand-mark"><i></i><i></i><i></i></span>
      <span>舆情智析</span><small>OPINION SENTINEL</small>
    </router-link>
    <div v-if="title" class="header-title">{{ title }}</div>
    <nav>
      <router-link v-if="mode === 'dashboard'" to="/dashboard" class="active">任务总览</router-link>
      <router-link v-if="mode === 'admin'" to="/admin" class="active">任务管理</router-link>
      <router-link to="/" class="portal-exit">退出当前入口</router-link>
    </nav>
  </header>
</template>
