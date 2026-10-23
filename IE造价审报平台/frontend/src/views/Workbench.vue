<template>
  <div class="workbench">
    <el-card class="header-card">
      <div class="header-content">
        <div>
          <h1>工程造价审报工作台</h1>
          <p>一站式完成项目创建、数据上传、报告生成</p>
        </div>
        <div class="header-actions">
          <el-button v-if="isAdmin" type="info" @click="$router.push('/settings')">
            <el-icon><Setting /></el-icon>
            系统设置
          </el-button>
          <el-button v-if="isAdmin" type="warning" @click="$router.push('/logs')">
            <el-icon><Document /></el-icon>
            操作日志
          </el-button>
          <el-button v-if="isAdmin" type="success" @click="$router.push('/dictionary')">
            <el-icon><Collection /></el-icon>
            数据字典
          </el-button>
          <el-button v-if="isAdmin" type="primary" @click="$router.push('/backup')">
            <el-icon><FolderOpened /></el-icon>
            数据备份
          </el-button>
          <el-button type="primary" size="large" @click="showCreateProjectDialog">
            <el-icon><Plus /></el-icon>
            新建项目
          </el-button>
          <el-button type="danger" @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            退出登录
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>我的项目</span>
          <el-input
            v-model="searchText"
            placeholder="搜索项目名称..."
            style="width: 300px"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>

      <el-table :data="filteredProjects" v-loading="loading" stripe>
        <el-table-column prop="name" label="项目名称" min-width="200" />
        <el-table-column prop="client_name" label="建设单位" width="150" />
        <el-table-column prop="project_type" label="工程类型" width="120" />
        <el-table-column label="Excel数据" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.excel_count > 0 ? 'success' : 'info'" size="small">
              {{ row.excel_count || 0 }} 个文件
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="报告状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.report_count > 0 ? 'success' : 'info'" size="small">
              {{ row.report_count || 0 }} 份报告
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="420" fixed="right">
          <template #default="{ row }">
            <div class="action-btns">
              <el-button type="primary" link size="small" @click="showUploadDialog(row)">
                <el-icon><Upload /></el-icon>
                上传Excel
              </el-button>
              <el-button type="success" link size="small" @click="showGenerateDialog(row)" :disabled="!row.excel_count">
                <el-icon><Document /></el-icon>
                生成报告
              </el-button>
              <el-button v-if="row.report_count > 0" type="warning" link size="small" @click="showNewVersionDialog(row)">
                <el-icon><RefreshRight /></el-icon>
                新建版本
              </el-button>
              <el-button type="info" link size="small" @click="viewProjectReports(row)">
                <el-icon><View /></el-icon>
                查看报告
              </el-button>
              <el-button v-if="isAdmin" type="danger" link size="small" @click="deleteProject(row)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建项目" width="500px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="项目名称" required>
          <el-input v-model="createForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="建设单位">
          <el-input v-model="createForm.client_name" placeholder="请输入建设单位名称" />
        </el-form-item>
        <el-form-item label="工程类型">
          <el-select v-model="createForm.project_type" placeholder="请选择工程类型" style="width: 100%">
            <el-option label="道路工程" value="道路工程" />
            <el-option label="排水工程" value="排水工程" />
            <el-option label="交通安全" value="交通安全" />
            <el-option label="桥梁工程" value="桥梁工程" />
            <el-option label="照明工程" value="照明工程" />
            <el-option label="电力工程" value="电力工程" />
            <el-option label="通信工程" value="通信工程" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createProject" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- 上传Excel对话框 -->
    <el-dialog v-model="uploadDialogVisible" :title="`上传Excel - ${currentProject?.name}`" width="700px">
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

      <!-- 预览结果 -->
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

      <el-divider />

      <h4 style="margin-bottom: 10px">已上传文件</h4>
      <el-table :data="currentExcelFiles" stripe max-height="300">
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="engineering_type" label="工程类型" width="120" />
        <el-table-column label="数据项" width="100" align="center">
          <template #default="{ row }">
            {{ row.data_items?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewExcelData(row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
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

    <!-- 生成报告对话框 -->
    <el-dialog v-model="generateDialogVisible" :title="`生成报告 - ${currentProject?.name}`" width="500px">
      <el-form :model="generateForm" label-width="100px">
        <el-form-item label="选择模板" required>
          <el-select v-model="generateForm.template_id" placeholder="请选择报告模板" style="width: 100%">
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="template.name"
              :value="template.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="info" @click="previewTemplate" :disabled="!generateForm.template_id">
            <el-icon><View /></el-icon>
            预览模板
          </el-button>
        </el-form-item>
        <el-form-item>
          <el-alert
            title="提示"
            type="info"
            :closable="false"
          >
            将根据项目数据和所选模板自动生成评审报告
          </el-alert>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="generateReport" :loading="generating">生成报告</el-button>
      </template>
    </el-dialog>

    <!-- 预览模板对话框 -->
    <el-dialog v-model="previewDialogVisible" title="模板预览" width="70%">
      <div v-loading="previewLoading">
        <h3 style="margin-bottom: 15px">{{ previewData.name }}</h3>
        <div class="template-preview-content">
          <pre>{{ previewData.content }}</pre>
        </div>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 查看报告对话框 -->
    <el-dialog v-model="reportsDialogVisible" :title="`报告列表 - ${currentProject?.name}`" width="850px">
      <el-table :data="currentReports" stripe>
        <el-table-column prop="file_name" label="报告名称" min-width="200" />
        <el-table-column label="版本" width="80" align="center">
          <template #default="{ row }">
            <el-tag type="primary" size="small">v{{ row.version || 1 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'generated' ? 'success' : 'info'" size="small">
              {{ row.status === 'generated' ? '已生成' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.generated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="downloadReport(row)">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 新建版本对话框 -->
    <el-dialog v-model="newVersionDialogVisible" :title="`新建版本 - ${currentProject?.name}`" width="700px">
      <el-alert
        title="新建版本说明"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        上传新的 Excel 数据后，系统将基于最新数据重新生成报告，版本号自动递增（v1 → v2 → v3...）。
      </el-alert>
      <el-upload
        ref="newVersionUploadRef"
        :auto-upload="false"
        :on-change="handleNewVersionFileChange"
        :on-remove="handleNewVersionFileRemove"
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
            仅支持 .xlsx 文件，单个文件不超过10MB。上传后将自动生成新版本报告。
          </div>
        </template>
      </el-upload>

      <div v-if="newVersionPreviewResult" style="margin-top: 16px">
        <el-alert
          :title="`解析到 ${newVersionPreviewResult.total_sheets} 个工作表`"
          :type="newVersionPreviewResult.warnings?.length ? 'warning' : 'success'"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <el-card v-for="(sheet, idx) in newVersionPreviewResult.sheets" :key="idx" shadow="never" style="margin-bottom: 12px">
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
          v-for="(w, i) in newVersionPreviewResult.warnings || []"
          :key="i"
          :title="w"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        />
      </div>

      <template #footer>
        <el-button @click="newVersionDialogVisible = false">取消</el-button>
        <el-button type="warning" @click="previewNewVersionUpload" :loading="previewingNewVersion" :disabled="!selectedNewVersionFile">
          <el-icon><View /></el-icon>
          预览解析结果
        </el-button>
        <el-button type="primary" @click="confirmNewVersionUpload" :loading="uploadingNewVersion" :disabled="!selectedNewVersionFile">
          <el-icon><Upload /></el-icon>
          上传并生成新版本
        </el-button>
      </template>
    </el-dialog>

    <!-- 查看Excel数据对话框 -->
    <el-dialog v-model="dataDialogVisible" title="Excel数据详情" width="90%">
      <el-table :data="currentData" stripe max-height="500">
        <el-table-column prop="item_name" label="项目名称" min-width="200" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, RefreshRight } from '@element-plus/icons-vue'
import { projectApi, templateApi, reportApi } from '../api'
import type { UploadFile } from 'element-plus'

const router = useRouter()

const loading = ref(false)
const creating = ref(false)
const generating = ref(false)
const searchText = ref('')
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

const projects = ref<any[]>([])
const templates = ref<any[]>([])
const currentProject = ref<any>(null)
const currentExcelFiles = ref<any[]>([])
const currentReports = ref<any[]>([])
const currentData = ref<any[]>([])

const createDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const generateDialogVisible = ref(false)
const reportsDialogVisible = ref(false)
const dataDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewData = ref({ name: '', content: '' })

// Excel 预览与上传
const selectedExcelFile = ref<File | null>(null)
const previewingExcel = ref(false)
const uploadingExcel = ref(false)
const excelPreviewResult = ref<any>(null)
const manualMappings = ref<Record<string, Record<string, number>>>({})

// 新建版本
const newVersionDialogVisible = ref(false)
const selectedNewVersionFile = ref<File | null>(null)
const previewingNewVersion = ref(false)
const uploadingNewVersion = ref(false)
const newVersionPreviewResult = ref<any>(null)
const newVersionUploadRef = ref()

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

const initManualMappings = (previewResult: any = null) => {
  const source = previewResult || excelPreviewResult.value
  const result: Record<string, Record<string, number>> = {}
  if (source?.sheets) {
    for (const sheet of source.sheets) {
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

const createForm = ref({
  name: '',
  client_name: '',
  project_type: ''
})

const generateForm = ref({
  template_id: null as number | null
})

const uploadRef = ref()

const filteredProjects = computed(() => {
  if (!searchText.value) return projects.value
  return projects.value.filter(p =>
    p.name.toLowerCase().includes(searchText.value.toLowerCase())
  )
})

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

const loadProjects = async () => {
  loading.value = true
  try {
    const res = await projectApi.getList()
    projects.value = res.data
  } catch (error) {
    ElMessage.error('获取项目列表失败')
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

const showCreateProjectDialog = () => {
  createForm.value = { name: '', client_name: '', project_type: '' }
  createDialogVisible.value = true
}

const createProject = async () => {
  if (!createForm.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }

  creating.value = true
  try {
    await projectApi.create(createForm.value)
    ElMessage.success('项目创建成功')
    createDialogVisible.value = false
    loadProjects()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

const showUploadDialog = async (project: any) => {
  currentProject.value = project
  uploadDialogVisible.value = true
  selectedExcelFile.value = null
  excelPreviewResult.value = null
  if (uploadRef.value) uploadRef.value.clearFiles()
  await loadProjectExcelFiles(project.id)
}

const loadProjectExcelFiles = async (projectId: number) => {
  try {
    const res = await projectApi.getData(projectId)
    currentExcelFiles.value = res.data
  } catch (error) {
    console.error('获取Excel文件列表失败')
  }
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
  if (!selectedExcelFile.value || !currentProject.value) return
  previewingExcel.value = true
  try {
    const res = await projectApi.previewExcel(currentProject.value.id, selectedExcelFile.value)
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
  if (!selectedExcelFile.value || !currentProject.value) return
  uploadingExcel.value = true
  try {
    const mappings = manualMappings.value && Object.keys(manualMappings.value).length > 0
      ? manualMappings.value
      : undefined
    const res = await projectApi.uploadExcel(currentProject.value.id, selectedExcelFile.value, mappings)
    ElMessage.success(`上传成功，共 ${res.data.items_count} 项`)
    selectedExcelFile.value = null
    excelPreviewResult.value = null
    manualMappings.value = {}
    if (uploadRef.value) uploadRef.value.clearFiles()
    loadProjectExcelFiles(currentProject.value.id)
    loadProjects()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '上传失败')
  } finally {
    uploadingExcel.value = false
  }
}

const viewExcelData = (file: any) => {
  currentData.value = file.data_items || []
  dataDialogVisible.value = true
}

const previewTemplate = async () => {
  if (!generateForm.value.template_id) return
  
  previewLoading.value = true
  try {
    const res = await templateApi.preview(generateForm.value.template_id)
    previewData.value = res.data
    previewDialogVisible.value = true
  } catch (error) {
    ElMessage.error('预览模板失败')
  } finally {
    previewLoading.value = false
  }
}

const showGenerateDialog = (project: any) => {
  if (!project.excel_count) {
    ElMessage.warning('请先上传Excel数据')
    return
  }
  currentProject.value = project
  generateForm.value.template_id = null
  generateDialogVisible.value = true
}

const generateReport = async () => {
  if (!generateForm.value.template_id) {
    ElMessage.warning('请选择模板')
    return
  }

  generating.value = true
  try {
    const res = await reportApi.generate({
      project_id: currentProject.value.id,
      template_id: generateForm.value.template_id
    })
    const reportId = res.data.id
    generateDialogVisible.value = false
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
        loadProjects()
        return
      }
      if (attempts >= maxAttempts) {
        generatingDialogVisible.value = false
        ElMessage.warning('报告生成超时，请稍后在报告列表查看')
        loadProjects()
        return
      }
      pollTimer = setTimeout(check, 2000)
    } catch (error) {
      generatingDialogVisible.value = false
      ElMessage.error('获取报告状态失败')
      loadProjects()
    }
  }
  check()
}

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})

const viewProjectReports = async (project: any) => {
  currentProject.value = project
  try {
    const res = await reportApi.getByProject(project.id)
    currentReports.value = res.data
    reportsDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取报告列表失败')
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

const deleteProject = async (project: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除项目"${project.name}"吗？此操作将同时删除所有相关数据和报告。`,
      '确认删除',
      { type: 'warning' }
    )

    await projectApi.delete(project.id)
    ElMessage.success('删除成功')
    loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString('zh-CN')
}

const formatNumber = (value: number) => {
  return value?.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '-'
}

// ===== 新建版本相关 =====
const showNewVersionDialog = (project: any) => {
  currentProject.value = project
  newVersionDialogVisible.value = true
  selectedNewVersionFile.value = null
  newVersionPreviewResult.value = null
  manualMappings.value = {}
  if (newVersionUploadRef.value) newVersionUploadRef.value.clearFiles()
}

const handleNewVersionFileChange = (file: UploadFile) => {
  const raw = file.raw as File
  if (!raw) return
  if (!raw.name.endsWith('.xlsx')) {
    ElMessage.error('只能上传 .xlsx 格式的 Excel 文件')
    newVersionUploadRef.value?.clearFiles()
    return
  }
  if (raw.size / 1024 / 1024 >= 10) {
    ElMessage.error('文件大小不能超过10MB')
    newVersionUploadRef.value?.clearFiles()
    return
  }
  selectedNewVersionFile.value = raw
  newVersionPreviewResult.value = null
}

const handleNewVersionFileRemove = () => {
  selectedNewVersionFile.value = null
  newVersionPreviewResult.value = null
}

const previewNewVersionUpload = async () => {
  if (!selectedNewVersionFile.value || !currentProject.value) return
  previewingNewVersion.value = true
  try {
    const res = await projectApi.previewExcel(currentProject.value.id, selectedNewVersionFile.value)
    newVersionPreviewResult.value = res.data
    initManualMappings(newVersionPreviewResult.value)
    if (newVersionPreviewResult.value.warnings?.length) {
      ElMessage.warning('解析完成，但存在警告，请检查')
    } else {
      ElMessage.success('解析完成，可上传并生成新版本')
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '预览失败')
  } finally {
    previewingNewVersion.value = false
  }
}

const confirmNewVersionUpload = async () => {
  if (!selectedNewVersionFile.value || !currentProject.value) return
  uploadingNewVersion.value = true
  try {
    // 1. 上传新 Excel 数据（覆盖旧数据，带手工映射）
    await projectApi.uploadExcel(
      currentProject.value.id,
      selectedNewVersionFile.value,
      Object.keys(manualMappings.value).length > 0 ? manualMappings.value : undefined
    )
    // 2. 获取项目最新报告
    const reportsRes = await reportApi.getByProject(currentProject.value.id)
    const reports = reportsRes.data || []
    if (reports.length === 0) {
      ElMessage.warning('Excel 已更新，但未找到已有报告，请先生成报告')
      newVersionDialogVisible.value = false
      loadProjects()
      return
    }
    // 找到最新版本（version 最大的）
    const latestReport = reports.reduce((max: any, r: any) =>
      (r.version || 1) > (max.version || 1) ? r : max, reports[0])
    // 3. 基于最新报告创建新版本
    const newReport = await reportApi.newVersion(latestReport.id)
    const newVer = newReport.data.version || 2
    ElMessage.success(`新版本 v${newVer} 已生成`)
    newVersionDialogVisible.value = false
    selectedNewVersionFile.value = null
    newVersionPreviewResult.value = null
    manualMappings.value = {}
    if (newVersionUploadRef.value) newVersionUploadRef.value.clearFiles()
    loadProjects()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '新建版本失败')
  } finally {
    uploadingNewVersion.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  ElMessage.success('已退出登录')
  router.push('/login')
}

onMounted(() => {
  checkAdmin()
  loadProjects()
  loadTemplates()
})
</script>

<style scoped>
.workbench {
  padding: 20px;
}

.header-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h1 {
  font-size: 28px;
  margin-bottom: 8px;
}

.header-content p {
  font-size: 14px;
  opacity: 0.9;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

.warning {
  color: #e6a23c;
}

.action-btns {
  display: flex;
  flex-wrap: nowrap;
  gap: 2px;
  align-items: center;
}

.action-btns .el-button {
  margin-left: 0 !important;
  padding: 5px 8px;
}

.action-btns .el-button + .el-button {
  margin-left: 0 !important;
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
