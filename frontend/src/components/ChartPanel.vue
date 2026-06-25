<script setup lang="ts">
import * as echarts from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ option: any }>()
const element = ref<HTMLElement>()
let chart: echarts.ECharts | undefined
const resize = () => chart?.resize()
onMounted(() => {
  if (element.value) chart = echarts.init(element.value)
  chart?.setOption(props.option)
  window.addEventListener('resize', resize)
})
watch(() => props.option, value => chart?.setOption(value, true), { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>

<template><div ref="element" class="chart"></div></template>
