import { apiAdminDelete, apiAdminGet, apiAdminPost, apiRequest } from './base'
import { useUserStore } from '@/stores/user'

/**
 * 对话 API - 支持多种问答模式
 *
 * 问答模式 (qa_type):
 * - COMMON_QA: 智能问答（通用大模型对话）
 * - DATABASE_QA: 数据问答（Text2SQL）
 * - FILEDATA_QA: 表格问答（上传Excel文件分析）
 * - REPORT_QA: 深度问数（基于Skill的深度分析）
 */
export const dataChatApi = {
  /**
   * 发送对话请求（SSE 流式）
   * 返回原始 Response 对象，由调用方处理流式数据
   */
  chat: (data) => {
    const userStore = useUserStore()
    return fetch('/api/data-chat/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...userStore.getAuthHeaders()
      },
      body: JSON.stringify(data)
    })
  },

  /** 获取推荐问题 */
  getRecommendations: (data) => apiAdminPost('/api/data-chat/recommend', data),

  /** 获取对话历史列表 */
  getSessions: (params = {}) => {
    const { page = 1, page_size = 20, qa_type, search } = params
    let url = `/api/data-chat/sessions?page=${page}&page_size=${page_size}`
    if (qa_type) url += `&qa_type=${qa_type}`
    if (search) url += `&search=${encodeURIComponent(search)}`
    return apiAdminGet(url)
  },

  /** 获取指定对话的历史记录 */
  getSessionRecords: (chatId) => apiAdminGet(`/api/data-chat/sessions/${encodeURIComponent(chatId)}/records`),

  /** 重命名会话 */
  renameSession: async (chatId, title) => {
    const userStore = useUserStore()
    return apiRequest(
      `/api/data-chat/sessions/${encodeURIComponent(chatId)}`,
      {
        method: 'PATCH',
        headers: { ...userStore.getAuthHeaders() },
        body: JSON.stringify({ title })
      },
      true
    )
  },

  /** 删除会话 */
  deleteSession: (chatId) => apiAdminDelete(`/api/data-chat/sessions/${encodeURIComponent(chatId)}`)
}
