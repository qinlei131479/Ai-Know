<template>
  <!-- 外层满足 AppLayout 的 flex column，内层强制左右布局 -->
  <div class="data-chat-wrapper">
    <div class="data-chat-container">
    <!-- 左侧：历史对话列表 -->
    <aside class="data-chat-sider">
      <div class="sider-header">
        <a-button type="text" size="small" class="new-chat-btn" @click="handleNewChat">
          <PlusOutlined />
          <span>新建对话</span>
        </a-button>
      </div>
      <div class="sider-list" v-if="sessions.length > 0">
        <div
          v-for="s in sessions"
          :key="s.chat_id"
          class="session-item"
          :class="{ active: s.chat_id === chatId }"
          @click="loadSession(s)"
        >
          <MessageSquare :size="14" class="session-icon" />
          <span class="session-title" :title="s.first_question || '新对话'">
            {{ (s.first_question || '新对话').slice(0, 28) }}{{ (s.first_question || '').length > 28 ? '...' : '' }}
          </span>
        </div>
      </div>
      <div class="sider-empty" v-else-if="!loadingSessions">
        <span class="empty-text">暂无对话历史</span>
      </div>
      <a-spin v-if="loadingSessions" class="sider-loading" />
    </aside>

    <!-- 右侧：当前对话区 -->
    <main class="data-chat-main">
      <!-- 顶部栏：数据源、模型、问答类型同一行 -->
      <header class="data-chat-header">
        <div class="header-toolbar">
          <h1 class="header-title">数据问答</h1>
          <a-select
            v-model:value="currentDsId"
            placeholder="选择数据源"
            class="header-select"
            :options="dsOptions"
            @change="handleDsChange"
          />
          <ModelSelectorComponent
            v-if="configStore.config?.model_names"
            :model_spec="selectedModel"
            placeholder="选择模型"
            @select-model="onModelSelect"
          />
          <div class="qa-type-chips">
            <template v-for="chip in qaTypeChips" :key="chip.value">
              <router-link
                v-if="chip.value !== 'FILEDATA_QA' && chip.value !== 'REPORT_QA'"
                :to="chip.path"
                class="qa-chip"
                :class="{ active: chip.value === 'DATABASE_QA' }"
              >
                <component :is="chip.icon" :size="14" />
                <span>{{ chip.label }}</span>
              </router-link>
              <a-tooltip v-else title="敬请期待">
                <span class="qa-chip disabled">
                  <component :is="chip.icon" :size="14" />
                  <span>{{ chip.label }}</span>
                </span>
              </a-tooltip>
            </template>
          </div>
        </div>
      </header>

      <!-- 对话主体 -->
      <div class="data-chat-body">
      <!-- 对话区域 -->
      <div class="chat-messages" ref="messagesRef">
        <!-- 空态: 推荐问题 -->
        <div v-if="messages.length === 0 && currentDsId" class="welcome-area">
          <div class="welcome-title">
            <MessageSquareMore :size="28" />
            <span>向数据库提问</span>
          </div>
          <div class="welcome-desc">基于 Text2SQL 技术，将自然语言转换为 SQL 查询</div>
          <div class="recommend-list" v-if="recommendations.length > 0">
            <div
              v-for="(q, i) in recommendations"
              :key="i"
              class="recommend-item"
              @click="sendQuestion(q)"
            >
              {{ q }}
            </div>
          </div>
          <a-spin v-else-if="loadingRecommend" />
        </div>

        <div v-if="messages.length === 0 && !currentDsId" class="welcome-area">
          <div class="welcome-title">
            <MessageSquareMore :size="28" />
            <span>请先选择数据源</span>
          </div>
          <div class="welcome-desc">从上方下拉框选择一个已配置的数据源开始</div>
        </div>

        <!-- 消息列表：使用 msgKey 确保数据更新时强制重渲染 -->
        <div v-for="(msg, idx) in messages" :key="`${idx}-${msg.msgKey ?? 0}`" class="message-wrapper">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="message user-message">
            <div class="message-content">{{ msg.content }}</div>
          </div>

          <!-- AI 回复 -->
          <div v-else class="message ai-message">
            <!-- 步骤进度 -->
            <div class="step-progress" v-if="msg.steps && msg.steps.length > 0">
              <div v-for="(step, si) in msg.steps" :key="si" class="step-item" :class="step.status">
                <CheckCircleOutlined v-if="step.status === 'done'" class="step-icon done" />
                <LoadingOutlined v-else-if="step.status === 'running'" class="step-icon running" />
                <ClockCircleOutlined v-else class="step-icon pending" />
                <span class="step-label">{{ step.label }}</span>
              </div>
            </div>

            <!-- 摘要（优先展示） -->
            <div class="summary-block" v-if="msg.summary" v-html="renderMarkdown(msg.summary)"></div>

            <!-- SQL 展示 -->
            <div class="sql-block" v-if="msg.sql">
              <div class="sql-header">
                <span>生成的 SQL</span>
                <a-button size="small" type="text" @click="copySql(msg.sql)">复制</a-button>
              </div>
              <pre class="sql-code"><code>{{ msg.sql }}</code></pre>
            </div>

            <!-- 图表/表格（有 renderData 时显示） -->
            <div class="chart-block" v-if="msg.renderData && msg.renderData.data?.length > 0">
              <DataChatChart :config="msg.chartConfig || {}" :data="msg.renderData" />
            </div>

            <!-- 独立表格兜底（无 renderData 但有 tableData 时） -->
            <div class="data-table-block" v-else-if="msg.tableData && msg.tableData.length > 0">
              <a-table
                :columns="getTableColumns(msg.tableData)"
                :data-source="msg.tableData.slice(0, 100)"
                :pagination="{ pageSize: 10, size: 'small' }"
                size="small"
                :scroll="{ x: 'max-content' }"
              />
              <div class="table-tip" v-if="msg.tableData.length > 100">
                仅显示前 100 条，共 {{ msg.tableData.length }} 条
              </div>
            </div>

            <!-- 推荐问题 -->
            <div class="recommend-follow" v-if="msg.recommended && msg.recommended.length > 0">
              <div class="recommend-follow-title">你可能还想问:</div>
              <div class="recommend-follow-list">
                <span
                  v-for="(q, qi) in msg.recommended"
                  :key="qi"
                  class="follow-item"
                  @click="sendQuestion(q)"
                >
                  {{ q }}
                </span>
              </div>
            </div>

            <!-- 错误信息 -->
            <div class="error-block" v-if="msg.error">
              <a-alert :message="msg.error" type="error" show-icon />
            </div>
          </div>
        </div>

        <!-- 流式输出中占位 -->
        <div v-if="streaming" class="message ai-message streaming-placeholder">
          <a-spin size="small" /> <span style="margin-left: 8px; color: var(--gray-600)">正在分析...</span>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-input-area">
        <div class="input-wrapper">
          <a-textarea
            v-model:value="inputText"
            :placeholder="currentDsId ? '输入你的问题...' : '请先选择数据源'"
            :disabled="!currentDsId || streaming"
            :auto-size="{ minRows: 1, maxRows: 4 }"
            @pressEnter="handleEnter"
          />
          <a-button
            type="primary"
            :disabled="!inputText.trim() || !currentDsId || streaming"
            @click="handleSend"
            class="send-btn"
          >
            发送
          </a-button>
        </div>
      </div>
    </div>
    </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { CheckCircleOutlined, LoadingOutlined, ClockCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import { MessageSquareMore, Bot, Database, FileSpreadsheet, Search, MessageSquare } from 'lucide-vue-next'
import { marked } from 'marked'
import DataChatChart from '@/components/datasource/DataChatChart.vue'
import ModelSelectorComponent from '@/components/ModelSelectorComponent.vue'
import { useConfigStore } from '@/stores/config'
import { datasourceApi } from '@/apis/datasource_api'
import { dataChatApi } from '@/apis/data_chat_api'

const configStore = useConfigStore()
const currentDsId = ref(null)
const dsOptions = ref([])
const inputText = ref('')
const messages = ref([])
const streaming = ref(false)
const messagesRef = ref(null)
const recommendations = ref([])
const loadingRecommend = ref(false)
const chatId = ref(null)
const selectedModel = ref('')
const sessions = ref([])
const loadingSessions = ref(false)

// 问答类型：智能问答、数据问答、表格问答、深度问数
const qaTypeChips = [
  { label: '智能问答', value: 'COMMON_QA', path: '/agent', icon: Bot },
  { label: '数据问答', value: 'DATABASE_QA', path: '/data-chat', icon: MessageSquareMore },
  { label: '表格问答', value: 'FILEDATA_QA', path: '/data-chat', icon: FileSpreadsheet },
  { label: '深度问数', value: 'REPORT_QA', path: '/data-chat', icon: Search }
]

// 加载数据源列表
async function loadDatasources() {
  try {
    const res = await datasourceApi.list()
    const list = res.datasources || []
    dsOptions.value = list
      .filter((ds) => ds.status === 'success')
      .map((ds) => ({ label: ds.name, value: ds.id }))
  } catch (e) {
    console.error('加载数据源失败', e)
  }
}

// 数据源切换
async function handleDsChange() {
  messages.value = []
  chatId.value = null
  recommendations.value = []
  if (currentDsId.value) {
    loadRecommendations()
  }
}

// 加载对话历史列表
async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await dataChatApi.getSessions(30)
    sessions.value = res.data || []
  } catch (e) {
    console.error('加载对话列表失败', e)
  } finally {
    loadingSessions.value = false
  }
}

// 新建对话
function handleNewChat() {
  messages.value = []
  chatId.value = null
  recommendations.value = []
  if (currentDsId.value) {
    loadRecommendations()
  }
}

// 加载指定会话的历史记录
async function loadSession(session) {
  if (session.chat_id === chatId.value) return
  chatId.value = session.chat_id
  if (session.datasource_id) {
    currentDsId.value = session.datasource_id
  }
  messages.value = []
  try {
    const res = await dataChatApi.getSessionRecords(session.chat_id)
    const records = res.data || []
    for (const r of records) {
      messages.value.push({ role: 'user', content: r.question })
      const aiMsg = {
        role: 'ai',
        msgKey: 0,
        steps: [],
        sql: r.sql_statement || null,
        chartConfig: r.chart_config || null,
        renderData: r.query_result || null,
        tableData: r.query_result?.data || null,
        summary: r.answer || null,
        recommended: null,
        error: null
      }
      messages.value.push(aiMsg)
    }
    if (currentDsId.value) {
      loadRecommendations()
    }
  } catch (e) {
    console.error('加载会话记录失败', e)
    message.error('加载会话记录失败')
  }
}

// 模型选择
function onModelSelect(spec) {
  selectedModel.value = spec || ''
}

// 获取推荐问题
async function loadRecommendations() {
  loadingRecommend.value = true
  try {
    const res = await dataChatApi.getRecommendations({
      datasource_id: currentDsId.value,
      question: ''
    })
    recommendations.value = res.data || []
  } catch (e) {
    console.error('获取推荐问题失败', e)
  } finally {
    loadingRecommend.value = false
  }
}

function handleEnter(e) {
  if (e.shiftKey) return // Shift+Enter 换行
  e.preventDefault()
  handleSend()
}

function sendQuestion(q) {
  inputText.value = q
  handleSend()
}

async function handleSend() {
  const query = inputText.value.trim()
  if (!query || !currentDsId.value || streaming.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: query })
  inputText.value = ''

  // 使用 reactive 使流式更新实时触发视图渲染
  const aiMsg = reactive({
    role: 'ai',
    msgKey: 0,
    steps: [],
    sql: null,
    chartConfig: null,
    renderData: null,
    tableData: null,
    summary: null,
    recommended: null,
    error: null
  })
  messages.value.push(aiMsg)
  streaming.value = true
  scrollToBottom()

  try {
    const response = await dataChatApi.chat({
      query,
      datasource_id: currentDsId.value,
      chat_id: chatId.value,
      model: selectedModel.value || undefined
    })

    if (!response.ok) {
      aiMsg.error = `请求失败: ${response.status}`
      streaming.value = false
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const prefix = 'data:'
        if (!line.startsWith(prefix)) continue
        const dataStr = line.slice(prefix.length).trim()
        if (!dataStr || dataStr === '[DONE]') continue

        try {
          const evt = JSON.parse(dataStr)
          if (evt.dataType === 'stream_end' && evt.data?.chat_id) {
            chatId.value = evt.data.chat_id
            loadSessions()
          } else {
            processSSEEvent(aiMsg, evt)
            // 每处理一个事件后让出主线程，使 Vue 能实时渲染
            await new Promise((r) => setTimeout(r, 0))
          }
          scrollToBottom()
        } catch (e) {
          // 忽略解析失败的行
        }
      }
    }
  } catch (e) {
    aiMsg.error = '请求异常: ' + (e.message || '未知错误')
  } finally {
    streaming.value = false
    scrollToBottom()
  }
}

function processSSEEvent(msg, evt) {
  // 后端 SSE 格式: {"dataType": "...", "data": {...}}
  const dataType = evt.dataType
  const data = evt.data

  switch (dataType) {
    case 'step_progress':
      // 步骤进度: {step, stepName, status: "start"|"complete", progressId}
      if (data.status === 'start') {
        msg.steps.push({ label: data.stepName || data.step, status: 'running' })
      } else if (data.status === 'complete') {
        const step = msg.steps.find((s) => s.label === (data.stepName || data.step))
        if (step) step.status = 'done'
      }
      break

    case 'answer':
      // 文本回复或错误: {content, messageType?}
      if (data.messageType === 'error') {
        msg.error = data.content
      } else {
        msg.summary = (msg.summary || '') + (data.content || '')
      }
      break

    case 'bus_data':
      // 业务数据: 图表数据 或 推荐问题
      if (data.chart_config != null) msg.chartConfig = data.chart_config
      if (data.render_data != null) {
        msg.renderData = data.render_data
        msg.tableData = data.render_data?.data ?? null
      }
      if (data.sql) msg.sql = data.sql
      if (data.recommended_questions) {
        msg.recommended = data.recommended_questions
      }
      break

    case 'stream_end':
      // 流结束信号，chat_id 已在主循环中处理
      break
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function copySql(sql) {
  navigator.clipboard.writeText(sql)
  message.success('已复制 SQL')
}

function getTableColumns(data) {
  if (!data || data.length === 0) return []
  return Object.keys(data[0]).map((k) => ({
    title: k,
    dataIndex: k,
    key: k,
    width: 150,
    ellipsis: true
  }))
}

function renderMarkdown(text) {
  if (!text) return ''
  return marked(text, { breaks: true })
}

onMounted(() => {
  configStore.refreshConfig()
  loadDatasources()
  loadSessions()
})
</script>

<style lang="less" scoped>
.data-chat-wrapper {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.data-chat-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: row;
  flex-wrap: nowrap;
  overflow: hidden;
  background: var(--gray-25);
}

.data-chat-sider {
  width: 260px;
  min-width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--gray-150);
  background: var(--main-0);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sider-header {
  padding: 16px;
  border-bottom: 1px solid var(--gray-100);
}

.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  border: 1px dashed var(--gray-200);
  border-radius: 8px;
  color: var(--color-primary-500);
  font-size: 14px;
  transition: border-color 0.2s, background 0.2s;

  &:hover {
    border-color: var(--color-primary-500);
    background: var(--color-primary-50);
  }
}

.sider-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  margin: 0 8px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--gray-800);
  font-size: 13px;
  line-height: 1.4;
  transition: background 0.2s;

  &:hover {
    background: var(--gray-50);
  }

  &.active {
    background: var(--color-primary-50);
    color: var(--color-primary-700);
  }
}

.session-icon {
  flex-shrink: 0;
  color: var(--gray-900);
}

.session-item.active .session-icon {
  color: var(--color-primary-500);
}

.session-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sider-empty,
.sider-loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.empty-text {
  font-size: 13px;
  color: var(--gray-500);
}

.data-chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  background: var(--main-0);
}

.data-chat-header {
  padding: 12px 20px;
  border-bottom: 1px solid var(--gray-150);
  background: var(--main-0);
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-2000);
  margin-right: 8px;
}

.header-select {
  width: 180px;
}

.qa-type-chips {
  display: flex;
  align-items: center;
  gap: 4px;
}

.qa-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  color: var(--gray-600);
  border-radius: 8px;
  text-decoration: none;
  transition: all 0.2s;

  &:hover:not(.disabled) {
    background: var(--gray-50);
    color: var(--color-primary-500);
  }

  &.active {
    background: var(--color-primary-50);
    color: var(--color-primary-700);
  }

  &.disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
}

.data-chat-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  max-width: 780px;
  width: 100%;
  margin: 0 auto;
}

.welcome-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 48px 60px;
}

.welcome-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 24px;
  font-weight: 500;
  color: var(--gray-900);
  margin-bottom: 12px;
}

.welcome-desc {
  font-size: 14px;
  color: var(--gray-600);
  margin-bottom: 32px;
}

.recommend-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 560px;
}

.recommend-item {
  padding: 10px 18px;
  border: 1px solid var(--gray-200);
  border-radius: 20px;
  font-size: 13px;
  color: var(--gray-800);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--color-primary-500);
    color: var(--color-primary-500);
    background: var(--color-primary-50);
  }
}

.message-wrapper {
  margin-bottom: 24px;
}

.message {
  &.user-message {
    display: flex;
    justify-content: flex-end;

    .message-content {
      background: var(--color-primary-500);
      color: #fff;
      padding: 12px 18px;
      border-radius: 12px 12px 4px 12px;
      max-width: 75%;
      font-size: 14px;
      line-height: 1.6;
      word-break: break-word;
    }
  }

  &.ai-message {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
}

.step-progress {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--gray-600);

  &.done {
    color: var(--color-success-500);
  }

  &.running {
    color: var(--color-primary-500);
  }
}

.step-icon {
  font-size: 14px;
}

.sql-block {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  overflow: hidden;
  background: var(--main-0);
}

.sql-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: var(--gray-50);
  font-size: 12px;
  color: var(--gray-700);
  border-bottom: 1px solid var(--gray-150);
}

.sql-code {
  padding: 14px 16px;
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  background: var(--main-0);

  code {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }
}

.chart-block {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  padding: 20px;
  background: var(--main-0);
}

.data-table-block {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  overflow: hidden;
  background: var(--main-0);
}

.table-tip {
  text-align: center;
  font-size: 12px;
  color: var(--gray-500);
  padding: 8px;
}

.summary-block {
  font-size: 14px;
  line-height: 1.8;
  color: var(--gray-900);

  :deep(p) {
    margin: 0 0 10px;
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 20px;
  }
}

.recommend-follow {
  margin-top: 8px;
}

.recommend-follow-title {
  font-size: 12px;
  color: var(--gray-500);
  margin-bottom: 8px;
}

.recommend-follow-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.follow-item {
  padding: 6px 14px;
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  font-size: 12px;
  color: var(--gray-700);
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--color-primary-500);
    color: var(--color-primary-500);
  }
}

.error-block {
  max-width: 100%;
}

.chat-input-area {
  padding: 20px 24px 24px;
  border-top: 1px solid var(--gray-150);
  background: var(--main-0);
}

.input-wrapper {
  max-width: 780px;
  margin: 0 auto;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-wrapper :deep(.ant-input) {
  border-radius: 8px;
  resize: none;
}

.send-btn {
  flex-shrink: 0;
  height: 36px;
  border-radius: 8px;
}

.streaming-placeholder {
  display: flex;
  align-items: center;
  padding: 12px 0;
}
</style>
