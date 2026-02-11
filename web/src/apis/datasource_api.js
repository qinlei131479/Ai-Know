import { apiAdminGet, apiAdminPost, apiAdminPut, apiAdminDelete } from './base'

/**
 * 数据源管理 API
 */
export const datasourceApi = {
  /** 获取支持的数据源类型 */
  getTypes: () => apiAdminGet('/api/datasource/types'),

  /** 获取数据源列表 */
  list: () => apiAdminGet('/api/datasource/list'),

  /** 获取数据源详情 */
  getDetail: (dsId) => apiAdminGet(`/api/datasource/${dsId}`),

  /** 创建数据源 */
  create: (data) => apiAdminPost('/api/datasource/create', data),

  /** 更新数据源 */
  update: (dsId, data) => apiAdminPut(`/api/datasource/${dsId}`, data),

  /** 删除数据源 */
  delete: (dsId) => apiAdminDelete(`/api/datasource/${dsId}`),

  /** 测试连接 */
  testConnection: (data) => apiAdminPost('/api/datasource/check', data),

  /** 同步表结构（可选传入选中的表名列表） */
  syncTables: (dsId, selectedTables = null) =>
    apiAdminPost(`/api/datasource/${dsId}/sync`, {
      selected_tables: selectedTables
    }),

  /** 获取数据源下的表列表 */
  getTables: (dsId) => apiAdminGet(`/api/datasource/${dsId}/tables`),

  /** 获取表字段列表 */
  getFields: (tableId) => apiAdminGet(`/api/datasource/table/${tableId}/fields`),

  /** 更新表信息 */
  updateTable: (tableId, data) => apiAdminPut(`/api/datasource/table/${tableId}`, data),

  /** 更新字段信息 */
  updateField: (fieldId, data) => apiAdminPut(`/api/datasource/field/${fieldId}`, data),

  /** 预览表数据 */
  previewTable: (dsId, tableName, limit = 100) =>
    apiAdminPost(`/api/datasource/${dsId}/preview`, { table_name: tableName, limit }),

  /** 保存表关系 */
  saveTableRelation: (dsId, data) => apiAdminPost(`/api/datasource/${dsId}/table-relation`, data),

  /** 获取表关系 */
  getTableRelation: (dsId) => apiAdminGet(`/api/datasource/${dsId}/table-relation`),

  /** 根据配置获取表（不保存） */
  getTablesByConfig: (data) => apiAdminPost('/api/datasource/tables-by-config', data),

  /** 根据配置获取字段（不保存） */
  getFieldsByConfig: (data) => apiAdminPost('/api/datasource/fields-by-config', data)
}

/**
 * 术语管理 API
 */
export const terminologyApi = {
  /** 获取术语列表 */
  list: (dsId) =>
    apiAdminGet(dsId ? `/api/terminology/list?datasource_id=${dsId}` : '/api/terminology/list'),

  /** 创建术语 */
  create: (data) => apiAdminPost('/api/terminology/create', data),

  /** 更新术语 */
  update: (termId, data) => apiAdminPut(`/api/terminology/${termId}`, data),

  /** 删除术语 */
  delete: (termId) => apiAdminDelete(`/api/terminology/${termId}`)
}

/**
 * SQL 示例管理 API
 */
export const sqlExampleApi = {
  /** 获取 SQL 示例列表 */
  list: (dsId) =>
    apiAdminGet(dsId ? `/api/sql-example/list?datasource_id=${dsId}` : '/api/sql-example/list'),

  /** 创建 SQL 示例 */
  create: (data) => apiAdminPost('/api/sql-example/create', data),

  /** 更新 SQL 示例 */
  update: (exampleId, data) => apiAdminPut(`/api/sql-example/${exampleId}`, data),

  /** 删除 SQL 示例 */
  delete: (exampleId) => apiAdminDelete(`/api/sql-example/${exampleId}`)
}
