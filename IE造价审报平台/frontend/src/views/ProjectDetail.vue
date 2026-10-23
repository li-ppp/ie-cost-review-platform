<template>
  <div class="project-detail">
    <el-page-header @back="$router.push('/')" title="返回工作台">
      <template #content>
        <span class="page-title">{{ project?.name }}</span>
      </template>
    </el-page-header>

    <el-row :gutter="20" style="margin-top: 20px" v-loading="pageLoading">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>项目信息</span>
          </template>
          <el-descriptions :column="1" border v-if="project">
            <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item>
            <el-descriptions-item label="建设单位">{{ project.client_name }}</el-descriptions-item>
            <el-descriptions-item label="工程类型">{{ project.project_type }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(project.status)">
                {{ getStatusText(project.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatDate(project.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>数据汇总</span>
          </template>
          <div v-if="summary" class="summary-content">
            <div class="summary-item">
              <div class="summary-label">送审金额</div>
              <div class="summary-value">{{ formatMoney(summary.total_submitted) }} 元</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">审定金额</div>
              <div class="summary-value">{{ formatMoney(summary.total_audited) }} 元</div>
            </div>
            <div class="summary-item">
              <div class="summary-label">审减金额</div>
              <div class="summary-value warning">{{ formatMoney(Math.abs(summary.total_adjustment)) }} 元</div>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>Excel数据管理</span>
          <div>
            <el-button type="warning" @click="validateData" :loading="validating">
              <el-icon><Check /></el-icon>
              校验数据
            </el-button>
            <el-button type="success" @click="exportData" :loading="exporting">
              <el-icon><Download /></el-icon>
              导出数据
            </el-button>
            <el-button type="primary" @click="showUploadDialog" style="margin-left: 10px">
              <el-icon><Upload /></el-icon>
              上传Excel文件
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="excelFiles" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="engineering_type" label="工程类型" />
        <el-table-column prop="upload_time" label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.upload_time) }}
          </template>
        </el-table-column>
        <el-table-column label="数据项数" width="100">
          <template #default="{ row }">
            {{ row.data_items?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewData(row)">
              查看数据
            </el-button>
            <el-button v-if="isAdmin" type="warning" link @click="handleEditData(row)">
              编辑数据
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>生成报告</span>
        </div>
      </template>

      <template v-if="isAdmin">
        <el-form :model="generateForm" label-width="100px">
          <el-form-item label="选择模板">
            <el-select v-model="generateForm.template_id" placeholder="请选择模板">
              <el-option
                v-for="template in templates"
                :key="template.id"
                :label="template.name"
                :value="template.id"
              />
            </el-select>
          </el-form-item>

          <el-collapse v-model="sectionTotalsExpanded" style="margin-bottom: 12px">
            <el-collapse-item title="汇总段落金额（可选：措施/其他/规费/税金/附加税）" name="sections">
              <el-alert type="info" :closable="false" style="margin-bottom: 12px"
                title="留空则保留模板原有数字；填写后会用真实数据替换报告中(二)~(六)段的金额。" />
              <el-table :data="sectionTotalRows" border size="small">
                <el-table-column prop="label" label="段落" width="120" />
                <el-table-column label="送审金额（元）">
                  <template #default="{ row }">
                    <el-input-number v-model="sectionTotals[row.key].submitted" :controls="false" size="small" :precision="2" style="width: 100%" placeholder="留空" />
                  </template>
                </el-table-column>
                <el-table-column label="审定金额（元）">
                  <template #default="{ row }">
                    <el-input-number v-model="sectionTotals[row.key].audited" :controls="false" size="small" :precision="2" style="width: 100%" placeholder="留空" />
                  </template>
                </el-table-column>
                <el-table-column label="审减金额（元）">
                  <template #default="{ row }">
                    <el-input-number v-model="sectionTotals[row.key].adjustment" :controls="false" size="small" :precision="2" style="width: 100%" placeholder="留空" />
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>

          <el-form-item>
            <el-button type="primary" @click="generateReport" :loading="generating">
              生成报告
            </el-button>
          </el-form-item>
        </el-form>
      </template>
      <el-alert v-else type="info" :closable="false" title="仅管理员可生成报告，员工可上传Excel数据与创建报告新版本" />

      <el-divider />

      <h4 style="margin-bottom: 15px">历史报告</h4>
      <el-table :data="reports" stripe v-loading="reportsLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'generated' ? 'success' : 'info'">
              {{ row.status === 'generated' ? '已生成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.generated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="340">
          <template #default="{ row }">
            <el-button type="info" link @click="previewReport(row)">
              预览
            </el-button>
            <el-button type="primary" link @click="downloadReport(row)">
              下载
            </el-button>
            <el-button type="success" link @click="exportReportPdf(row)">
              导出PDF
            </el-button>
            <el-button type="warning" link @click="createNewVersion(row)" :loading="creatingVersionId === row.id">
              新版本
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 数据查看对话框 -->
    <el-dialog v-model="dataDialogVisible" title="数据详情" width="80%">
      <el-table :data="currentData" stripe max-height="500">
        <el-table-column prop="item_name" label="项目名称" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="submitted_qty" label="送审工程量" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.submitted_qty) }}
          </template>
        </el-table-column>
        <el-table-column prop="submitted_price" label="送审单价" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.submitted_price) }}
          </template>
        </el-table-column>
        <el-table-column prop="submitted_total" label="送审合价" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.submitted_total) }}
          </template>
        </el-table-column>
        <el-table-column prop="audited_qty" label="审核工程量" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.audited_qty) }}
          </template>
        </el-table-column>
        <el-table-column prop="audited_price" label="审核单价" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.audited_price) }}
          </template>
        </el-table-column>
        <el-table-column prop="audited_total" label="审核合价" width="120">
          <template #default="{ row }">
            {{ formatNumber(row.audited_total) }}
          </template>
        </el-table-column>
        <el-table-column prop="adjustment" label="调整金额" width="120">
          <template #default="{ row }">
            {{ row.adjustment > 0 ? '+' : '' }}{{ formatNumber(row.adjustment) }}
            {{ row.adjustment > 0 ? '审增' : row.adjustment < 0 ? '审减' : '' }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 数据编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑数据" width="80%">
      <el-table :data="editData" stripe max-height="500">
        <el-table-column prop="item_name" label="项目名称">
          <template #default="{ row }">
            <el-input v-model="row.item_name" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="100">
          <template #default="{ row }">
            <el-input v-model="row.unit" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="submitted_qty" label="送审工程量" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.submitted_qty" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column prop="submitted_price" label="送审单价" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.submitted_price" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column prop="submitted_total" label="送审合价" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.submitted_total" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column prop="audited_qty" label="审核工程量" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.audited_qty" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column prop="audited_price" label="审核单价" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.audited_price" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column prop="audited_total" label="审核合价" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.audited_total" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
        <el-table-column prop="adjustment" label="调整金额" width="130">
          <template #default="{ row }">
            <el-input-number v-model="row.adjustment" size="small" :precision="2" :controls="false" />
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEditData" :loading="savingEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 报告预览对话框 -->
    <el-dialog v-model="previewDialogVisible" title="报告预览" width="70%">
      <div class="preview-content" v-loading="previewLoading">
        <pre>{{ previewContent }}</pre>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 上传Excel对话框 -->
    <el-dialog v-model="uploadDialogVisible" title="上传Excel" width="700px">
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :on-change="handleExcelFileChange"
        :on-remove="handleExcelFileRemove"
        :limit="1"
        :on-exceed="() => ElMessage.warning('只能选择一个文件')"
        accept=".xlsx"
        drag
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处或 <em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            仅支持 .xlsx 文件，单个文件不超过10MB。选择后请先预览解析结果，确认无误再上传。
          </div>
        </template>
      </el-upload>

      <div style="margin-top: 12px">
        <el-button type="warning" @click="previewExcelUpload" :loading="previewingExcel" :disabled="!selectedExcelFile">
          <el-icon><View /></el-icon>
          预览解析结果
        </el-button>
        <el-button type="success" @click="confirmExcelUpload" :loading="uploadingExcel" :disabled="!selectedExcelFile">
          <el-icon><Upload /></el-icon>
          确认上传
        </el-button>
      </div>

      <div v-if="excelPreviewResult" style="margin-top: 16px">
        <el-alert
          :title="`解析到 ${excelPreviewResult.total_sheets} 个工作表`"
          :type="excelPreviewResult.warnings?.length ? 'warning' : 'success'"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <el-card v-for="(sheet, idx) in excelPreviewResult.sheets" :key="idx" shadow="never" style="margin-bottom: 12px">
          <template #header>
            <span>{{ sheet.engineering_type || sheet.sheet_name }} （{{ sheet.total_rows }} 行）</span>
          </template>
          <el-descriptions :column="2" border size="small" style="margin-bottom: 8px">
            <el-descriptions-item label="表头行">{{ sheet.header_row + 1 }}</el-descriptions-item>
            <el-descriptions-item label="数据起始行">{{ sheet.data_start_row + 1 }}</el-descriptions-item>
          </el-descriptions>
          <div style="margin-bottom: 8px">
            <el-tag v-for="(col, key) in sheet.column_mapping" :key="key" size="small" style="margin: 2px">
              {{ key }} → 列{{ col + 1 }}
            </el-tag>
          </div>
          <el-table :data="sheet.sample_data" stripe size="small" max-height="200">
            <el-table-column prop="name" label="项目名称" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column prop="submitted_qty" label="送审量" width="100" />
            <el-table-column prop="audited_qty" label="审核量" width="100" />
            <el-table-column prop="adjustment" label="调整额" width="100" />
          </el-table>
          <el-collapse style="margin-top: 8px">
            <el-collapse-item title="手工映射列（如自动识别有误可在此修正）" :name="idx">
              <div class="mapping-grid">
                <div v-for="fd in FIELD_DEFINITIONS" :key="fd.key" class="mapping-item">
                  <span class="mapping-label">{{ fd.label }}</span>
                  <el-select
                    :model-value="getMappingValue(sheet.sheet_name, fd.key, sheet.column_mapping?.[fd.key])"
                    @update:model-value="(v: number) => setMappingValue(sheet.sheet_name, fd.key, v)"
                    size="small"
                    placeholder="选择列"
                    style="width: 100%"
                  >
                    <el-option
                      v-for="ac in sheet.available_columns || []"
                      :key="ac.col"
                      :label="ac.label"
                      :value="ac.col"
                    />
                  </el-select>
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>
        <el-alert
          v-for="(w, i) in excelPreviewResult.warnings || []"
          :key="i"
          :title="w"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
      </div>
    </el-dialog>

    <!-- 报告生成中对话框 -->
    <el-dialog v-model="generatingDialogVisible" title="报告生成中" width="400px" :close-on-click-modal="false" :close-on-press-escape="false" :show-close="false">
      <div style="text-align: center; padding: 20px 0">
        <el-icon class="is-loading" :size="48"><Loading /></el-icon>
        <p style="margin-top: 16px; font-size: 16px">正在生成报告，请稍候...</p>
        <p style="color: #909399; font-size: 13px">系统正在填充模板数据，完成后将自动展示填充结果</p>
      </div>
    </el-dialog>

    <!-- 填充结果对话框 -->
    <el-dialog v-model="fillResultDialogVisible" title="报告填充结果" width="700px">
      <div v-if="fillResult">
        <el-alert
          :title="fillResultAlertTitle"
          :type="fillResultAlertType"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />

        <el-card v-if="fillResult.matched_types?.length" shadow="never" style="margin-bottom: 12px">
          <template #header>已填充工程类型 ({{ fillResult.matched_types.length }})</template>
          <div>
            <el-tag v-for="t in fillResult.matched_types" :key="t" type="success" style="margin: 4px">
              {{ t }}（{{ fillResult.detail_counts?.[t] || 0 }} 项）
            </el-tag>
          </div>
        </el-card>

        <el-card v-if="fillResult.skipped_types?.length" shadow="never" style="margin-bottom: 12px">
          <template #header>跳过的工程类型 ({{ fillResult.skipped_types.length }})</template>
          <el-alert
            v-for="t in fillResult.skipped_types"
            :key="t"
            :title="`${t}：${fillResult.skipped_reasons?.[t] || '原因未知'}`"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 6px"
          />
        </el-card>

        <el-card v-if="fillResult.unfilled_placeholders?.length" shadow="never" style="margin-bottom: 12px">
          <template #header>未填充占位符 ({{ fillResult.unfilled_placeholders.length }})</template>
          <el-tag v-for="ph in fillResult.unfilled_placeholders" :key="ph" type="danger" style="margin: 4px" v-text="'{{' + ph + '}}'" />
        </el-card>

        <el-card v-if="fillResult.warnings?.length" shadow="never">
          <template #header>警告 ({{ fillResult.warnings.length }})</template>
          <el-alert
            v-for="(w, i) in fillResult.warnings"
            :key="i"
            :title="w"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 6px"
          />
        </el-card>
      </div>
      <template #footer>
        <el-button @click="fillResultDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { projectApi, templateApi, reportApi } from '../api'
import type { UploadFile, UploadInstance } from 'element-plus'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))

const project = ref<any>(null)
const summary = ref<any>(null)
const excelFiles = ref<any[]>([])
const templates = ref<any[]>([])
const reports = ref<any[]>([])
const loading = ref(false)
const generating = ref(false)
const pageLoading = ref(false)
const reportsLoading = ref(false)
const creatingVersionId = ref<number | null>(null)
const dataDialogVisible = ref(false)
const currentData = ref<any[]>([])
const validating = ref(false)
const exporting = ref(false)
const editDialogVisible = ref(false)
const editData = ref<any[]>([])
const savingEdit = ref(false)
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

// Excel 预览与上传
const uploadDialogVisible = ref(false)
const uploadRef = ref<UploadInstance>()
const selectedExcelFile = ref<File | null>(null)
const previewingExcel = ref(false)
const uploadingExcel = ref(false)
const excelPreviewResult = ref<any>(null)
const manualMappings = ref<Record<string, Record<string, number>>>({})

// 固定 9 个字段下拉（中文标签 + 字段 key）
const FIELD_DEFINITIONS = [
  { key: 'name', label: '项目名称' },
  { key: 'unit', label: '单位' },
  { key: 'submitted_qty', label: '送审工程量' },
  { key: 'submitted_price', label: '送审单价' },
  { key: 'submitted_total', label: '送审合价' },
  { key: 'audited_qty', label: '审核工程量' },
  { key: 'audited_price', label: '审核单价' },
  { key: 'audited_total', label: '审核合价' },
  { key: 'adjustment', label: '调整金额' },
]

const initManualMappings = () => {
  const result: Record<string, Record<string, number>> = {}
  if (excelPreviewResult.value?.sheets) {
    for (const sheet of excelPreviewResult.value.sheets) {
      const sheetMap: Record<string, number> = {}
      const cm = sheet.column_mapping || {}
      for (const fd of FIELD_DEFINITIONS) {
        if (cm[fd.key] !== undefined && cm[fd.key] !== null) {
          sheetMap[fd.key] = cm[fd.key]
        }
      }
      result[sheet.sheet_name] = sheetMap
    }
  }
  manualMappings.value = result
}

const getMappingValue = (sheetName: string, fieldKey: string, fallback: any): number => {
  const sheetMap = manualMappings.value[sheetName]
  if (sheetMap && sheetMap[fieldKey] !== undefined) {
    return sheetMap[fieldKey]
  }
  return fallback ?? 0
}

const setMappingValue = (sheetName: string, fieldKey: string, value: number) => {
  if (!manualMappings.value[sheetName]) {
    manualMappings.value[sheetName] = {}
  }
  manualMappings.value[sheetName][fieldKey] = value
}

// 报告生成轮询
const generatingDialogVisible = ref(false)
const fillResultDialogVisible = ref(false)
const fillResult = ref<any>(null)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const generateForm = ref({
  template_id: null as number | null
})

// (二)~(六) 汇总段落金额（可选填写，留空则保留模板原数字）
type SectionTotal = { submitted: number | null; audited: number | null; adjustment: number | null }
const sectionTotalsExpanded = ref(false)
const sectionTotals = ref<Record<string, SectionTotal>>({
  措施项目: { submitted: null, audited: null, adjustment: null },
  其他项目: { submitted: null, audited: null, adjustment: null },
  规费: { submitted: null, audited: null, adjustment: null },
  税金: { submitted: null, audited: null, adjustment: null },
  附加税: { submitted: null, audited: null, adjustment: null },
})

const buildSectionTotalsPayload = (): Record<string, { submitted: number; audited: number; adjustment: number }> | undefined => {
  const result: Record<string, { submitted: number; audited: number; adjustment: number }> = {}
  let hasAny = false
  for (const [key, vals] of Object.entries(sectionTotals.value)) {
    if (vals.submitted != null || vals.audited != null || vals.adjustment != null) {
      hasAny = true
      result[key] = {
        submitted: Number(vals.submitted) || 0,
        audited: Number(vals.audited) || 0,
        adjustment: Number(vals.adjustment) || 0,
      }
    }
  }
  return hasAny ? result : undefined
}

const sectionTotalRows = [
  { key: '措施项目', label: '(二) 措施项目' },
  { key: '其他项目', label: '(三) 其他项目' },
  { key: '规费', label: '(四) 规费' },
  { key: '税金', label: '(五) 税金' },
  { key: '附加税', label: '(六) 附加税' },
]

const fillResultAlertType = computed(() => {
  if (!fillResult.value) return 'info'
  if (fillResult.value.error) return 'error'
  if (fillResult.value.skipped_types?.length || fillResult.value.unfilled_placeholders?.length) return 'warning'
  return 'success'
})

const fillResultAlertTitle = computed(() => {
  if (!fillResult.value) return ''
  if (fillResult.value.error) return `报告生成失败：${fillResult.value.error}`
  const matched = fillResult.value.matched_types?.length || 0
  const skipped = fillResult.value.skipped_types?.length || 0
  const unfilled = fillResult.value.unfilled_placeholders?.length || 0
  if (skipped === 0 && unfilled === 0) return `报告生成成功：已填充 ${matched} 个工程类型`
  return `报告已生成，但有 ${skipped} 个工程类型被跳过，${unfilled} 个占位符未填充`
})

const loadProject = async () => {
  pageLoading.value = true
  try {
    const res = await projectApi.getById(projectId.value)
    project.value = res.data
  } catch (error) {
    ElMessage.error('获取项目信息失败')
  } finally {
    pageLoading.value = false
  }
}

const loadSummary = async () => {
  try {
    const res = await projectApi.getSummary(projectId.value)
    summary.value = res.data
  } catch (error) {
    ElMessage.error('获取汇总数据失败')
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const res = await projectApi.getData(projectId.value)
    excelFiles.value = res.data
  } catch (error) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const loadTemplates = async () => {
  try {
    const res = await templateApi.getList()
    templates.value = res.data
  } catch (error) {
    console.error('获取模板列表失败')
  }
}

const loadReports = async () => {
  try {
    const res = await reportApi.getByProject(projectId.value)
    reports.value = res.data
  } catch (error) {
    console.error('获取报告列表失败')
  }
}

const createNewVersion = async (report: any) => {
  creatingVersionId.value = report.id
  try {
    await reportApi.newVersion(report.id)
    ElMessage.success('新版本创建成功')
    loadReports()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建新版本失败')
  } finally {
    creatingVersionId.value = null
  }
}

const showUploadDialog = () => {
  selectedExcelFile.value = null
  excelPreviewResult.value = null
  if (uploadRef.value) uploadRef.value.clearFiles()
  uploadDialogVisible.value = true
}

const handleExcelFileChange = (file: UploadFile) => {
  const raw = file.raw as File
  if (!raw) return
  if (!raw.name.endsWith('.xlsx')) {
    ElMessage.error('只能上传 .xlsx 格式的 Excel 文件')
    uploadRef.value?.clearFiles()
    return
  }
  if (raw.size / 1024 / 1024 >= 10) {
    ElMessage.error('文件大小不能超过10MB')
    uploadRef.value?.clearFiles()
    return
  }
  selectedExcelFile.value = raw
  excelPreviewResult.value = null
}

const handleExcelFileRemove = () => {
  selectedExcelFile.value = null
  excelPreviewResult.value = null
}

const previewExcelUpload = async () => {
  if (!selectedExcelFile.value) return
  previewingExcel.value = true
  try {
    const res = await projectApi.previewExcel(projectId.value, selectedExcelFile.value)
    excelPreviewResult.value = res.data
    initManualMappings()
    if (excelPreviewResult.value.warnings?.length) {
      ElMessage.warning('解析完成，但存在警告，请检查')
    } else {
      ElMessage.success('解析完成，可在下方手工调整列映射后上传')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '预览失败')
  } finally {
    previewingExcel.value = false
  }
}

const confirmExcelUpload = async () => {
  if (!selectedExcelFile.value) return
  uploadingExcel.value = true
  try {
    const mappings = manualMappings.value && Object.keys(manualMappings.value).length > 0
      ? manualMappings.value
      : undefined
    const res = await projectApi.uploadExcel(projectId.value, selectedExcelFile.value, mappings)
    ElMessage.success(`上传成功，共 ${res.data.items_count} 项`)
    selectedExcelFile.value = null
    excelPreviewResult.value = null
    manualMappings.value = {}
    if (uploadRef.value) uploadRef.value.clearFiles()
    uploadDialogVisible.value = false
    loadData()
    loadSummary()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploadingExcel.value = false
  }
}

const viewData = (file: any) => {
  currentData.value = file.data_items || []
  dataDialogVisible.value = true
}

const generateReport = async () => {
  if (!generateForm.value.template_id) {
    ElMessage.warning('请选择模板')
    return
  }

  generating.value = true
  try {
    const payload: any = {
      project_id: projectId.value,
      template_id: generateForm.value.template_id
    }
    const sectionPayload = buildSectionTotalsPayload()
    if (sectionPayload) {
      payload.section_totals = sectionPayload
    }
    const res = await reportApi.generate(payload)
    const reportId = res.data.id
    generatingDialogVisible.value = true
    pollReportStatus(reportId)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '报告生成失败')
  } finally {
    generating.value = false
  }
}

const pollReportStatus = (reportId: number) => {
  let attempts = 0
  const maxAttempts = 60
  const check = async () => {
    attempts++
    try {
      const res = await reportApi.getFillResult(reportId)
      const status = res.data.status
      if (status === 'generated' || status === 'failed') {
        generatingDialogVisible.value = false
        fillResult.value = res.data.fill_report
        fillResultDialogVisible.value = true
        loadReports()
        return
      }
      if (attempts >= maxAttempts) {
        generatingDialogVisible.value = false
        ElMessage.warning('报告生成超时，请稍后在报告列表查看')
        loadReports()
        return
      }
      pollTimer = setTimeout(check, 2000)
    } catch (error) {
      generatingDialogVisible.value = false
      ElMessage.error('获取报告状态失败')
      loadReports()
    }
  }
  check()
}

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})

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

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    draft: 'info',
    in_progress: 'warning',
    completed: 'success'
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    draft: '草稿',
    in_progress: '进行中',
    completed: '已完成'
  }
  return texts[status] || status
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString('zh-CN')
}

const formatMoney = (value: number) => {
  return value?.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'
}

const formatNumber = (value: number) => {
  return value?.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '-'
}

const validateData = async () => {
  validating.value = true
  try {
    const res = await projectApi.validate(projectId.value)
    const { valid, errors, warnings } = res.data
    
    if (valid && warnings.length === 0) {
      ElMessage.success('数据校验通过')
    } else if (valid) {
      ElMessage.warning(`数据校验通过，但有 ${warnings.length} 个警告`)
      console.warn('校验警告:', warnings)
    } else {
      ElMessage.error(`数据校验失败，发现 ${errors.length} 个错误`)
      console.error('校验错误:', errors)
    }
  } catch (error) {
    ElMessage.error('数据校验失败')
  } finally {
    validating.value = false
  }
}

const exportData = async () => {
  exporting.value = true
  try {
    const res = await projectApi.exportData(projectId.value)
    const blob = new Blob([res.data], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${project.value?.name || '项目'}_数据导出.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('数据导出成功')
  } catch (error) {
    ElMessage.error('数据导出失败')
  } finally {
    exporting.value = false
  }
}

const handleEditData = (file: any) => {
  editData.value = JSON.parse(JSON.stringify(file.data_items || []))
  editDialogVisible.value = true
}

const saveEditData = async () => {
  savingEdit.value = true
  try {
    // 批量更新数据
    for (const item of editData.value) {
      await projectApi.updateData(projectId.value, item.id, {
        item_name: item.item_name,
        unit: item.unit,
        submitted_qty: item.submitted_qty,
        submitted_price: item.submitted_price,
        submitted_total: item.submitted_total,
        audited_qty: item.audited_qty,
        audited_price: item.audited_price,
        audited_total: item.audited_total,
        adjustment: item.adjustment
      })
    }
    ElMessage.success('数据保存成功')
    editDialogVisible.value = false
    loadData()
    loadSummary()
  } catch (error) {
    ElMessage.error('数据保存失败')
  } finally {
    savingEdit.value = false
  }
}

const previewReport = async (report: any) => {
  previewLoading.value = true
  previewDialogVisible.value = true
  try {
    const res = await reportApi.preview(report.id)
    previewContent.value = res.data.content
  } catch (error) {
    ElMessage.error('报告预览失败')
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
    link.download = report.file_name.replace('.docx', '.pdf')
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('PDF导出成功')
  } catch (error) {
    ElMessage.error('PDF导出失败')
  }
}

onMounted(() => {
  checkAdmin()
  loadProject()
  loadSummary()
  loadData()
  loadTemplates()
  loadReports()
})
</script>

<style scoped>
.project-detail {
  padding: 20px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.summary-content {
  display: flex;
  justify-content: space-around;
  padding: 20px;
}

.summary-item {
  text-align: center;
}

.summary-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 10px;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.summary-value.warning {
  color: #e6a23c;
}

.summary-value.success {
  color: #67c23a;
}

.warning {
  color: #e6a23c;
}

.success {
  color: #67c23a;
}

.mapping-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px 12px;
}

.mapping-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mapping-label {
  font-size: 12px;
  color: #606266;
}
</style>
