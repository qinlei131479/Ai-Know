<template>
  <div class="ds-detail-container layout-container">
    <!-- dsId 无效时（如从错误链接进入） -->
    <div v-if="!isDsIdValid" class="ds-detail-error">
      <a-result status="error" title="数据源 ID 无效">
        <template #extra>
          <a-button type="primary" @click="$router.push('/datasource')">返回列表</a-button>
        </template>
      </a-result>
    </div>

    <template v-else>
    <HeaderComponent :title="dsInfo.name || '数据源详情'">
      <template #left>
        <a-button type="text" @click="$router.push('/datasource')">
          <template #icon><ArrowLeft :size="16" /></template>
        </a-button>
      </template>
      <template #behind-title>
        <a-tag :color="getStatusColor(dsInfo.status)">{{ getStatusText(dsInfo.status) }}</a-tag>
      </template>
      <template #actions>
        <a-button @click="handleSync" :loading="syncing">
          <template #icon><RefreshCw :size="14" /></template>
          同步表结构
        </a-button>
      </template>
    </HeaderComponent>

    <div class="ds-detail-body">
      <!-- 左侧：表列表 -->
      <div class="table-list-panel">
        <div class="panel-header">
          <span class="panel-title">数据表</span>
          <a-input-search
            v-model:value="tableSearch"
            placeholder="搜索表名"
            size="small"
            style="width: 160px"
            allow-clear
          />
        </div>
        <div class="table-list">
          <div
            v-for="tbl in filteredTables"
            :key="tbl.id"
            class="table-item"
            :class="{ active: selectedTable?.id === tbl.id }"
            @click="selectTable(tbl)"
          >
            <div class="table-item-main">
              <span class="table-name">{{ tbl.table_name }}</span>
              <a-switch
                size="small"
                :checked="tbl.checked"
                @change="(v) => toggleTable(tbl, v)"
                @click.stop
              />
            </div>
            <div class="table-comment" v-if="tbl.custom_comment || tbl.table_comment">
              {{ tbl.custom_comment || tbl.table_comment }}
            </div>
          </div>
          <a-empty v-if="filteredTables.length === 0" description="暂无数据表" />
        </div>
      </div>

      <!-- 右侧：表详情 / 术语 / SQL 示例 -->
      <div class="table-detail-panel">
        <a-tabs v-model:activeKey="rightTab">
          <!-- 表结构 Tab -->
          <a-tab-pane key="schema" tab="表结构">
            <template v-if="selectedTable">
              <div class="table-info-bar">
                <span class="table-info-name">{{ selectedTable.table_name }}</span>
                <span class="table-info-comment" v-if="selectedTable.table_comment">
                  {{ selectedTable.table_comment }}
                </span>
              </div>
              <a-tabs v-model:activeKey="activeTab" size="small">
                <a-tab-pane key="fields" tab="字段列表">
                  <a-table
                    :columns="fieldColumns"
                    :data-source="fields"
                    :loading="loadingFields"
                    :pagination="false"
                    size="small"
                    row-key="id"
                  >
                    <template #bodyCell="{ column, record }">
                      <template v-if="column.key === 'checked'">
                        <a-switch
                          size="small"
                          :checked="record.checked"
                          @change="(v) => toggleField(record, v)"
                        />
                      </template>
                      <template v-if="column.key === 'custom_comment'">
                        <a-input
                          v-model:value="record.custom_comment"
                          size="small"
                          placeholder="自定义注释"
                          @blur="updateFieldComment(record)"
                        />
                      </template>
                    </template>
                  </a-table>
                </a-tab-pane>
                <a-tab-pane key="preview" tab="数据预览">
                  <div class="preview-header">
                    <span>显示前 100 条数据</span>
                    <a-button
                      size="small"
                      @click="loadPreview"
                      :loading="loadingPreview"
                    >
                      <template #icon><RefreshCw :size="12" /></template>
                      刷新
                    </a-button>
                  </div>
                  <a-spin :spinning="loadingPreview">
                    <a-table
                      v-if="previewData.length > 0"
                      :columns="previewColumns"
                      :data-source="previewData"
                      :pagination="{ pageSize: 20, size: 'small', showTotal: (t) => `共 ${t} 条` }"
                      size="small"
                      :scroll="{ x: 'max-content' }"
                    />
                    <a-empty
                      v-else-if="!loadingPreview && previewLoaded"
                      description="无数据"
                    />
                  </a-spin>
                </a-tab-pane>
              </a-tabs>
            </template>
            <a-empty v-else description="请从左侧选择一张表" />
          </a-tab-pane>

          <!-- 术语管理 Tab -->
          <a-tab-pane key="terminology" tab="术语管理">
            <TerminologyPanel :datasource-id="dsId" />
          </a-tab-pane>

          <!-- SQL 示例 Tab -->
          <a-tab-pane key="sql-example" tab="SQL 示例">
            <SqlExamplePanel :datasource-id="dsId" />
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import { ArrowLeft, RefreshCw } from 'lucide-vue-next'
import HeaderComponent from '@/components/HeaderComponent.vue'
import TerminologyPanel from '@/components/datasource/TerminologyPanel.vue'
import SqlExamplePanel from '@/components/datasource/SqlExamplePanel.vue'
import { datasourceApi } from '@/apis/datasource_api'

const route = useRoute()
const dsId = computed(() => Number(route.params.ds_id))

/** ds_id 有效（存在且为合法数字） */
const isDsIdValid = computed(() => {
  const id = dsId.value
  return Number.isFinite(id) && id > 0
})

const dsInfo = ref({})
const tables = ref([])
const tableSearch = ref('')
const selectedTable = ref(null)
const rightTab = ref('schema')
const activeTab = ref('fields')
const syncing = ref(false)

// 字段
const fields = ref([])
const loadingFields = ref(false)

// 预览
const previewData = ref([])
const previewColumns = ref([])
const loadingPreview = ref(false)
const previewLoaded = ref(false)

const filteredTables = computed(() => {
  if (!tableSearch.value) return tables.value
  const kw = tableSearch.value.toLowerCase()
  return tables.value.filter(
    (t) =>
      t.table_name.toLowerCase().includes(kw) ||
      (t.table_comment || '').toLowerCase().includes(kw) ||
      (t.custom_comment || '').toLowerCase().includes(kw)
  )
})

const fieldColumns = [
  { title: '字段名', dataIndex: 'field_name', key: 'field_name', width: 180 },
  { title: '类型', dataIndex: 'field_type', key: 'field_type', width: 120 },
  { title: '注释', dataIndex: 'field_comment', key: 'field_comment', width: 160, ellipsis: true },
  { title: '自定义注释', key: 'custom_comment', width: 200 },
  { title: '启用', key: 'checked', width: 80 }
]

async function loadDsInfo() {
  if (!isDsIdValid.value) return
  try {
    dsInfo.value = await datasourceApi.getDetail(dsId.value)
  } catch (e) {
    message.error('加载数据源详情失败')
  }
}

async function loadTables() {
  if (!isDsIdValid.value) return
  try {
    const res = await datasourceApi.getTables(dsId.value)
    tables.value = res.tables || []
    if (tables.value.length > 0 && !selectedTable.value) {
      selectTable(tables.value[0])
    }
  } catch (e) {
    message.error('加载表列表失败')
  }
}

async function selectTable(tbl) {
  selectedTable.value = tbl
  activeTab.value = 'fields'
  previewData.value = []
  previewColumns.value = []
  previewLoaded.value = false
  await loadFields(tbl.id)
}

async function loadFields(tableId) {
  loadingFields.value = true
  try {
    const res = await datasourceApi.getFields(tableId)
    fields.value = res.fields || []
  } catch (e) {
    message.error('加载字段失败')
  } finally {
    loadingFields.value = false
  }
}

async function loadPreview() {
  if (!selectedTable.value) return
  loadingPreview.value = true
  try {
    const res = await datasourceApi.previewTable(dsId.value, selectedTable.value.table_name)
    const data = res.data || []
    previewData.value = data.map((row, idx) => ({ ...row, _rowKey: idx }))
    previewLoaded.value = true
    if (data.length > 0) {
      previewColumns.value = Object.keys(data[0]).map((k) => ({
        title: k,
        dataIndex: k,
        key: k,
        width: 150,
        ellipsis: true
      }))
    } else {
      previewColumns.value = []
    }
  } catch (e) {
    message.error('加载预览失败')
    previewLoaded.value = true
  } finally {
    loadingPreview.value = false
  }
}

// 切换到预览标签时自动加载数据
watch(activeTab, (newVal) => {
  if (newVal === 'preview' && selectedTable.value && !previewLoaded.value) {
    loadPreview()
  }
})

async function toggleTable(tbl, checked) {
  try {
    await datasourceApi.updateTable(tbl.id, { checked })
    tbl.checked = checked
  } catch (e) {
    message.error('更新失败')
  }
}

async function toggleField(field, checked) {
  try {
    await datasourceApi.updateField(field.id, { checked })
    field.checked = checked
  } catch (e) {
    message.error('更新失败')
  }
}

async function updateFieldComment(field) {
  try {
    await datasourceApi.updateField(field.id, { custom_comment: field.custom_comment })
  } catch (e) {
    message.error('更新注释失败')
  }
}

async function handleSync() {
  syncing.value = true
  try {
    await datasourceApi.syncTables(dsId.value)
    message.success('同步完成')
    await loadTables()
    // 重新选中当前表
    if (selectedTable.value) {
      const refreshed = tables.value.find((t) => t.id === selectedTable.value.id)
      if (refreshed) {
        selectTable(refreshed)
      }
    }
  } catch (e) {
    message.error('同步失败')
  } finally {
    syncing.value = false
  }
}

function getStatusColor(status) {
  const map = { success: 'green', failed: 'red', pending: 'default' }
  return map[status] || 'default'
}

function getStatusText(status) {
  const map = { success: '已连接', failed: '连接失败', pending: '待连接' }
  return map[status] || status || '未知'
}

watch(dsId, () => {
  selectedTable.value = null
  loadDsInfo()
  loadTables()
})

onMounted(() => {
  loadDsInfo()
  loadTables()
})
</script>

<style lang="less" scoped>
.ds-detail-container {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.ds-detail-body {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.ds-detail-error {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.table-list-panel {
  width: 280px;
  flex-shrink: 0;
  border-right: 1px solid var(--gray-150);
  display: flex;
  flex-direction: column;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--gray-100);
}

.panel-title {
  font-weight: 500;
  font-size: 14px;
  color: var(--gray-900);
}

.table-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.table-item {
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-bottom: 2px;

  &:hover {
    background-color: var(--gray-50);
  }

  &.active {
    background-color: var(--color-primary-50);
  }
}

.table-item-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.table-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--gray-900);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-comment {
  font-size: 12px;
  color: var(--gray-600);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-detail-panel {
  flex: 1;
  padding: 16px 20px;
  overflow-y: auto;

  &.empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.table-info-bar {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--gray-50);
  border-radius: 6px;

  .table-info-name {
    font-weight: 600;
    font-size: 14px;
    color: var(--gray-900);
  }

  .table-info-comment {
    font-size: 13px;
    color: var(--gray-600);
    margin-left: 12px;
  }
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--gray-600);
}
</style>
