import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 添加 token 认证信息
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      const message = data?.detail || data?.message || '请求失败'

      switch (status) {
        case 400:
          ElMessage.error(message || '请求参数错误')
          break
        case 401:
          ElMessage.error('未授权，请重新登录')
          localStorage.removeItem('token')
          setTimeout(() => {
            window.location.href = '/login'
          }, 1500)
          break
        case 403:
          ElMessage.error('拒绝访问')
          break
        case 404:
          ElMessage.error(message || '请求的资源不存在')
          break
        case 500:
          ElMessage.error(message || '服务器错误')
          break
        case 503:
          ElMessage.error('服务不可用')
          break
        default:
          ElMessage.error(message || `请求失败 (${status})`)
      }
    } else if (error.request) {
      if (error.code === 'ECONNABORTED') {
        ElMessage.error('请求超时，请稍后重试')
      } else {
        ElMessage.error('网络错误，请检查网络连接')
      }
    } else {
      ElMessage.error('请求失败，请稍后重试')
    }

    console.error('响应错误:', error)
    return Promise.reject(error)
  }
)

// 认证相关API
export const authApi = {
  // 用户登录
  login: (data: { username: string; password: string }) => {
    return api.post('/auth/login', data)
  },

  // 用户注册
  register: (data: { username: string; password: string; display_name?: string }) => {
    return api.post('/auth/register', data)
  },

  // 获取当前用户信息
  getCurrentUser: () => {
    return api.get('/auth/me')
  }
}

// 项目相关API
export const projectApi = {
  // 获取项目列表
  getList: (params?: { skip?: number; limit?: number }) => {
    return api.get('/projects/', { params })
  },

  // 获取项目详情
  getById: (id: number) => {
    return api.get(`/projects/${id}`)
  },

  // 创建项目
  create: (data: any) => {
    return api.post('/projects/', data)
  },

  // 更新项目
  update: (id: number, data: any) => {
    return api.put(`/projects/${id}`, data)
  },

  // 删除项目
  delete: (id: number) => {
    return api.delete(`/projects/${id}`)
  },

  // 获取项目数据
  getData: (projectId: number) => {
    return api.get(`/projects/${projectId}/data`)
  },

  // 获取项目汇总
  getSummary: (projectId: number) => {
    return api.get(`/projects/${projectId}/summary`)
  },

  // 更新Excel数据项
  updateData: (projectId: number, dataId: number, data: any) => {
    return api.put(`/projects/${projectId}/data/${dataId}`, data)
  },

  // 校验项目数据
  validate: (projectId: number) => {
    return api.post(`/projects/${projectId}/validate`)
  },

  // 导出项目数据
  exportData: (projectId: number) => {
    return api.get(`/projects/${projectId}/export`, {
      responseType: 'blob'
    })
  },

  // 预览Excel解析结果（不保存）
  previewExcel: (projectId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post(`/projects/${projectId}/excel-preview`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 上传Excel（正式保存）
  uploadExcel: (projectId: number, file: File, columnMappings?: Record<string, Record<string, number>>) => {
    const formData = new FormData()
    formData.append('file', file)
    if (columnMappings && Object.keys(columnMappings).length > 0) {
      formData.append('column_mappings', JSON.stringify(columnMappings))
    }
    return api.post(`/projects/${projectId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

// 模板相关API
export const templateApi = {
  // 获取模板列表
  getList: (params?: { skip?: number; limit?: number }) => {
    return api.get('/templates/', { params })
  },

  // 上传模板
  upload: (data: FormData) => {
    return api.post('/templates/', data, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 删除模板
  delete: (id: number) => {
    return api.delete(`/templates/${id}`)
  },

  // 预览模板
  preview: (id: number) => {
    return api.get(`/templates/${id}/preview`)
  },

  // 获取模板变量配置
  getVariables: (id: number) => {
    return api.get(`/templates/${id}/variables`)
  },

  // 更新模板变量配置
  updateVariables: (id: number, data: any) => {
    return api.put(`/templates/${id}/variables`, data)
  },

  // 检查模板兼容性
  check: (id: number) => {
    return api.get(`/templates/${id}/check`)
  }
}

// 报告相关API
export const reportApi = {
  // 生成报告
  generate: (data: { project_id: number; template_id: number }) => {
    return api.post('/reports/generate', data)
  },

  // 审核报告
  review: (id: number, data: { review_status: string; review_comment?: string }) => {
    return api.put(`/reports/${id}/review`, data)
  },

  // 获取审核历史
  getReviewHistory: (id: number) => {
    return api.get(`/reports/${id}/review-history`)
  },

  // 下载报告
  download: (id: number) => {
    return api.get(`/reports/${id}/download`, {
      responseType: 'blob'
    })
  },

  // 获取项目的所有报告
  getByProject: (projectId: number) => {
    return api.get(`/reports/project/${projectId}`)
  },

  // 获取所有报告
  getAll: (params?: { skip?: number; limit?: number }) => {
    return api.get('/reports/', { params })
  },

  // 预览报告
  preview: (id: number) => {
    return api.get(`/reports/${id}/preview`)
  },

  // 导出PDF
  exportPdf: (id: number) => {
    return api.get(`/reports/${id}/export-pdf`, {
      responseType: 'blob'
    })
  },

  // 创建新版本
  newVersion: (id: number) => {
    return api.post(`/reports/${id}/new-version`)
  },

  // 获取报告版本列表
  getVersions: (id: number) => {
    return api.get(`/reports/${id}/versions`)
  },

  // 对比两个版本
  compare: (id: number, otherId: number) => {
    return api.get(`/reports/${id}/compare/${otherId}`)
  },

  // 获取填充结果
  getFillResult: (id: number) => {
    return api.get(`/reports/${id}/fill-result`)
  },

  // 删除报告
  delete: (id: number) => {
    return api.delete(`/reports/${id}`)
  }
}

// 数据备份相关API
export const backupApi = {
  // 创建备份
  create: (data: { description?: string }) => {
    return api.post('/backup/create', data)
  },

  // 获取备份列表
  list: () => {
    return api.get('/backup/list')
  },

  // 恢复备份
  restore: (id: number) => {
    return api.post(`/backup/restore/${id}`)
  },

  // 删除备份
  delete: (id: number) => {
    return api.delete(`/backup/${id}`)
  }
}

// 数据字典相关API
export const dictionaryApi = {
  // 获取字典列表
  getList: (params?: { category?: string; skip?: number; limit?: number }) => {
    return api.get('/dictionary/', { params })
  },

  // 获取所有分类
  getCategories: () => {
    return api.get('/dictionary/categories')
  },

  // 创建字典项
  create: (data: any) => {
    return api.post('/dictionary/', data)
  },

  // 更新字典项
  update: (id: number, data: any) => {
    return api.put(`/dictionary/${id}`, data)
  },

  // 删除字典项
  delete: (id: number) => {
    return api.delete(`/dictionary/${id}`)
  }
}

// 系统设置相关API
export const settingsApi = {
  // 获取所有设置
  getAll: () => {
    return api.get('/settings/')
  },

  // 更新设置
  update: (key: string, data: { key: string; value: string; description?: string }) => {
    return api.put(`/settings/${key}`, data)
  }
}

// 操作日志相关API
export const logsApi = {
  // 获取操作日志
  getAll: (params?: { skip?: number; limit?: number }) => {
    return api.get('/logs/', { params })
  }
}

// 账号管理相关API（仅管理员）
export const userApi = {
  // 获取员工列表（含总数）
  getList: () => {
    return api.get('/users/')
  },
  // 新增员工（默认密码 123456）
  create: (data: { username: string; display_name?: string; password?: string }) => {
    return api.post('/users/', data)
  },
  // 重置密码为 123456
  resetPassword: (id: number) => {
    return api.post(`/users/${id}/reset-password`)
  },
  // 删除员工
  delete: (id: number) => {
    return api.delete(`/users/${id}`)
  }
}

export default api
