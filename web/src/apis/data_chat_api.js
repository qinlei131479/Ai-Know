import { apiAdminGet, apiAdminPost } from './base'
import { useUserStore } from '@/stores/user'

/**
 * 数据问答 API
 */
export const dataChatApi = {
  /**
   * 发送数据问答请求（SSE 流式）
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
  getSessions: (limit = 20) => apiAdminGet(`/api/data-chat/sessions?limit=${limit}`),

  /** 获取指定对话的历史记录 */
  getSessionRecords: (chatId) => apiAdminGet(`/api/data-chat/sessions/${encodeURIComponent(chatId)}/records`)
}
