<template>
  <!-- 外层满足 AppLayout 的 flex column，内层强制左右布局 -->
  <div class="data-chat-wrapper">
    <div class="data-chat-container">
    <!-- 左侧：历史对话列表 -->
    <aside class="data-chat-sider">
      <!-- 搜索框 -->
      <div class="sider-search">
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索对话..."
          size="small"
          @search="handleSearch"
          @pressEnter="handleSearch"
          allow-clear
          @clear="handleClearSearch"
        />
      </div>

      <div class="sider-header">
        <a-button type="text" size="small" class="new-chat-btn" @click="handleNewChat">
          <PlusOutlined />
          <span>新建对话</span>
        </a-button>
      </div>

      <!-- 对话列表（支持滚动加载） -->
      <div class="sider-list" v-if="sessions.length > 0" @scroll="handleSiderScroll">
        <div
          v-for="s in sessions"
          :key="s.chat_id"
          class="session-item"
          :class="{ active: s.chat_id === chatId }"
          @click="loadSession(s)"
        >
          <MessageSquare :size="14" class="session-icon" />
          <span class="session-title" :title="s.title || '新对话'">
            {{ (s.title || '新对话').slice(0, 28) }}{{ (s.title || '').length > 28 ? '...' : '' }}
          </span>
          <a-dropdown trigger="click" placement="bottomRight">
            <template #overlay>
              <a-menu>
                <a-menu-item key="rename" @click="(e) => { e.domEvent?.stopPropagation?.(); openRenameModal(s) }">
                  重命名
                </a-menu-item>
                <a-menu-item key="delete" @click="(e) => { e.domEvent?.stopPropagation?.(); handleDeleteSession(s) }">
                  删除
                </a-menu-item>
              </a-menu>
            </template>
            <EllipsisOutlined class="session-more" @click.stop />
          </a-dropdown>
        </div>
        <!-- 加载更多 -->
        <div v-if="pagination.page < pagination.totalPages" class="sider-load-more" @click="loadMoreSessions">
          <a-button type="link" size="small" :loading="loadingSessions">
            加载更多...
          </a-button>
        </div>
      </div>
      <div class="sider-empty" v-else-if="!loadingSessions">
        <span class="empty-text">暂无对话历史</span>
      </div>
      <a-spin v-if="loadingSessions" class="sider-loading" />
    </aside>

    <a-modal
      v-model:open="renameModalOpen"
      title="重命名会话"
      ok-text="保存"
      cancel-text="取消"
      :confirm-loading="renameSaving"
      @ok="submitRename"
    >
      <a-input v-model:value="renameTitle" placeholder="请输入会话名称" />
    </a-modal>

    <!-- 右侧：当前对话区 -->
    <main class="data-chat-main">
      <!-- 顶部栏：只有模型选择器 -->
      <header class="data-chat-header">
        <div class="header-left">
          <ModelSelectorComponent
            v-if="configStore.config?.model_names"
            :model_spec="selectedModel"
            placeholder="选择模型"
            @select-model="onModelSelect"
          />
        </div>
      </header>

      <!-- 对话主体 -->
      <div class="data-chat-body">
      <!-- 对话区域 -->
      <div class="chat-messages" ref="messagesRef">
        <!-- 空态: 根据问答模式显示不同欢迎内容 -->
        <div v-if="messages.length === 0" class="welcome-area">
          <!-- 未选择问答模式 -->
          <div v-if="!currentQaType" class="welcome-title">
            <MessageSquareMore :size="28" />
            <span>选择下方问答模式开始对话</span>
          </div>

          <!-- 智能问答模式 -->
          <div v-else-if="currentQaType === 'COMMON_QA'" class="welcome-title">
            <Bot :size="28" />
            <span>智能问答</span>
          </div>

          <!-- 数据问答模式 -->
          <div v-else-if="currentQaType === 'DATABASE_QA'">
            <div v-if="currentDsId" class="welcome-area">
              <div class="welcome-title">
                <Database :size="28" />
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
            <div v-else class="welcome-area">
              <div class="welcome-title">
                <Database :size="28" />
                <span>请先选择数据源</span>
              </div>
              <div class="welcome-desc">在下方输入栏点击「数据问答」并选择数据源开始</div>
            </div>
          </div>

          <!-- 表格问答模式 -->
          <div v-else-if="currentQaType === 'FILEDATA_QA'" class="welcome-title">
            <FileSpreadsheet :size="28" />
            <span>表格问答</span>
          </div>

          <!-- 深度问数模式 -->
          <div v-else-if="currentQaType === 'REPORT_QA'" class="welcome-title">
            <Search :size="28" />
            <span>深度问数（开发中）</span>
          </div>
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
        <!-- 表格问答提示 -->
        <div v-if="currentQaType === 'FILEDATA_QA'" class="table-qa-hint">
          表格问答需要上传Excel文件（.xlsx, .xls, .csv）才能发送
        </div>

        <!-- 输入区：圆角卡片容器（参考设计图） -->
        <div class="input-card">
          <div class="input-inner">
            <a-textarea
              v-model:value="inputText"
              :placeholder="getInputPlaceholder()"
              :disabled="streaming"
              :auto-size="{ minRows: 1, maxRows: 4 }"
              class="input-textarea"
              @pressEnter="handleEnter"
            />
          </div>
          <!-- 底部操作栏：问答模式 + 发送 -->
          <div class="input-footer">
            <div class="left-actions">
              <template v-if="currentQaType">
                <!-- 已选模式：Pill，数据问答时带数据源下拉 -->
                <div
                  class="mode-pill"
                  :style="getCurrentChipStyle()"
                >
                  <component :is="getCurrentChip().icon" :size="14" />
                  <span class="mode-label">{{ getCurrentChip().label }}</span>
                  <!-- 数据问答：数据源下拉集成在 Pill 内 -->
                  <template v-if="currentQaType === 'DATABASE_QA' || currentQaType === 'REPORT_QA'">
                    <span class="ds-sep">|</span>
                    <a-dropdown trigger="click" placement="bottomLeft" @openChange="() => {}">
                      <span class="ds-dropdown-trigger">
                        {{ getSelectedDsName() || '选择数据源' }}
                        <ChevronDown :size="12" class="ds-chevron" />
                      </span>
                      <template #overlay>
                        <a-menu
                          :selected-keys="currentDsId ? [currentDsId] : []"
                          @click="({ key }) => handleDsMenuSelect(key)"
                        >
                          <a-menu-item v-for="opt in dsOptions" :key="opt.value">
                            <Database :size="14" class="ds-menu-icon" />
                            {{ opt.label }}
                          </a-menu-item>
                          <a-menu-item v-if="dsOptions.length === 0" disabled key="empty">
                            暂无数据源
                          </a-menu-item>
                        </a-menu>
                      </template>
                    </a-dropdown>
                  </template>
                  <CloseOutlined class="clear-mode-icon" @click.stop="clearQaType" />
                </div>
              </template>

              <!-- 未选模式：四个 Chip，数据问答为下拉选择数据源 -->
              <template v-else>
                <template v-for="chip in qaTypeChips" :key="chip.value">
                  <a-dropdown
                    v-if="chip.value === 'DATABASE_QA'"
                    trigger="click"
                    placement="bottomLeft"
                  >
                    <div class="inner-chip" :style="{ color: chip.color }">
                      <component :is="chip.icon" :size="13" />
                      <span>{{ chip.label }}</span>
                      <ChevronDown :size="12" class="chip-chevron" />
                    </div>
                    <template #overlay>
                      <a-menu @click="({ key }) => selectDataQaWithDs(key)">
                        <a-menu-item v-for="opt in dsOptions" :key="opt.value">
                          <Database :size="14" class="ds-menu-icon" />
                          {{ opt.label }}
                        </a-menu-item>
                        <a-menu-item v-if="dsOptions.length === 0" disabled key="empty">
                          暂无数据源
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                  <div
                    v-else
                    class="inner-chip"
                    :style="{ color: chip.color }"
                    @click="selectQaType(chip.value)"
                  >
                    <component :is="chip.icon" :size="13" />
                    <span>{{ chip.label }}</span>
                  </div>
                </template>
              </template>
            </div>
            <div class="right-actions">
              <a-button
                type="primary"
                shape="circle"
                :disabled="!inputText.trim() || streaming"
                @click="handleSend"
                class="send-btn-icon"
              >
                <template #icon><SendHorizontal :size="16" /></template>
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>
    </main>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { CheckCircleOutlined, LoadingOutlined, ClockCircleOutlined, PlusOutlined, CloseOutlined, EllipsisOutlined } from '@ant-design/icons-vue'
import { MessageSquareMore, Bot, Database, FileSpreadsheet, Search, MessageSquare, ChevronDown, SendHorizontal } from 'lucide-vue-next'
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
const fileList = ref([])  // 表格问答模式使用的文件列表
const messages = ref([])
const streaming = ref(false)
const messagesRef = ref(null)
const recommendations = ref([])
const loadingRecommend = ref(false)
const chatId = ref(null)
const selectedModel = ref('')
const sessions = ref([])
const loadingSessions = ref(false)
const renameModalOpen = ref(false)
const renameSaving = ref(false)
const renameChatId = ref('')
const renameTitle = ref('')

// 问答类型：智能问答、数据问答、表格问答、深度问数
const qaTypeChips = [
  { label: '智能问答', value: 'COMMON_QA', path: '/agent', icon: Bot, color: '#7E6BF2' },
  { label: '数据问答', value: 'DATABASE_QA', path: '/data-chat', icon: MessageSquareMore, color: '#10b981' },
  { label: '表格问答', value: 'FILEDATA_QA', path: '/data-chat', icon: FileSpreadsheet, color: '#f59e0b' },
  { label: '深度问数', value: 'REPORT_QA', path: '/data-chat', icon: Search, color: '#8b5cf6' }
]

// 当前问答模式：默认智能问答
const currentQaType = ref('COMMON_QA')

// 获取当前问答模式的配置
function getCurrentQaMode() {
  // 默认使用智能问答
  return qaTypeChips.find(c => c.value === currentQaType.value) || qaTypeChips[0]
}

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

// Pill 内数据源下拉选择
function handleDsMenuSelect(key) {
  if (key === 'empty') return
  currentDsId.value = key
  handleDsChange()
}

// 未选模式时点击「数据问答」并在下拉中选中某数据源
function selectDataQaWithDs(key) {
  if (key === 'empty') return
  currentQaType.value = 'DATABASE_QA'
  currentDsId.value = key
  messages.value = []
  chatId.value = null
  loadRecommendations()
}

// 分页状态
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
  totalPages: 0
})

// 加载对话历史列表（支持分页）
async function loadSessions(reset = false) {
  if (reset) {
    pagination.page = 1
    sessions.value = []
  }

  loadingSessions.value = true
  try {
    const res = await dataChatApi.getSessions({
      page: pagination.page,
      page_size: pagination.pageSize,
      qa_type: currentQaType.value,
      search: searchText.value || undefined
    })

    if (reset) {
      sessions.value = res.data || []
    } else {
      sessions.value = [...sessions.value, ...(res.data || [])]
    }

    // 更新分页信息
    if (res.pagination) {
      pagination.total = res.pagination.total || 0
      pagination.totalPages = res.pagination.total_pages || 0
    }
  } catch (e) {
    console.error('加载对话列表失败', e)
  } finally {
    loadingSessions.value = false
  }
}

// 加载更多历史记录
async function loadMoreSessions() {
  if (pagination.page >= pagination.totalPages || loadingSessions.value) return
  pagination.page++
  await loadSessions()
}

// 搜索文本
const searchText = ref('')

// 搜索对话
async function handleSearch() {
  await loadSessions(true)
}

// 清除搜索
async function handleClearSearch() {
  searchText.value = ''
  await loadSessions(true)
}

// 新建对话
function handleNewChat() {
  messages.value = []
  chatId.value = null
  recommendations.value = []
  // 清空文件列表
  fileList.value = []
  // 如果是数据问答模式且有选中的数据源，加载推荐问题
  if ((currentQaType.value === 'DATABASE_QA' || currentQaType.value === 'REPORT_QA') && currentDsId.value) {
    loadRecommendations()
  }
}

// 加载指定会话的历史记录
async function loadSession(session) {
  if (session.chat_id === chatId.value) return
  chatId.value = session.chat_id
  if (session.qa_type) {
    currentQaType.value = session.qa_type
  }
  if (session.datasource_id) currentDsId.value = session.datasource_id
  else currentDsId.value = null
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
    if ((currentQaType.value === 'DATABASE_QA' || currentQaType.value === 'REPORT_QA') && currentDsId.value) {
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

// 判断当前是否可以发送消息
const canSendMessage = computed(() => {
  // 未选择模式时，使用默认的智能问答
  if (!currentQaType.value) return true

  switch (currentQaType.value) {
    case 'DATABASE_QA':
      return !!currentDsId.value
    case 'COMMON_QA':
      return true
    default:
      return false
  }
})

// 获取输入框占位符
function getInputPlaceholder() {
  if (streaming.value) return '正在思考...'

  if (!currentQaType.value || currentQaType.value === 'COMMON_QA') {
    return '输入你的问题...'
  }

  switch (currentQaType.value) {
    case 'DATABASE_QA':
      return currentDsId.value ? '输入你的问题...' : '选择数据源后提问'
    case 'FILEDATA_QA':
      return '表格问答功能开发中...'
    case 'REPORT_QA':
      return '深度问数功能开发中...'
    default:
      return '输入你的问题...'
  }
}

// 获取当前选中的问答模式配置
function getCurrentChip() {
  return qaTypeChips.find(c => c.value === currentQaType.value) || qaTypeChips[0]
}

// 获取当前模式的样式
function getCurrentChipStyle() {
  const chip = getCurrentChip()
  return {
    color: chip.color,
    borderColor: chip.color + '30',
    backgroundColor: chip.color + '10'
  }
}

// 获取选中的数据源名称
function getSelectedDsName() {
  if (!currentDsId.value) return ''
  const ds = dsOptions.value.find(d => d.value === currentDsId.value)
  return ds?.label || ''
}

// 选择问答模式
function selectQaType(type) {
  currentQaType.value = type
  // 切换模式时清空对话
  messages.value = []
  chatId.value = null

  // 数据问答模式需要选择数据源后才能发送
  if (type !== 'DATABASE_QA' && type !== 'REPORT_QA') {
    currentDsId.value = null
  }
}

// 清除已选问答模式
function clearQaType() {
  currentQaType.value = null
  currentDsId.value = null
  messages.value = []
  chatId.value = null
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

  // 检查是否可以发送
  const currentMode = getCurrentQaMode()
  const canSend = checkCanSend(currentMode)
  if (!canSend) {
    // 点击发送但条件不满足时也清空输入框
    if (query) inputText.value = ''
    return
  }

  if (!query || streaming.value) return

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

  // 构建请求参数
  const requestData = {
    query,
    qa_type: currentQaType.value,
    chat_id: chatId.value,
    model: selectedModel.value || undefined,
    uuid: generateUUID()
  }

  // 根据问答类型添加不同参数
  if (currentQaType.value === 'DATABASE_QA' || currentQaType.value === 'REPORT_QA') {
    if (!currentDsId.value) {
      aiMsg.error = '请选择数据源'
      streaming.value = false
      return
    }
    requestData.datasource_id = currentDsId.value
  }

  // 添加文件列表（表格问答）
  if (currentQaType.value === 'FILEDATA_QA') {
    requestData.file_list = fileList.value || []
  }

  try {
    const response = await dataChatApi.chat(requestData)

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

function openRenameModal(session) {
  renameChatId.value = session.chat_id
  renameTitle.value = session.title || ''
  renameModalOpen.value = true
}

async function submitRename() {
  const title = (renameTitle.value || '').trim()
  if (!title) {
    message.warning('请输入会话名称')
    return
  }
  renameSaving.value = true
  try {
    await dataChatApi.renameSession(renameChatId.value, title)
    message.success('已重命名')
    renameModalOpen.value = false
    await loadSessions(true)
  } catch (e) {
    message.error(e.message || '重命名失败')
  } finally {
    renameSaving.value = false
  }
}

async function handleDeleteSession(session) {
  try {
    await dataChatApi.deleteSession(session.chat_id)
    message.success('已删除')
    if (chatId.value === session.chat_id) {
      handleNewChat()
    }
    await loadSessions(true)
  } catch (e) {
    message.error(e.message || '删除失败')
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

// 侧边栏滚动事件 - 加载更多历史记录
function handleSiderScroll(e) {
  const target = e.target
  const isNearBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 10
  if (isNearBottom && pagination.page < pagination.totalPages && !loadingSessions.value) {
    loadMoreSessions()
  }
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

// 生成UUID
function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0
    const v = c === 'x' ? r : (r & 0x3 | 0x8)
    return v.toString(16)
  })
}

// 检查是否可以发送
function checkCanSend(mode) {
  if (streaming.value) return false

  const query = inputText.value.trim()
  if (!query) return false

  switch (mode.value) {
    case 'DATABASE_QA':
    case 'REPORT_QA':
      return !!currentDsId.value
    case 'FILEDATA_QA':
      // 表格问答需要文件
      return fileList.value && fileList.value.length > 0
    case 'COMMON_QA':
    default:
      return true
  }
}

// 初始化默认值
async function initDefaults() {
  // 等待 configStore 加载完成
  await configStore.refreshConfig()

  // 加载数据源
  await loadDatasources()

  // 设置默认问答模式为智能问答
  currentQaType.value = 'COMMON_QA'

  // 如果有数据源，自动选中第一个
  if (dsOptions.value.length > 0) {
    currentDsId.value = dsOptions.value[0].value
    // 加载推荐问题
    loadRecommendations()
  }
}

onMounted(() => {
  initDefaults()
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
  padding: 12px;
  border-bottom: 1px solid var(--gray-100);
}

.sider-search {
  padding: 12px 12px 8px;
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

.sider-load-more {
  padding: 12px;
  text-align: center;
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

.session-more {
  flex-shrink: 0;
  color: var(--gray-500);
  padding: 4px;
  border-radius: 6px;
  transition: background 0.2s, color 0.2s;

  &:hover {
    background: var(--gray-100);
    color: var(--gray-700);
  }
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-center {
  display: flex;
  align-items: center;
  gap: 12px;
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

.qa-mode-chips {
  display: flex;
  align-items: center;
  gap: 4px;
}

.mode-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  color: var(--gray-600);
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s;

  &:hover:not(.disabled) {
    background: var(--gray-50);
  }

  &.active {
    font-weight: 500;
  }

  &.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.ds-select {
  width: 160px;
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
  padding: 16px 24px 20px;
  border-top: 1px solid var(--gray-150);
  background: var(--main-0);
}

.table-qa-hint {
  max-width: 780px;
  margin: 0 auto 12px;
  padding: 10px 14px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  font-size: 13px;
  color: #92400e;
}

/* 输入区圆角卡片容器（参考设计图） */
.input-card {
  max-width: 820px;
  margin: 0 auto;
  padding: 14px 16px 14px;
  background: #f6f7f8;
  border-radius: 16px;
}

.input-inner {
  background: #fff;
  border-radius: 10px;
  padding: 2px 4px;
  border: 1px solid transparent;
  transition: border-color 0.2s;

  &:focus-within {
    border-color: var(--color-primary-500);
  }
}

.input-inner :deep(.input-textarea.ant-input),
.input-inner :deep(.ant-input) {
  border: none;
  border-radius: 8px;
  resize: none;
  padding: 10px 12px;
  box-shadow: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.6;
}

.input-inner :deep(.ant-input:focus),
.input-inner :deep(.ant-input:hover) {
  border: none;
  box-shadow: none;
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.left-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.right-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
  border: 1px solid;
  cursor: default;
}

.ds-sep {
  color: inherit;
  opacity: 0.6;
  margin: 0 2px;
}

.ds-dropdown-trigger {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 0 2px;
  border-radius: 4px;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ds-dropdown-trigger:hover {
  opacity: 0.9;
}

.ds-chevron {
  flex-shrink: 0;
  opacity: 0.7;
}

.ds-menu-icon {
  margin-right: 8px;
  vertical-align: -2px;
}

.clear-mode-icon {
  margin-left: 2px;
  font-size: 12px;
  cursor: pointer;
  opacity: 0.6;

  &:hover {
    opacity: 1;
  }
}

.mode-label {
  font-weight: 500;
}

.inner-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 6px;
  border: 1px solid var(--gray-200);
  background: #fff;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: var(--gray-300);
    background: var(--gray-50);
  }
}

.chip-chevron {
  opacity: 0.7;
  margin-left: 2px;
}

.send-btn-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
}

.streaming-placeholder {
  display: flex;
  align-items: center;
  padding: 12px 0;
}
</style>
