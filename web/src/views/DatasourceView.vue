<template>
  <div class="datasource-container layout-container">
    <HeaderComponent title="数据源管理">
      <template #actions>
        <a-button type="primary" @click="openCreateModal">新建数据源</a-button>
      </template>
    </HeaderComponent>

    <div class="datasource-content">
      <!-- 搜索区 -->
      <div class="search-bar">
        <a-input-search
          v-model:value="searchText"
          placeholder="搜索数据源名称..."
          style="width: 300px"
          allow-clear
        />
      </div>

      <!-- 数据源卡片列表 -->
      <a-spin :spinning="loading">
        <div class="ds-card-grid" v-if="filteredList.length > 0">
          <div
            v-for="ds in filteredList"
            :key="ds.id"
            class="ds-card"
            @click="goDetail(ds.id)"
          >
            <div class="ds-card-header">
              <div class="ds-type-icon">
                <component :is="getTypeIcon(ds.ds_type)" :size="20" />
              </div>
              <div class="ds-info">
                <div class="ds-name">{{ ds.name }}</div>
                <div class="ds-type-label">{{ ds.type_name || ds.ds_type }}</div>
              </div>
              <a-tag :color="getStatusColor(ds.status)" class="ds-status-tag">
                {{ getStatusText(ds.status) }}
              </a-tag>
            </div>
            <div class="ds-card-body">
              <div class="ds-desc" v-if="ds.description">{{ ds.description }}</div>
              <div class="ds-meta">
                <span v-if="ds.table_count">表: {{ ds.table_count }}</span>
                <span>{{ formatTime(ds.created_at) }}</span>
              </div>
            </div>
            <div class="ds-card-actions" @click.stop>
              <a-button size="small" @click="handleSync(ds)">
                <template #icon><RefreshCw :size="14" /></template>
                同步
              </a-button>
              <a-button size="small" @click="handleEdit(ds)">编辑</a-button>
              <a-popconfirm title="确定删除此数据源?" @confirm="handleDelete(ds.id)">
                <a-button size="small" danger>删除</a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>
        <a-empty v-else description="暂无数据源" />
      </a-spin>
    </div>

    <!-- 新建/编辑数据源弹窗 -->
    <DatasourceFormModal
      v-model:open="formModalOpen"
      :editing="editingDs"
      :ds-types="dsTypes"
      @success="handleFormSuccess"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { Database, RefreshCw } from 'lucide-vue-next'
import dayjs from 'dayjs'
import HeaderComponent from '@/components/HeaderComponent.vue'
import DatasourceFormModal from '@/components/datasource/DatasourceFormModal.vue'
import { datasourceApi } from '@/apis/datasource_api'

const router = useRouter()
const loading = ref(false)
const searchText = ref('')
const dsList = ref([])
const dsTypes = ref([])
const formModalOpen = ref(false)
const editingDs = ref(null)

const filteredList = computed(() => {
  if (!searchText.value) return dsList.value
  const kw = searchText.value.toLowerCase()
  return dsList.value.filter(
    (ds) =>
      ds.name.toLowerCase().includes(kw) ||
      ds.ds_type.toLowerCase().includes(kw) ||
      (ds.description || '').toLowerCase().includes(kw)
  )
})

async function loadDatasources() {
  loading.value = true
  try {
    const res = await datasourceApi.list()
    dsList.value = res.datasources || []
  } catch (e) {
    message.error('加载数据源列表失败')
  } finally {
    loading.value = false
  }
}

async function loadTypes() {
  try {
    const res = await datasourceApi.getTypes()
    dsTypes.value = res.types || []
  } catch (e) {
    console.error('加载数据源类型失败', e)
  }
}

function openCreateModal() {
  editingDs.value = null
  formModalOpen.value = true
}

function handleEdit(ds) {
  editingDs.value = ds
  formModalOpen.value = true
}

function handleFormSuccess() {
  formModalOpen.value = false
  loadDatasources()
}

async function handleDelete(dsId) {
  try {
    await datasourceApi.delete(dsId)
    message.success('删除成功')
    loadDatasources()
  } catch (e) {
    message.error('删除失败')
  }
}

async function handleSync(ds) {
  try {
    message.loading({ content: '正在同步表结构...', key: 'sync' })
    await datasourceApi.syncTables(ds.id)
    message.success({ content: '同步完成', key: 'sync' })
    loadDatasources()
  } catch (e) {
    message.error({ content: '同步失败', key: 'sync' })
  }
}

function goDetail(dsId) {
  router.push({ name: 'DatasourceDetailComp', params: { ds_id: dsId } })
}

function getStatusColor(status) {
  const map = { success: 'green', failed: 'red', pending: 'default' }
  return map[status] || 'default'
}

function getStatusText(status) {
  const map = { success: '已连接', failed: '连接失败', pending: '待连接' }
  return map[status] || status
}

function getTypeIcon() {
  return Database
}

function formatTime(t) {
  return t ? dayjs(t).format('YYYY-MM-DD HH:mm') : ''
}

onMounted(() => {
  loadDatasources()
  loadTypes()
})
</script>

<style lang="less" scoped>
.datasource-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.datasource-content {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
}

.search-bar {
  margin-bottom: 20px;
}

.ds-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.ds-card {
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: border-color 0.2s;
  background: var(--main-0);

  &:hover {
    border-color: var(--color-primary-500);
  }
}

.ds-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.ds-type-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--gray-50);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary-500);
  flex-shrink: 0;
}

.ds-info {
  flex: 1;
  min-width: 0;
}

.ds-name {
  font-weight: 500;
  font-size: 15px;
  color: var(--gray-1000);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ds-type-label {
  font-size: 12px;
  color: var(--gray-600);
}

.ds-card-body {
  margin-bottom: 12px;
}

.ds-desc {
  font-size: 13px;
  color: var(--gray-700);
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ds-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--gray-500);
}

.ds-card-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--gray-100);
  padding-top: 10px;
}
</style>
