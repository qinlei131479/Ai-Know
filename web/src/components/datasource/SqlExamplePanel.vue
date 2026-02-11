<template>
  <div class="sql-example-panel">
    <div class="panel-toolbar">
      <a-button type="primary" size="small" @click="openForm()">新建 SQL 示例</a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="list"
      :loading="loading"
      :pagination="{ pageSize: 15, size: 'small' }"
      size="small"
      row-key="id"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'sql_text'">
          <code class="sql-preview">{{ truncate(record.sql_text, 80) }}</code>
        </template>
        <template v-if="column.key === 'enabled'">
          <a-tag :color="record.enabled ? 'green' : 'default'">
            {{ record.enabled ? '启用' : '禁用' }}
          </a-tag>
        </template>
        <template v-if="column.key === 'actions'">
          <a-space>
            <a-button size="small" type="link" @click="openForm(record)">编辑</a-button>
            <a-popconfirm title="确定删除?" @confirm="handleDelete(record.id)">
              <a-button size="small" type="link" danger>删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <!-- 新建/编辑弹窗 -->
    <a-modal
      v-model:open="formVisible"
      :title="editingItem ? '编辑 SQL 示例' : '新建 SQL 示例'"
      @ok="handleSubmit"
      :confirm-loading="submitting"
      width="640px"
      destroy-on-close
    >
      <a-form :model="form" layout="vertical" style="margin-top: 16px">
        <a-form-item label="问题描述" required>
          <a-input v-model:value="form.question" placeholder="用户可能提出的问题" />
        </a-form-item>
        <a-form-item label="SQL 语句" required>
          <a-textarea
            v-model:value="form.sql_text"
            placeholder="SELECT ..."
            :rows="6"
            style="font-family: 'JetBrains Mono', 'Fira Code', monospace; font-size: 13px"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { sqlExampleApi } from '@/apis/datasource_api'

const props = defineProps({
  datasourceId: { type: Number, required: true }
})

const loading = ref(false)
const list = ref([])
const formVisible = ref(false)
const editingItem = ref(null)
const submitting = ref(false)

const form = ref({
  question: '',
  sql_text: ''
})

const columns = [
  { title: '问题描述', dataIndex: 'question', key: 'question', width: 240, ellipsis: true },
  { title: 'SQL', key: 'sql_text', ellipsis: true },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '操作', key: 'actions', width: 120 }
]

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

async function loadList() {
  loading.value = true
  try {
    const res = await sqlExampleApi.list(props.datasourceId)
    list.value = res.examples || []
  } catch (e) {
    message.error('加载 SQL 示例列表失败')
  } finally {
    loading.value = false
  }
}

function openForm(item = null) {
  editingItem.value = item
  if (item) {
    form.value = {
      question: item.question,
      sql_text: item.sql_text
    }
  } else {
    form.value = { question: '', sql_text: '' }
  }
  formVisible.value = true
}

async function handleSubmit() {
  if (!form.value.question || !form.value.sql_text) {
    message.warning('请填写必填项')
    return
  }
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      datasource_id: props.datasourceId
    }
    if (editingItem.value) {
      await sqlExampleApi.update(editingItem.value.id, payload)
      message.success('更新成功')
    } else {
      await sqlExampleApi.create(payload)
      message.success('创建成功')
    }
    formVisible.value = false
    loadList()
  } catch (e) {
    message.error(editingItem.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id) {
  try {
    await sqlExampleApi.delete(id)
    message.success('删除成功')
    loadList()
  } catch (e) {
    message.error('删除失败')
  }
}

onMounted(loadList)
</script>

<style lang="less" scoped>
.panel-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.sql-preview {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  color: var(--gray-700);
  background: var(--gray-50);
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
