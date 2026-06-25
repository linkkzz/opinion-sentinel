<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppHeader from '../../components/AppHeader.vue'
import ChartPanel from '../../components/ChartPanel.vue'
import TaskConfigModal from '../../components/TaskConfigModal.vue'
import { api, getTasks, type Task } from '../../api'

const tasks = ref<Task[]>([])
const overview = ref({ tasks: 0, running: 0, completed: 0, data_total: 0, analyzed: 0, analysis_rate: 0, high_risk: 0, negative: 0, interactions: 0, views: 0 })
const stats = ref<Record<number, any>>({})
const clock = ref(new Date())
const showTaskConfig = ref(false)
const load = async () => {
  tasks.value = await getTasks()
  overview.value = (await api.get('/tasks/overview/dashboard')).data
  const rows = await Promise.all(tasks.value.map(async task => [task.id, (await api.get(`/tasks/${task.id}/stats`)).data] as const))
  stats.value = Object.fromEntries(rows)
}
const riskOption = computed(() => ({
  tooltip: { trigger: 'item' }, legend: { bottom: 0, textStyle: { color: '#9bb1d1' } },
  series: [{ type: 'pie', radius: ['58%', '78%'], center: ['50%', '44%'], label: { show: false }, data: [
    { name: '高风险', value: Object.values(stats.value).reduce((s: number, x: any) => s + (x.risks.high || 0), 0), itemStyle: { color: '#ff4d68' } },
    { name: '中风险', value: Object.values(stats.value).reduce((s: number, x: any) => s + (x.risks.medium || 0), 0), itemStyle: { color: '#ffb547' } },
    { name: '低风险', value: Object.values(stats.value).reduce((s: number, x: any) => s + (x.risks.low || 0), 0), itemStyle: { color: '#20d5a4' } },
  ] }],
}))
const platformOption = computed(() => {
  const all: Record<string, number> = {}
  Object.values(stats.value).forEach((x: any) => Object.entries(x.platforms).forEach(([k,v]) => all[k] = (all[k] || 0) + Number(v)))
  return { grid: { left: 40, right: 20, top: 20, bottom: 30 }, xAxis: { type:'category', data:Object.keys(all), axisLabel:{color:'#8ca5c9'}, axisLine:{lineStyle:{color:'#244267'}} }, yAxis:{ type:'value', axisLabel:{color:'#8ca5c9'}, splitLine:{lineStyle:{color:'#152c4d'}} }, series:[{type:'bar', data:Object.values(all), barWidth:18, itemStyle:{color:'#23aaff', borderRadius:[8,8,0,0]}}] }
})
const sentimentOption = computed(() => {
  const values={positive:0,neutral:0,negative:0}
  Object.values(stats.value).forEach((x:any)=>Object.keys(values).forEach(k=>(values as any)[k]+=x.sentiments[k]||0))
  return {tooltip:{trigger:'item'},series:[{type:'pie',radius:['45%','70%'],roseType:'radius',label:{color:'#91a9c8',fontSize:10},data:[{name:'正面',value:values.positive,itemStyle:{color:'#20d5a4'}},{name:'中性',value:values.neutral,itemStyle:{color:'#39a9ff'}},{name:'负面',value:values.negative,itemStyle:{color:'#ff4d68'}}]}]}
})
const engagementTotals = computed(() => Object.values(stats.value).reduce((total:any, row:any) => ({
  likes: total.likes + (row.engagement?.likes || 0),
  comments: total.comments + (row.engagement?.comments || 0),
  shares: total.shares + (row.engagement?.shares || 0),
}), { likes:0, comments:0, shares:0 }))
const engagementOption = computed(() => ({
  tooltip:{trigger:'item',formatter:'{b}<br/>{c}（{d}%）'},
  legend:{bottom:5,textStyle:{color:'#7895b8',fontSize:9}},
  series:[{type:'pie',radius:['48%','70%'],center:['50%','43%'],padAngle:4,itemStyle:{borderRadius:5},label:{show:false},data:[
    {name:'点赞',value:engagementTotals.value.likes,itemStyle:{color:'#22c7ff'}},
    {name:'评论',value:engagementTotals.value.comments,itemStyle:{color:'#7a7dff'}},
    {name:'转发',value:engagementTotals.value.shares,itemStyle:{color:'#20d5a4'}},
  ]}],
}))
const globalTrendOption = computed(() => {
  const totals:Record<string,number>={}
  Object.values(stats.value).forEach((row:any)=>row.trend.forEach((point:any)=>totals[point.date]=(totals[point.date]||0)+point.count))
  const dates=Object.keys(totals).sort()
  return {grid:{left:42,right:18,top:28,bottom:35},tooltip:{trigger:'axis'},xAxis:{type:'category',data:dates,axisLabel:{color:'#7894b6',fontSize:9},axisLine:{lineStyle:{color:'#244267'}}},yAxis:{type:'value',axisLabel:{color:'#7894b6'},splitLine:{lineStyle:{color:'#142b49'}}},series:[{type:'line',smooth:true,symbol:'circle',symbolSize:7,data:dates.map(date=>totals[date]),lineStyle:{width:3,color:'#23c8ff'},itemStyle:{color:'#23c8ff'},areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(35,200,255,.4)'},{offset:1,color:'rgba(35,200,255,0)'}]}}}]}
})
const formatNumber = (value:number=0) => value >= 10000 ? `${(value/10000).toFixed(1)}万` : value.toLocaleString()
onMounted(() => { load(); window.setInterval(() => clock.value = new Date(), 1000) })
</script>

<template>
  <div class="screen-shell">
    <AppHeader mode="dashboard" />
    <main class="screen-content">
      <div class="screen-heading"><div><span class="eyebrow">GLOBAL SITUATION AWARENESS</span><h1>舆情全局态势</h1><p>全域任务实时感知与风险洞察</p></div><div class="screen-heading-actions"><button @click="showTaskConfig=true">＋ 配置新任务</button><div class="screen-time"><strong>{{ clock.toLocaleTimeString('zh-CN', { hour12: false }) }}</strong><span>{{ clock.toLocaleDateString('zh-CN', { year:'numeric', month:'long', day:'numeric', weekday:'long' }) }}</span></div></div></div>
      <section class="metric-row global-metrics">
        <div class="metric-card cyan"><span>监测任务</span><strong>{{ overview.tasks }}</strong><small>MONITORING MISSIONS</small></div>
        <div class="metric-card blue"><span>进行中</span><strong>{{ overview.running }}</strong><small>ACTIVE</small></div>
        <div class="metric-card violet"><span>数据总量</span><strong>{{ overview.data_total }}</strong><small>TOTAL DATA</small></div>
        <div class="metric-card green"><span>研判覆盖率</span><strong>{{ overview.analysis_rate }}%</strong><small>{{ overview.analyzed }} ANALYZED</small></div>
        <div class="metric-card red"><span>高风险舆情</span><strong>{{ overview.high_risk }}</strong><small>HIGH RISK</small></div>
        <div class="metric-card orange"><span>负面舆情</span><strong>{{ overview.negative }}</strong><small>NEGATIVE</small></div>
        <div class="metric-card cyan"><span>累计曝光</span><strong>{{ formatNumber(overview.views) }}</strong><small>TOTAL EXPOSURE</small></div>
        <div class="metric-card violet"><span>累计互动</span><strong>{{ formatNumber(overview.interactions) }}</strong><small>ENGAGEMENT</small></div>
      </section>
      <section class="overview-grid global-grid">
        <div class="screen-panel task-rank"><header><span>任务态势</span><small>MISSION STATUS</small></header><div class="task-rank-list"><router-link v-for="task in tasks" :key="task.id" :to="`/dashboard/tasks/${task.id}`"><span class="rank-no">{{ String(tasks.indexOf(task)+1).padStart(2,'0') }}</span><div><b>{{ task.name }}</b><small>{{ task.platforms.join(' · ') }}</small></div><div class="mini-progress"><i :style="`width:${stats[task.id]?.analysis_rate || 0}%`"></i></div><strong>{{ stats[task.id]?.total || 0 }}</strong><em :class="task.status">{{ task.status === 'running' ? '进行中' : '已完结' }}</em></router-link><div v-if="!tasks.length" class="screen-empty">暂无任务，请前往管理中心创建</div></div></div>
        <div class="screen-panel"><header><span>风险结构</span><small>RISK DISTRIBUTION</small></header><ChartPanel :option="riskOption" /></div>
        <div class="screen-panel wide"><header><span>平台声量分布</span><small>PLATFORM VOLUME</small></header><ChartPanel :option="platformOption" /></div>
        <div class="screen-panel"><header><span>全局情感结构</span><small>GLOBAL SENTIMENT</small></header><ChartPanel :option="sentimentOption" /></div>
        <div class="screen-panel alert-panel"><header><span>实时预警</span><small>RISK ALERTS</small><i class="live-dot"></i></header><div class="alerts"><template v-for="task in tasks" :key="task.id"><div v-if="stats[task.id]?.risks?.high"><span>高</span><div><b>{{ task.name }}</b><small>发现 {{ stats[task.id].risks.high }} 条高风险信息</small></div><time>持续关注</time></div></template><p v-if="!overview.high_risk">当前未发现高风险舆情</p></div></div>
        <div class="screen-panel"><header><span>全局声量走势</span><small>GLOBAL VOLUME TREND</small></header><ChartPanel :option="globalTrendOption" /></div>
        <div class="screen-panel"><header><span>互动行为结构</span><small>ENGAGEMENT MIX</small></header><ChartPanel :option="engagementOption" /></div>
      </section>
    </main>
    <TaskConfigModal v-if="showTaskConfig" @close="showTaskConfig=false" @saved="showTaskConfig=false; load()" />
  </div>
</template>
