<template>
  <a-modal
    :open="open"
    :title="editing ? '编辑数据源' : '新建数据源'"
    :width="currentStep === 0 ? 640 : 800"
    :footer="null"
    @cancel="handleCancel"
    destroy-on-close
  >
    <a-steps :current="currentStep" size="small" style="margin-bottom: 24px">
      <a-step title="连接配置" />
      <a-step title="选择数据表" />
    </a-steps>

    <!-- Step 1: 连接配置 -->
    <div v-show="currentStep === 0">
      <a-form :model="form" layout="vertical" style="margin-top: 16px">
        <a-form-item label="数据源名称" required>
          <a-input v-model:value="form.name" placeholder="请输入数据源名称" />
        </a-form-item>

        <a-form-item label="数据源类型" required>
          <a-select
            v-model:value="form.ds_type"
            placeholder="请选择类型"
            :disabled="!!editing"
            @change="handleTypeChange"
          >
            <a-select-option v-for="t in dsTypes" :key="t.code" :value="t.code">
              {{ t.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" placeholder="数据源描述" :rows="2" />
        </a-form-item>

        <!-- 连接配置 -->
        <a-divider>连接配置</a-divider>

        <a-row :gutter="16">
          <a-col :span="16">
            <a-form-item label="主机地址" required>
              <a-input v-model:value="form.configuration.host" placeholder="localhost" />
            </a-form-item>
          </a-col>
          <a-col :span="8">
            <a-form-item label="端口" required>
              <a-input-number
                v-model:value="form.configuration.port"
                :min="1"
                :max="65535"
                style="width: 100%"
                :placeholder="getDefaultPort()"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="用户名" required>
              <a-input v-model:value="form.configuration.username" placeholder="用户名" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="密码" required>
              <a-input-password v-model:value="form.configuration.password" placeholder="密码" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item label="数据库名" required>
          <a-input v-model:value="form.configuration.database" placeholder="数据库名称" />
        </a-form-item>

        <a-form-item label="Schema" v-if="showSchema">
          <a-input v-model:value="form.configuration.schema" placeholder="Schema (可选)" />
        </a-form-item>

        <!-- 连接测试按钮 -->
        <a-form-item>
          <a-button :loading="testing" @click="testConnection">
            <template #icon><CheckCircleOutlined /></template>
            测试连接
          </a-button>
          <span
            v-if="testResult !== null"
            :style="{
              marginLeft: '12px',
              color: testResult ? 'var(--color-success-500)' : 'var(--color-error-500)'
            }"
          >
            {{ testResult ? '连接成功' : '连接失败' }}
          </span>
        </a-form-item>
      </a-form>

      <div style="text-align: right; margin-top: 16px">
        <a-button @click="handleCancel" style="margin-right: 8px">取消</a-button>
        <a-button type="primary" :loading="fetchingTables" @click="handleNext">
          下一步
        </a-button>
      </div>
    </div>

    <!-- Step 2: 选择数据表 -->
    <div v-show="currentStep === 1">
      <div class="table-select-header">
        <a-checkbox
          :checked="isAllSelected"
          :indeterminate="isIndeterminate"
          @change="toggleSelectAll"
        >
          全选
        </a-checkbox>
        <span class="table-select-count">
          已选择 {{ selectedTables.length }} / {{ remoteTableList.length }} 个表
        </span>
      </div>

      <a-spin :spinning="fetchingTables">
        <div class="table-select-grid">
          <a-checkbox-group v-model:value="selectedTables" style="width: 100%">
            <a-row :gutter="[12, 8]">
              <a-col :span="12" v-for="t in remoteTableList" :key="t.tableName">
                <a-checkbox :value="t.tableName">
                  <span class="table-select-name">{{ t.tableName }}</span>
                  <span class="table-select-comment" v-if="t.tableComment">
                    ({{ t.tableComment }})
                  </span>
                </a-checkbox>
              </a-col>
            </a-row>
          </a-checkbox-group>
          <a-empty v-if="!fetchingTables && remoteTableList.length === 0" description="未获取到表" />
        </div>
      </a-spin>

      <div style="text-align: right; margin-top: 16px">
        <a-button @click="currentStep = 0" style="margin-right: 8px">上一步</a-button>
        <a-button type="primary" :loading="submitting" @click="handleSubmit">
          {{ editing ? '保存' : '创建' }}
        </a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { message } from 'ant-design-vue'
import { CheckCircleOutlined } from '@ant-design/icons-vue'
import { datasourceApi } from '@/apis/datasource_api'

const props = defineProps({
  open: Boolean,
  editing: { type: Object, default: null },
  dsTypes: { type: Array, default: () => [] }
})

const emit = defineEmits(['update:open', 'success'])

const currentStep = ref(0)
const submitting = ref(false)
const testing = ref(false)
const testResult = ref(null)
const fetchingTables = ref(false)

// 远程表列表 & 用户选中的表
const remoteTableList = ref([])
const selectedTables = ref([])

const defaultForm = () => ({
  name: '',
  ds_type: '',
  description: '',
  configuration: {
    host: '',
    port: null,
    username: '',
    password: '',
    database: '',
    schema: ''
  }
})

const form = reactive(defaultForm())

const showSchema = computed(() => {
  return ['pg', 'oracle', 'sqlServer', 'kingbase'].includes(form.ds_type)
})

const isAllSelected = computed(
  () => remoteTableList.value.length > 0 && selectedTables.value.length === remoteTableList.value.length
)
const isIndeterminate = computed(
  () => selectedTables.value.length > 0 && selectedTables.value.length < remoteTableList.value.length
)

const defaultPorts = {
  mysql: 3306,
  pg: 5432,
  oracle: 1521,
  sqlServer: 1433,
  ck: 8123,
  dm: 5236,
  doris: 9030,
  starrocks: 9030,
  kingbase: 54321,
  redshift: 5439
}

function getDefaultPort() {
  return String(defaultPorts[form.ds_type] || 3306)
}

function handleTypeChange(type) {
  if (defaultPorts[type] && !form.configuration.port) {
    form.configuration.port = defaultPorts[type]
  }
}

// 打开弹窗时重置状态
watch(
  () => props.open,
  (val) => {
    if (val) {
      currentStep.value = 0
      testResult.value = null
      remoteTableList.value = []
      selectedTables.value = []
      if (props.editing) {
        loadEditData()
      } else {
        Object.assign(form, defaultForm())
      }
    }
  }
)

async function loadEditData() {
  try {
    const detail = await datasourceApi.getDetail(props.editing.id)
    form.name = detail.name
    form.ds_type = detail.ds_type
    form.description = detail.description || ''
    if (detail.configuration && typeof detail.configuration === 'object') {
      Object.assign(form.configuration, detail.configuration)
    }
  } catch (e) {
    message.error('加载数据源详情失败')
  }
}

async function testConnection() {
  if (!form.ds_type || !form.configuration.host) {
    message.warning('请先填写连接配置')
    return
  }
  testing.value = true
  testResult.value = null
  try {
    const res = await datasourceApi.testConnection({
      ds_type: form.ds_type,
      configuration: form.configuration
    })
    testResult.value = res.success !== false
    if (!testResult.value) {
      message.error(res.message || '连接失败')
    }
  } catch (e) {
    testResult.value = false
    message.error('连接测试异常')
  } finally {
    testing.value = false
  }
}

function toggleSelectAll(e) {
  if (e.target.checked) {
    selectedTables.value = remoteTableList.value.map((t) => t.tableName)
  } else {
    selectedTables.value = []
  }
}

/** 下一步：获取远程表列表 */
async function handleNext() {
  if (!form.name || !form.ds_type) {
    message.warning('请填写数据源名称和类型')
    return
  }
  if (!form.configuration.host || !form.configuration.database) {
    message.warning('请填写完整的连接配置')
    return
  }

  fetchingTables.value = true
  try {
    const res = await datasourceApi.getTablesByConfig({
      ds_type: form.ds_type,
      configuration: form.configuration
    })
    remoteTableList.value = res.tables || []

    if (props.editing) {
      // 编辑模式：加载已选中的表
      try {
        const existingRes = await datasourceApi.getTables(props.editing.id)
        const existingTables = existingRes.tables || []
        const checkedNames = existingTables.filter((t) => t.checked).map((t) => t.table_name)
        // 只勾选远程仍然存在的表
        selectedTables.value = checkedNames.filter((n) =>
          remoteTableList.value.some((t) => t.tableName === n)
        )
      } catch {
        selectedTables.value = remoteTableList.value.map((t) => t.tableName)
      }
    } else {
      // 新建模式：默认全选
      selectedTables.value = remoteTableList.value.map((t) => t.tableName)
    }

    currentStep.value = 1
  } catch (e) {
    message.error('获取表列表失败，请检查连接配置')
  } finally {
    fetchingTables.value = false
  }
}

async function handleSubmit() {
  if (selectedTables.value.length === 0) {
    message.warning('请至少选择一个表')
    return
  }
  submitting.value = true
  try {
    if (props.editing) {
      // 更新数据源配置
      await datasourceApi.update(props.editing.id, {
        name: form.name,
        description: form.description,
        configuration: form.configuration
      })
      // 同步表结构 + 更新选中状态
      await datasourceApi.syncTables(props.editing.id, selectedTables.value)
      message.success('更新成功')
    } else {
      // 新建数据源（带选中的表）
      await datasourceApi.create({
        name: form.name,
        ds_type: form.ds_type,
        description: form.description,
        type_name: props.dsTypes.find((t) => t.code === form.ds_type)?.name || form.ds_type,
        configuration: form.configuration,
        selected_tables: selectedTables.value
      })
      message.success('创建成功')
    }
    emit('success')
  } catch (e) {
    message.error(props.editing ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

function handleCancel() {
  emit('update:open', false)
}
</script>

<style lang="less" scoped>
.table-select-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.table-select-count {
  font-size: 13px;
  color: var(--gray-600);
}

.table-select-grid {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px 4px;
  border: 1px solid var(--gray-150);
  border-radius: 6px;
}

.table-select-name {
  font-weight: 500;
  color: var(--gray-900);
}

.table-select-comment {
  font-size: 12px;
  color: var(--gray-500);
  margin-left: 4px;
}
</style>
