<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../../components/AppHeader.vue'
import ChartPanel from '../../components/ChartPanel.vue'
import TaskConfigModal from '../../components/TaskConfigModal.vue'
import { api, getCollectionFeed, getCollectionStatus, getTask, type CollectionStatus, type SourceItem, type Task } from '../../api'

const id = Number(useRoute().params.id)
const task = ref<Task>()
const stats = ref<any>({ risks:{}, sentiments:{}, platforms:{}, engagement:{}, trend:[], risk_trend:[], sentiment_trend:[], topics:[] })
const items = ref<SourceItem[]>([])
const collectionStatus = ref<CollectionStatus>()
const strategy = ref<any>()
const eligibility = ref<any>({ eligible: false, reason: '正在检查研判数据…' })
const reports = ref<any[]>([])
const reportStatus = ref<any>({ state: 'unavailable', reason: '' })
const busy = ref('')
const message = ref('')
const selected = ref<SourceItem>()
const showStrategyDetail = ref(false)
const showReportDetail = ref(false)
const showTaskConfig = ref(false)
let refreshTimer: number | undefined
const latestReport = computed(() => reports.value.find(value => value.generation_status === 'completed'))
const collectionScreenStateText = computed(() => ({ idle:'等待任务', queued:'排队中', collecting:'采集中', waiting:'等待下一轮', paused:'已暂停', error:'异常', stopped:'已停止' }[collectionStatus.value?.state || 'idle'] || '等待任务'))
const feedItems = computed(() => items.value.slice(0, 20))
const scrollingFeedItems = computed(() => feedItems.value.length > 6 ? [...feedItems.value, ...feedItems.value] : feedItems.value)
const hotItems = computed(() => [...items.value].sort((a,b)=>b.interaction_count-a.interaction_count).slice(0,6))
const maxInteraction = computed(() => Math.max(1, ...hotItems.value.map(item=>item.interaction_count)))
const formatNumber = (value:number=0) => value >= 10000 ? `${(value/10000).toFixed(1)}万` : value.toLocaleString()
const sentimentText: Record<string, string> = { positive: '正面', neutral: '中性', negative: '负面' }
const riskText: Record<string, string> = { low: '低风险', medium: '中风险', high: '高风险' }
const hasUsableSource = (url?: string) => Boolean(url && !url.includes('example.com'))
const analysisStatusText = (item: SourceItem) => item.analysis_status === 'analyzed'
  ? (item.current_analysis?.source === 'human' ? '人工已修正' : 'AI已研判')
  : item.analysis_status === 'analyzing'
    ? 'AI研判中'
    : item.analysis_status === 'failed'
      ? '研判异常'
      : '等待AI研判'
const analysisStatusHint = (item: SourceItem) => item.analysis_status === 'analyzed'
  ? '该内容已形成研判结论。'
  : item.analysis_status === 'analyzing'
    ? 'AI正在读取正文、互动量和任务上下文，完成后会自动刷新。'
    : item.analysis_status === 'failed'
      ? (item.analysis_error || 'AI研判失败，请检查模型服务或稍后重试。')
      : '新入库内容已进入待研判队列，启动AI分析后会自动生成情感、风险和依据。'
const sentimentOption = computed(() => ({ tooltip:{trigger:'item'}, series:[{type:'pie', radius:['52%','76%'], label:{color:'#b8c9df', formatter:'{b}\n{d}%'}, data:[{name:'正面',value:stats.value.sentiments.positive||0,itemStyle:{color:'#20d5a4'}},{name:'中性',value:stats.value.sentiments.neutral||0,itemStyle:{color:'#39a9ff'}},{name:'负面',value:stats.value.sentiments.negative||0,itemStyle:{color:'#ff4d68'}}]}] }))
const trendOption = computed(() => ({ grid:{left:45,right:20,top:30,bottom:35}, tooltip:{trigger:'axis'}, xAxis:{type:'category',data:stats.value.trend.map((x:any)=>x.date),axisLabel:{color:'#829cbc'},axisLine:{lineStyle:{color:'#244267'}}},yAxis:{type:'value',axisLabel:{color:'#829cbc'},splitLine:{lineStyle:{color:'#142b49'}}},series:[{type:'line',smooth:true,data:stats.value.trend.map((x:any)=>x.count),symbolSize:8,lineStyle:{color:'#22c7ff',width:3},itemStyle:{color:'#22c7ff'},areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(34,199,255,.35)'},{offset:1,color:'rgba(34,199,255,0)'}]}}}]}))
const platformOption = computed(() => ({ grid:{left:80,right:20,top:10,bottom:20},xAxis:{type:'value',show:false},yAxis:{type:'category',data:Object.keys(stats.value.platforms),axisLabel:{color:'#9bb1d1'},axisLine:{show:false},axisTick:{show:false}},series:[{type:'bar',data:Object.values(stats.value.platforms),barWidth:12,itemStyle:{color:'#6c7cff',borderRadius:8},label:{show:true,position:'right',color:'#c8d8ee'}}]}))
const riskTrendOption = computed(() => ({
  grid:{left:45,right:20,top:35,bottom:35}, tooltip:{trigger:'axis'},
  legend:{top:8,right:15,textStyle:{color:'#7894b6',fontSize:9},data:['高风险','中风险','低风险']},
  xAxis:{type:'category',data:stats.value.risk_trend.map((x:any)=>x.date),axisLabel:{color:'#7893b3'},axisLine:{lineStyle:{color:'#244267'}}},
  yAxis:{type:'value',axisLabel:{color:'#7893b3'},splitLine:{lineStyle:{color:'#142b49'}}},
  series:[
    {name:'高风险',type:'line',smooth:true,data:stats.value.risk_trend.map((x:any)=>x.high),lineStyle:{color:'#ff4d68',width:2},itemStyle:{color:'#ff4d68'}},
    {name:'中风险',type:'line',smooth:true,data:stats.value.risk_trend.map((x:any)=>x.medium),lineStyle:{color:'#ffb547',width:2},itemStyle:{color:'#ffb547'}},
    {name:'低风险',type:'line',smooth:true,data:stats.value.risk_trend.map((x:any)=>x.low),lineStyle:{color:'#20d5a4',width:2},itemStyle:{color:'#20d5a4'}},
  ],
}))
const topicOption = computed(() => ({
  tooltip:{formatter:(p:any)=>`${p.data[3]}：${p.data[2]}次`},
  xAxis:{show:false,min:-1,max:4}, yAxis:{show:false,min:-1,max:4},
  series:[{type:'scatter',data:stats.value.topics.map((x:any,i:number)=>[i%4,Math.floor(i/4),x.value,x.name]),symbolSize:(v:any)=>Math.min(62,22+v[2]*6),itemStyle:{color:(p:any)=>['#22c7ff','#6c7cff','#20d5a4','#ffb547','#ef5da8'][p.dataIndex%5],opacity:.72},label:{show:true,formatter:(p:any)=>p.data[3],color:'#e4f2ff',fontSize:9}}],
}))
const sentimentTrendOption = computed(() => ({
  grid:{left:38,right:14,top:38,bottom:32}, tooltip:{trigger:'axis'},
  legend:{top:8,right:10,textStyle:{color:'#7894b6',fontSize:8},data:['正面','中性','负面']},
  xAxis:{type:'category',data:stats.value.sentiment_trend.map((x:any)=>x.date),axisLabel:{color:'#7893b3',fontSize:8},axisLine:{lineStyle:{color:'#244267'}}},
  yAxis:{type:'value',axisLabel:{color:'#7893b3',fontSize:8},splitLine:{lineStyle:{color:'#142b49'}}},
  series:[
    {name:'正面',type:'line',stack:'sentiment',smooth:true,showSymbol:false,areaStyle:{opacity:.18},data:stats.value.sentiment_trend.map((x:any)=>x.positive),lineStyle:{color:'#20d5a4'},itemStyle:{color:'#20d5a4'}},
    {name:'中性',type:'line',stack:'sentiment',smooth:true,showSymbol:false,areaStyle:{opacity:.16},data:stats.value.sentiment_trend.map((x:any)=>x.neutral),lineStyle:{color:'#39a9ff'},itemStyle:{color:'#39a9ff'}},
    {name:'负面',type:'line',stack:'sentiment',smooth:true,showSymbol:false,areaStyle:{opacity:.18},data:stats.value.sentiment_trend.map((x:any)=>x.negative),lineStyle:{color:'#ff4d68'},itemStyle:{color:'#ff4d68'}},
  ],
}))
const engagementOption = computed(() => ({
  tooltip:{trigger:'item',formatter:'{b}<br/>{c}（{d}%）'},
  legend:{bottom:4,textStyle:{color:'#7894b6',fontSize:8}},
  series:[{type:'pie',radius:['46%','68%'],center:['50%','43%'],padAngle:4,itemStyle:{borderRadius:5},label:{show:false},data:[
    {name:'点赞',value:stats.value.engagement.likes||0,itemStyle:{color:'#22c7ff'}},
    {name:'评论',value:stats.value.engagement.comments||0,itemStyle:{color:'#7a7dff'}},
    {name:'转发',value:stats.value.engagement.shares||0,itemStyle:{color:'#20d5a4'}},
  ]}],
}))
const load = async () => {
  task.value=await getTask(id)
  stats.value=(await api.get(`/tasks/${id}/stats`)).data
  items.value=(await getCollectionFeed(id,50)).items
  collectionStatus.value=await getCollectionStatus(id)
  const rows=(await api.get(`/tasks/${id}/strategies`)).data
  strategy.value=rows.find((value:any)=>value.generation_status==='completed')
  eligibility.value=(await api.get(`/tasks/${id}/strategies/eligibility`)).data
  reports.value=(await api.get(`/tasks/${id}/reports`)).data
  reportStatus.value=(await api.get(`/tasks/${id}/reports/status`)).data
}
const generateStrategy = async () => {
  busy.value='strategy'; message.value=''; eligibility.value={state:'generating',eligible:false,reason:'应对策略正在生成中',analyzed_count:stats.value.analyzed}
  try { await api.post(`/tasks/${id}/strategies`); message.value='应对策略生成成功'; await load() }
  catch(e:any) { message.value=e.response?.data?.detail || '应对策略生成失败'; await load() }
  finally { busy.value='' }
}
const openStrategyDetail = () => {
  if (!strategy.value) return
  showStrategyDetail.value=true
}
const completeTask = async () => {
  if (!confirm('完结后将停止持续AI研判，确定完结该任务吗？')) return
  busy.value='complete'; message.value=''
  try { await api.post(`/tasks/${id}/complete`); message.value='任务已完结，现在可以生成归档报告'; await load() }
  catch(e:any) { message.value=e.response?.data?.detail || '任务完结失败' }
  finally { busy.value='' }
}
const generateReport = async () => {
  busy.value='report'; message.value=''; reportStatus.value={state:'generating',reason:'任务报告正在生成中'}
  try { await api.post(`/tasks/${id}/reports`); message.value='任务报告生成成功'; await load() }
  catch(e:any) { message.value=e.response?.data?.detail || '报告生成失败'; await load() }
  finally { busy.value='' }
}
onMounted(async () => { await load(); refreshTimer=window.setInterval(load, 3000) })
onBeforeUnmount(() => window.clearInterval(refreshTimer))
</script>

<template>
  <div class="screen-shell" v-if="task">
    <AppHeader mode="dashboard" :title="task.name" />
    <main class="screen-content task-screen">
      <div class="task-screen-head"><router-link to="/dashboard">← 任务总览</router-link><div><span :class="['status-dot',task.status]"></span>{{ task.status==='running'?'实时监测中':'任务已完结' }} · {{ task.platforms.join(' / ') }}</div><div class="screen-actions"><button @click="showTaskConfig=true">修改任务配置</button><button v-if="task.status==='running'" :disabled="busy==='complete'" @click="completeTask">完结任务</button><button v-else-if="reportStatus.state==='available'" :disabled="busy==='report'" @click="generateReport">{{ busy==='report'?'报告生成中…':'生成任务报告' }}</button><button v-else-if="reportStatus.state==='generating'" disabled>报告生成中…</button><button v-if="latestReport" @click="showReportDetail=true">查看任务报告</button><a v-if="latestReport" :href="`/api/tasks/${id}/reports/${latestReport.id}/pdf`">下载报告 PDF</a></div></div>
      <div v-if="message" class="screen-message">{{ message }}<button @click="message=''">×</button></div>
      <section class="metric-row compact task-metrics"><div class="metric-card cyan"><span>数据总量</span><strong>{{ stats.total }}</strong><small>MONITORED</small></div><div class="metric-card blue"><span>研判完成</span><strong>{{ stats.analyzed }}</strong><small>{{ stats.analysis_rate }}%</small></div><div class="metric-card red"><span>高风险</span><strong>{{ stats.risks.high || 0 }}</strong><small>HIGH RISK</small></div><div class="metric-card orange"><span>中风险</span><strong>{{ stats.risks.medium || 0 }}</strong><small>MEDIUM RISK</small></div><div class="metric-card green"><span>低风险</span><strong>{{ stats.risks.low || 0 }}</strong><small>LOW RISK</small></div><div class="metric-card cyan"><span>阅读/播放</span><strong>{{ formatNumber(stats.engagement.views) }}</strong><small>EXPOSURE</small></div><div class="metric-card violet"><span>互动总量</span><strong>{{ formatNumber(stats.engagement.interactions) }}</strong><small>ENGAGEMENT</small></div><div class="metric-card red"><span>负面占比</span><strong>{{ stats.analyzed ? ((stats.sentiments.negative || 0) / stats.analyzed * 100).toFixed(1) : 0 }}%</strong><small>NEGATIVE RATIO</small></div></section>
      <section class="screen-live-strip"><header><span class="live-dot"></span><b>实时舆情流</b><small>{{ collectionScreenStateText }}</small></header><div><button v-for="item in feedItems.slice(0,8)" :key="item.id" @click="selected=item"><em>{{ item.platform }}</em><span>{{ item.title }}</span><strong>{{ item.analysis_status === 'analyzed' ? '已研判' : '等待AI研判' }}</strong></button><p v-if="!feedItems.length">等待持续监测采集首批内容</p></div></section>
      <section class="task-screen-grid">
        <div class="screen-panel"><header><span>情感倾向</span><small>SENTIMENT</small></header><ChartPanel :option="sentimentOption" /></div>
        <div class="screen-panel trend-panel"><header><span>舆情声量趋势</span><small>VOLUME TREND</small></header><ChartPanel :option="trendOption" /></div>
        <div class="screen-panel"><header><span>平台分布</span><small>PLATFORM</small></header><ChartPanel :option="platformOption" /></div>
        <div class="screen-panel feed-panel"><header><span>实时舆情流</span><small>INTELLIGENCE FEED · 自动滚动</small><i class="live-dot"></i></header><div class="feed-list"><div :class="['feed-track',{scrolling:feedItems.length>6}]"><button v-for="(item,index) in scrollingFeedItems" :key="`${item.id}-${index}`" @click="selected=item"><time>{{ item.publish_time ? new Date(item.publish_time).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}) : '--:--' }}</time><span><b>{{ item.title }}</b><small>{{ item.platform }} · {{ item.author }} · 互动 {{ formatNumber(item.interaction_count) }}</small></span><em v-if="item.current_analysis" :class="`risk ${item.current_analysis.risk_level}`">{{ item.current_analysis.risk_level==='high'?'高':item.current_analysis.risk_level==='medium'?'中':'低' }}</em><em v-else class="unjudged">未研判</em></button></div></div></div>
        <div class="screen-panel strategy-panel"><header><span>应对策略</span><small>RESPONSE STRATEGY</small><button class="panel-action" :disabled="!eligibility.eligible || busy==='strategy'" :title="eligibility.reason" @click="generateStrategy">{{ eligibility.state==='generating' || busy==='strategy'?'生成中…':strategy?'更新应对策略':'生成应对策略' }}</button></header><div v-if="eligibility.state==='generating'" class="screen-generation"><i></i><strong>应对策略生成中</strong><small>正在分析 {{ eligibility.analyzed_count }} 条研判结果，完成后自动展示</small></div><div v-else-if="strategy" class="strategy-preview"><div><span>应对策略 V{{ strategy.version_no }}</span><b>{{ strategy.is_manually_edited?'AI生成 · 人工已审核':'AI智能生成' }}</b></div><pre>{{ strategy.content }}</pre><button class="strategy-detail-link" @click="openStrategyDetail">查看完整应对策略 →</button></div><div v-else class="screen-empty">{{ eligibility.reason }}</div></div>
        <div class="screen-panel risk-trend-panel"><header><span>风险演化趋势</span><small>RISK EVOLUTION</small></header><ChartPanel :option="riskTrendOption" /></div>
        <div class="screen-panel sentiment-trend-panel"><header><span>情感演化</span><small>SENTIMENT EVOLUTION</small></header><ChartPanel :option="sentimentTrendOption" /></div>
        <div class="screen-panel engagement-panel"><header><span>互动构成</span><small>ENGAGEMENT MIX</small></header><ChartPanel :option="engagementOption" /></div>
        <div class="screen-panel topic-panel"><header><span>热点议题图谱</span><small>TOPIC CLUSTERS</small></header><ChartPanel :option="topicOption" /></div>
        <div class="screen-panel hot-panel"><header><span>互动热度排行</span><small>ENGAGEMENT RANKING</small></header><div class="hot-list"><button v-for="(item,index) in hotItems" :key="item.id" @click="selected=item"><i>{{ String(index+1).padStart(2,'0') }}</i><span><b>{{ item.title }}</b><small>{{ item.platform }} · {{ formatNumber(item.view_count) }} 曝光</small></span><div><em :style="`width:${item.interaction_count/maxInteraction*100}%`"></em></div><strong>{{ formatNumber(item.interaction_count) }}</strong></button><p v-if="!hotItems.length">暂无互动数据</p></div></div>
      </section>
    </main>
    <div v-if="selected" class="modal-mask dark" @click.self="selected=undefined">
      <article class="intel-detail screen-intel-detail">
        <button class="close" @click="selected=undefined">×</button>
        <span class="eyebrow">情报详情</span>
        <h2>{{ selected.title }}</h2>
        <div class="item-meta">
          <span>{{ selected.platform }}</span>
          <span>{{ selected.author }}</span>
          <span>{{ selected.publish_time ? new Date(selected.publish_time).toLocaleString() : '时间未知' }}</span>
          <a v-if="hasUsableSource(selected.source_url)" :href="selected.source_url" target="_blank">打开原文</a>
        </div>
        <div class="engagement-metrics">
          <span><b>{{ selected.view_count.toLocaleString() }}</b><small>阅读/播放</small></span>
          <span><b>{{ selected.like_count.toLocaleString() }}</b><small>点赞</small></span>
          <span><b>{{ selected.comment_count.toLocaleString() }}</b><small>评论</small></span>
          <span><b>{{ selected.share_count.toLocaleString() }}</b><small>转发/分享</small></span>
          <span><b>{{ selected.interaction_count.toLocaleString() }}</b><small>互动总量</small></span>
        </div>
        <p>{{ selected.content }}</p>
        <div class="analysis-summary screen-analysis-summary" :class="selected.analysis_status">
          <header>
            <span>研判状态</span>
            <b>{{ analysisStatusText(selected) }}</b>
          </header>
          <template v-if="selected.current_analysis">
            <div class="analysis-badges">
              <span :class="`sentiment ${selected.current_analysis.sentiment}`">{{ sentimentText[selected.current_analysis.sentiment] }}</span>
              <span :class="`risk ${selected.current_analysis.risk_level}`">{{ riskText[selected.current_analysis.risk_level] }}</span>
              <em>{{ selected.current_analysis.source==='human'?'人工修正':'AI研判' }}</em>
            </div>
            <p>{{ selected.current_analysis.reason }}</p>
            <div v-if="selected.current_analysis.topics.length" class="analysis-topics dark-topics">
              <span v-for="topic in selected.current_analysis.topics" :key="topic">{{ topic }}</span>
            </div>
          </template>
          <p v-else>{{ analysisStatusHint(selected) }}</p>
        </div>
      </article>
    </div>
    <div v-if="showStrategyDetail && strategy" class="modal-mask dark" @click.self="showStrategyDetail=false"><article class="intel-detail strategy-detail-modal"><button class="close" @click="showStrategyDetail=false">×</button><span class="eyebrow">RESPONSE STRATEGY</span><h2>完整应对策略 V{{ strategy.version_no }}</h2><div class="strategy-detail-meta"><span>依据 {{ strategy.analyzed_count }} 条已研判数据</span><b>{{ strategy.is_manually_edited?'AI生成 · 人工已审核':'AI智能生成' }}</b><time>{{ new Date(strategy.created_at).toLocaleString() }}</time></div><pre class="strategy-full-content">{{ strategy.content }}</pre></article></div>
    <div v-if="showReportDetail && latestReport" class="modal-mask dark" @click.self="showReportDetail=false"><article class="intel-detail strategy-detail-modal"><button class="close" @click="showReportDetail=false">×</button><span class="eyebrow">ARCHIVE REPORT</span><h2>任务报告 V{{ latestReport.version_no }}</h2><div class="strategy-detail-meta"><span>{{ task.name }}</span><b>{{ latestReport.is_manually_edited?'AI生成 · 人工已审核':'AI智能生成' }}</b><time>{{ new Date(latestReport.created_at).toLocaleString() }}</time></div><pre class="strategy-full-content">{{ latestReport.content }}</pre></article></div>
    <TaskConfigModal v-if="showTaskConfig" :task="task" @close="showTaskConfig=false" @saved="showTaskConfig=false; load()" />
  </div>
</template>
