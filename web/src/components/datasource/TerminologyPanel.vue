<template>
  <div class="terminology-panel">
    <div class="panel-toolbar">
      <a-button type="primary" size="small" @click="openForm()">新建术语</a-button>
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
      :title="editingItem ? '编辑术语' : '新建术语'"
      @ok="handleSubmit"
      :confirm-loading="submitting"
      destroy-on-close
    >
      <a-form :model="form" layout="vertical" style="margin-top: 16px">
        <a-form-item label="术语名称" required>
          <a-input v-model:value="form.word" placeholder="术语名称" />
        </a-form-item>
        <a-form-item label="术语描述">
          <a-textarea v-model:value="form.description" placeholder="术语解释说明" :rows="3" />
        </a-form-item>
        <a-form-item label="关联当前数据源">
          <a-switch v-model:checked="form.specific_ds" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { terminologyApi } from '@/apis/datasource_api'

const props = defineProps({
  datasourceId: { type: Number, required: true }
})

const loading = ref(false)
const list = ref([])
const formVisible = ref(false)
const editingItem = ref(null)
const submitting = ref(false)

const form = ref({
  word: '',
  description: '',
  specific_ds: false
})

const columns = [
  { title: '术语', dataIndex: 'word', key: 'word', width: 150 },
  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
  { title: '状态', key: 'enabled', width: 80 },
  { title: '操作', key: 'actions', width: 120 }
]

async function loadList() {
  loading.value = true
  try {
    const res = await terminologyApi.list(props.datasourceId)
    list.value = res.terminologies || []
  } catch (e) {
    message.error('加载术语列表失败')
  } finally {
    loading.value = false
  }
}

function openForm(item = null) {
  editingItem.value = item
  if (item) {
    form.value = {
      word: item.word,
      description: item.description || '',
      specific_ds: item.specific_ds || false
    }
  } else {
    form.value = { word: '', description: '', specific_ds: false }
  }
  formVisible.value = true
}

async function handleSubmit() {
  if (!form.value.word) {
    message.warning('请填写术语名称')
    return
  }
  submitting.value = true
  try {
    const payload = {
      ...form.value,
      datasource_ids: form.value.specific_ds ? [props.datasourceId] : null
    }
    if (editingItem.value) {
      await terminologyApi.update(editingItem.value.id, payload)
      message.success('更新成功')
    } else {
      await terminologyApi.create(payload)
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
    await terminologyApi.delete(id)
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
</style>
