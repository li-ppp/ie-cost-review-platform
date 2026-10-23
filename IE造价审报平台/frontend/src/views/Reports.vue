<template>
  <div class="reports">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报告管理</span>
        </div>
      </template>

      <el-table :data="reports" v-loading="loading" stripe size="small">
        <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="template_name" label="模板" min-width="120" show-overflow-tooltip />
        <el-table-column prop="created_by_name" label="上传人" width="100" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="85" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'generated' ? 'success' : 'info'" size="small">
              {{ row.status === 'generated' ? '已生成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="review_status" label="审核状态" width="95" align="center">
          <template #default="{ row }">
            <el-tag :type="getReviewStatusType(row.review_status)" size="small">
              {{ getReviewStatusText(row.review_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="60" align="center">
          <template #default="{ row }">
            v{{ row.version || 1 }}
          </template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" width="155">
          <template #default="{ row }">
            {{ formatDate(row.generated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="previewReport(row)">预览</el-button>
            <el-button type="primary" link size="small" @click="downloadReport(row)">下载</el-button>
            <el-button type="success" link size="small" @click="exportReportPdf(row)">PDF</el-button>
            <el-button v-if="isAdmin" type="warning" link size="small" @click="showReviewDialog(row)">审核</el-button>
            <el-button type="info" link size="small" @click="showVersionsDialog(row)">版本</el-button>
            <el-button v-if="isAdmin" type="danger" link size="small" @click="deleteReport(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 报告预览对话框 -->
    <el-dialog v-model="previewDialogVisible" title="报告预览" width="70%">
      <div class="preview-content" v-loading="previewLoading">
        <pre>{{ previewContent }}</pre>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 审核对话框 -->
    <el-dialog v-model="reviewDialogVisible" title="报告审核" width="600px">
      <el-form :model="reviewForm" label-width="100px">
        <el-form-item label="报告编号">
          <el-input :value="currentReport?.report_number" disabled />
        </el-form-item>
        <el-form-item label="当前状态">
          <el-tag :type="getReviewStatusType(currentReport?.review_status)">
            {{ getReviewStatusText(currentReport?.review_status) }}
          </el-tag>
        </el-form-item>
        <el-form-item v-if="reviewHistory.reviewed_at" label="上次审核">
          <div class="review-history">
            <span>状态：{{ getReviewStatusText(reviewHistory.review_status) }}</span>
            <span>时间：{{ formatDate(reviewHistory.reviewed_at) }}</span>
            <span v-if="reviewHistory.review_comment">意见：{{ reviewHistory.review_comment }}</span>
          </div>
        </el-form-item>
        <el-form-item label="审核状态" required>
          <el-select v-model="reviewForm.review_status" placeholder="请选择审核状态">
            <el-option label="审核中" value="reviewing" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input
            v-model="reviewForm.review_comment"
            type="textarea"
            :rows="4"
            placeholder="请输入审核意见"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitReview" :loading="reviewLoading">提交审核</el-button>
      </template>
    </el-dialog>

    <!-- 版本管理对话框 -->
    <el-dialog v-model="versionsDialogVisible" title="报告版本管理" width="70%">
      <div v-loading="versionsLoading">
        <div style="margin-bottom: 12px">
          <el-button type="primary" @click="createNewVersion" :loading="creatingVersion">
            <el-icon><Plus /></el-icon>
            基于当前报告创建新版本
          </el-button>
          <span style="margin-left: 12px; color: #909399; font-size: 13px">
            当前报告：{{ currentReport?.file_name }} (v{{ currentReport?.version || 1 }})
          </span>
        </div>
        <el-table :data="versions" stripe>
          <el-table-column prop="version" label="版本" width="80">
            <template #default="{ row }">v{{ row.version }}</template>
          </el-table-column>
          <el-table-column prop="file_name" label="文件名" min-width="200" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="review_status" label="审核状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getReviewStatusType(row.review_status)">
                {{ getReviewStatusText(row.review_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="生成时间" width="180">
            <template #default="{ row }">{{ formatDate(row.generated_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click="downloadVersion(row)">下载</el-button>
              <el-button
                size="small"
                link
                type="warning"
                @click="compareVersions(row)"
                :disabled="row.id === currentReport?.id"
              >
                与当前对比
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 对比结果 -->
      <el-dialog
        v-model="compareDialogVisible"
        title="版本对比"
        width="80%"
        append-to-body
      >
        <div v-loading="compareLoading">
          <el-alert
            v-if="compareResult"
            :title="`对比：${compareResult.report1.filename} ↔ ${compareResult.report2.filename}`"
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom: 12px"
          />
          <pre class="diff-content">{{ compareResult?.diff }}</pre>
        </div>
      </el-dialog>

      <template #footer>
        <el-button @click="versionsDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { reportApi } from '../api'

const loading = ref(false)
const reports = ref<any[]>([])
const previewDialogVisible = ref(false)
const previewContent = ref('')
const previewLoading = ref(false)
const isAdmin = ref(false)

const checkAdmin = () => {
  try {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      const user = JSON.parse(userStr)
      isAdmin.value = user.role === 'admin'
    } else {
      isAdmin.value = false
    }
  } catch {
    isAdmin.value = false
  }
}

// 审核相关
const reviewDialogVisible = ref(false)
const reviewLoading = ref(false)
const currentReport = ref<any>(null)
const reviewForm = ref({
  review_status: '',
  review_comment: ''
})
const reviewHistory = ref<any>({})

// 版本管理相关
const versionsDialogVisible = ref(false)
const versionsLoading = ref(false)
const versions = ref<any[]>([])
const creatingVersion = ref(false)
const compareDialogVisible = ref(false)
const compareLoading = ref(false)
const compareResult = ref<any>(null)

const getReviewStatusType = (status: string) => {
  const typeMap: Record<string, string> = {
    'draft': 'info',
    'reviewing': 'warning',
    'approved': 'success',
    'rejected': 'danger'
  }
  return typeMap[status] || 'info'
}

const getReviewStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'draft': '草稿',
    'reviewing': '审核中',
    'approved': '已通过',
    'rejected': '已驳回'
  }
  return textMap[status] || '未知'
}

const showReviewDialog = async (report: any) => {
  currentReport.value = report
  reviewForm.value = {
    review_status: report.review_status || 'draft',
    review_comment: report.review_comment || ''
  }
  reviewHistory.value = {}
  reviewDialogVisible.value = true
  try {
    const res = await reportApi.getReviewHistory(report.id)
    reviewHistory.value = res.data
  } catch {
    // 审核历史获取失败不阻塞
  }
}

const submitReview = async () => {
  if (!currentReport.value) return
  
  reviewLoading.value = true
  try {
    await reportApi.review(currentReport.value.id, reviewForm.value)
    ElMessage.success('审核提交成功')
    reviewDialogVisible.value = false
    loadReports()
  } catch (error) {
    ElMessage.error('审核提交失败')
  } finally {
    reviewLoading.value = false
  }
}

const loadReports = async () => {
  loading.value = true
  try {
    const res = await reportApi.getAll()
    reports.value = res.data
  } catch (error) {
    ElMessage.error('获取报告列表失败')
  } finally {
    loading.value = false
  }
}

const downloadReport = async (report: any) => {
  try {
    const res = await reportApi.download(report.id)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = report.file_name
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const deleteReport = async (report: any) => {
  try {
    await ElMessageBox.confirm(
      `确认删除报告 "${report.file_name || report.id}"？该操作会同时删除物理文件，不可恢复。`,
      '删除报告确认',
      { type: 'warning' }
    )
    await reportApi.delete(report.id)
    ElMessage.success('报告已删除')
    loadReports()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      // 错误已由拦截器提示
    }
  }
}

const previewReport = async (report: any) => {
  previewLoading.value = true
  previewDialogVisible.value = true
  try {
    const res = await reportApi.preview(report.id)
    previewContent.value = res.data.content
  } catch (error) {
    ElMessage.error('预览失败')
  } finally {
    previewLoading.value = false
  }
}

const exportReportPdf = async (report: any) => {
  try {
    const res = await reportApi.exportPdf(report.id)
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    const fileName = report.file_name || `report_${report.id}.docx`
    link.download = fileName.replace(/\.docx$/, '.pdf')
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('PDF导出成功')
  } catch (error: any) {
    let msg = 'PDF导出失败'
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text()
        const errData = JSON.parse(text)
        msg = errData.detail || errData.message || msg
      } catch {}
    } else if (error.response?.data?.detail) {
      msg = error.response.data.detail
    }
    ElMessage.error(msg)
  }
}

// 版本管理函数
const showVersionsDialog = async (report: any) => {
  currentReport.value = report
  versionsDialogVisible.value = true
  versionsLoading.value = true
  versions.value = []
  try {
    const res = await reportApi.getVersions(report.id)
    versions.value = res.data
  } catch (error) {
    ElMessage.error('获取版本列表失败')
  } finally {
    versionsLoading.value = false
  }
}

const createNewVersion = async () => {
  if (!currentReport.value) return
  creatingVersion.value = true
  try {
    await reportApi.newVersion(currentReport.value.id)
    ElMessage.success('新版本创建成功')
    const res = await reportApi.getVersions(currentReport.value.id)
    versions.value = res.data
    loadReports()
  } catch (error) {
    ElMessage.error('创建新版本失败')
  } finally {
    creatingVersion.value = false
  }
}

const compareVersions = async (row: any) => {
  if (!currentReport.value) return
  compareDialogVisible.value = true
  compareLoading.value = true
  compareResult.value = null
  try {
    const res = await reportApi.compare(currentReport.value.id, row.id)
    compareResult.value = res.data
  } catch (error) {
    ElMessage.error('版本对比失败')
  } finally {
    compareLoading.value = false
  }
}

const downloadVersion = async (report: any) => {
  try {
    const res = await reportApi.download(report.id)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = report.file_name
    link.click()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  checkAdmin()
  loadReports()
})
</script>

<style scoped>
.reports {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preview-content {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 16px;
}

.preview-content pre {
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 65vh;
  overflow: auto;
  font-family: 'Microsoft YaHei', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.8;
  color: #303133;
}

.diff-content {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 12px;
  max-height: 500px;
  overflow: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.review-history {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  background: #f5f7fa;
  border-left: 3px solid #409eff;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.review-history span {
  display: block;
}
</style>
