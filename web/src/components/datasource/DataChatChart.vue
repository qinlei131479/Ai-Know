<template>
  <div class="data-chat-chart">
    <div class="chart-toolbar">
      <a-radio-group v-model:value="viewMode" size="small">
        <a-radio-button value="chart">图表</a-radio-button>
        <a-radio-button value="table">表格</a-radio-button>
      </a-radio-group>
    </div>

    <!-- 图表视图 -->
    <div v-show="viewMode === 'chart'" ref="chartRef" class="chart-container"></div>

    <!-- 表格视图 -->
    <div v-show="viewMode === 'table'" class="table-view">
      <a-table
        v-if="tableColumns.length > 0"
        :columns="tableColumns"
        :data-source="tableRows"
        :row-key="(r) => r.key"
        :pagination="{ pageSize: 10, size: 'small' }"
        size="small"
        :scroll="{ x: 'max-content' }"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  config: { type: Object, default: null },
  data: { type: Object, default: null }
})

const chartRef = ref(null)
// 当 config 为 table 类型时默认显示表格视图
const viewMode = ref('chart')
let chartInstance = null

// 根据 config 类型初始化 viewMode
function initViewMode() {
  const t = props.config?.type || props.config?.chart_type
  if (t === 'table') {
    viewMode.value = 'table'
  }
}

// 归一化列名：支持 ["col1","col2"] 或 [{name,value}]，缺省时从 data 首行推导
function normalizeColumns(renderData) {
  const fromCols = renderData?.columns?.length
    ? renderData.columns.map((col) => {
        if (typeof col === 'string') return col
        if (col && typeof col === 'object') return col.value ?? col.name ?? col.key ?? ''
        return String(col)
      }).filter(Boolean)
    : []
  if (fromCols.length) return fromCols
  const first = renderData?.data?.[0]
  return first ? Object.keys(first) : []
}

// 表格列和数据
const tableColumns = computed(() => {
  const renderData = props.data
  const cols = normalizeColumns(renderData)
  if (!cols.length) return []
  return cols.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    width: 150,
    ellipsis: true
  }))
})

const tableRows = computed(() => {
  const renderData = props.data
  if (!renderData?.data?.length) return []
  return renderData.data.map((row, idx) => ({ ...row, key: idx }))
})

function renderChart() {
  if (!chartRef.value || !props.config) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)

  // 直接使用后端返回的 ECharts option，做最小化处理
  const option = buildOption(props.config, props.data)
  chartInstance.setOption(option)
}

function buildOption(config, renderData) {
  // 如果 config 已经是完整的 ECharts option，直接使用
  if (config.series || config.xAxis || config.yAxis) {
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      ...config,
      // 确保使用项目调色板
      color: getChartColors()
    }
  }

  // 否则根据 chart_type 构建 option
  const chartType = config.chart_type || config.type || 'bar'
  const data = renderData?.data || []
  const columns = normalizeColumns(renderData || {})

  if (data.length === 0) {
    return { title: { text: '暂无数据', left: 'center', top: 'center' } }
  }

  const colors = getChartColors()

  switch (chartType) {
    case 'pie':
      return buildPieOption(config, data, columns, colors)
    case 'line':
      return buildLineOption(config, data, columns, colors)
    case 'table':
      return { title: { text: '请切换到表格视图查看数据', left: 'center', top: 'center' } }
    case 'bar':
    default:
      return buildBarOption(config, data, columns, colors)
  }
}

function buildBarOption(config, data, columns, colors) {
  const xField = config.x_field || columns[0]
  const yFields = config.y_fields || columns.slice(1)

  return {
    color: colors,
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map((d) => d[xField]),
      axisLabel: { rotate: data.length > 8 ? 30 : 0 }
    },
    yAxis: { type: 'value' },
    series: yFields.map((field) => ({
      name: field,
      type: 'bar',
      data: data.map((d) => d[field])
    }))
  }
}

function buildLineOption(config, data, columns, colors) {
  const xField = config.x_field || columns[0]
  const yFields = config.y_fields || columns.slice(1)

  return {
    color: colors,
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map((d) => d[xField])
    },
    yAxis: { type: 'value' },
    series: yFields.map((field) => ({
      name: field,
      type: 'line',
      smooth: true,
      data: data.map((d) => d[field])
    }))
  }
}

function buildPieOption(config, data, columns, colors) {
  const nameField =
    config.name_field ||
    config.axis?.series?.value ||
    config.axis?.x?.value ||
    columns[0]
  const valueField =
    config.value_field ||
    config.axis?.y?.value ||
    columns[1]

  return {
    color: colors,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: true,
        label: { show: true, formatter: '{b}: {d}%' },
        data: data.map((d) => ({
          name: d[nameField],
          value: d[valueField]
        }))
      }
    ]
  }
}

function getChartColors() {
  // 从 CSS 变量读取项目调色板
  const root = document.documentElement
  const colors = []
  for (let i = 1; i <= 10; i++) {
    const color = getComputedStyle(root).getPropertyValue(`--chart-palette-${i}`).trim()
    if (color) colors.push(color)
  }
  return colors.length > 0
    ? colors
    : ['#3996ae', '#5faec2', '#82c3d6', '#a3d8e8', '#046a82', '#024c63', '#f0b429', '#e8694e', '#6c63ff', '#2ecc71']
}

// 响应式重绘
function handleResize() {
  chartInstance?.resize()
}

watch(
  () => [props.config, props.data],
  () => {
    initViewMode()
    nextTick(() => {
      renderChart()
      nextTick(() => chartInstance?.resize())
    })
  },
  { deep: true }
)

watch(viewMode, () => {
  nextTick(() => chartInstance?.resize())
})

onMounted(() => {
  initViewMode()
  nextTick(renderChart)
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style lang="less" scoped>
.data-chat-chart {
  width: 100%;
}

.chart-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.chart-container {
  width: 100%;
  height: 360px;
}

.table-view {
  width: 100%;
}
</style>
