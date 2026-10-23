<template>
  <div class="templates">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>模板管理</span>
          <el-button type="primary" @click="showUploadDialog">
            <el-icon><Upload /></el-icon>
            上传模板
          </el-button>
        </div>
      </template>

      <el-table :data="templates" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="模板名称" />
        <el-table-column prop="template_type" label="模板类型" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="previewTemplate(row)">
              预览
            </el-button>
            <el-button type="success" link @click="showVariablesDialog(row)">
              配置映射
            </el-button>
            <el-button type="warning" link @click="checkTemplate(row)">
              兼容性检查
            </el-button>
            <el-button type="danger" link @click="deleteTemplate(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上传模板对话框 -->
    <el-dialog v-model="dialogVisible" title="上传模板" width="500px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="模板名称" required>
          <el-input v-model="uploadForm.name" placeholder="请输入模板名称" />
        </el-form-item>
        <el-form-item label="模板类型" required>
          <el-select v-model="uploadForm.template_type" placeholder="请选择模板类型">
            <el-option label="预算评审报告" value="预算评审报告" />
            <el-option label="结算评审报告" value="结算评审报告" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item label="模板文件" required>
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
            accept=".docx"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">仅支持 .docx 文件</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload" :loading="uploading">
          上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 预览模板对话框 -->
    <el-dialog v-model="previewDialogVisible" title="模板预览" width="70%">
      <div v-loading="previewLoading">
        <pre class="preview-content">{{ previewContent }}</pre>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 变量映射配置对话框 -->
    <el-dialog v-model="variablesDialogVisible" title="模板变量映射配置" width="70%">
      <div v-loading="variablesLoading">
        <el-alert
          title="说明：{{变量名}} 为模板中的占位符，可在此为其配置映射的数据源路径（如 project.name、data.道路工程.合计 等）"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />
        <el-table :data="variables" stripe>
          <el-table-column prop="placeholder" label="模板变量" width="200" />
          <el-table-column label="映射数据源">
            <template #default="{ row }">
              <el-input v-model="row.field_name" placeholder="如 project.name（留空则使用默认填充逻辑）" clearable />
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="variablesDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveVariables" :loading="savingVariables">
          保存配置
        </el-button>
      </template>
    </el-dialog>

    <!-- 兼容性检查对话框 -->
    <el-dialog v-model="checkDialogVisible" title="模板兼容性检查" width="70%">
      <div v-loading="checkLoading">
        <el-alert
          :title="checkResult.is_compatible ? '模板结构兼容' : '模板存在兼容性问题'"
          :type="checkResult.is_compatible ? 'success' : 'warning'"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />

        <el-card v-if="checkResult.placeholders?.length" shadow="never" style="margin-bottom: 16px">
          <template #header>检测到的占位符 ({{ checkResult.placeholders.length }})</template>
          <el-tag v-for="ph in checkResult.placeholders" :key="ph" style="margin: 4px" v-text="'{{' + ph + '}}'" />
        </el-card>

        <el-card v-if="checkResult.engineering_types?.length" shadow="never" style="margin-bottom: 16px">
          <template #header>工程类型区段 ({{ checkResult.engineering_types.length }})</template>
          <el-table :data="checkResult.engineering_types" stripe size="small">
            <el-table-column prop="type" label="类型" width="120" />
            <el-table-column prop="header_text" label="标题文本" />
            <el-table-column label="核减子标题" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.has_reduced_subheader ? 'success' : 'danger'" size="small">
                  {{ row.has_reduced_subheader ? '有' : '无' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="核增子标题" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.has_increased_subheader ? 'success' : 'danger'" size="small">
                  {{ row.has_increased_subheader ? '有' : '无' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="detail_item_count" label="明细占位" width="100" align="center" />
          </el-table>
        </el-card>

        <el-descriptions v-if="checkResult.has_summary_paragraph !== undefined" border :column="1" style="margin-bottom: 16px">
          <el-descriptions-item label="汇总段落">
            <el-tag :type="checkResult.has_summary_paragraph ? 'success' : 'danger'" size="small">
              {{ checkResult.has_summary_paragraph ? '已找到' : '未找到' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-card v-if="checkResult.warnings?.length" shadow="never">
          <template #header>警告 ({{ checkResult.warnings.length }})</template>
          <el-alert
            v-for="(w, i) in checkResult.warnings"
            :key="i"
            :title="w"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 8px"
          />
        </el-card>
      </div>
      <template #footer>
        <el-button @click="checkDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadInstance, UploadFile } from 'element-plus'
import { templateApi } from '../api'

const loading = ref(false)
const uploading = ref(false)
const templates = ref<any[]>([])
const dialogVisible = ref(false)
const uploadRef = ref<UploadInstance>()
const selectedFile = ref<File | null>(null)

// 预览相关
const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewContent = ref('')

// 变量映射相关
const variablesDialogVisible = ref(false)
const variablesLoading = ref(false)
const savingVariables = ref(false)
const variables = ref<any[]>([])
const currentTemplate = ref<any>(null)

// 兼容性检查相关
const checkDialogVisible = ref(false)
const checkLoading = ref(false)
const checkResult = ref<any>({})

const uploadForm = ref({
  name: '',
  template_type: ''
})

const loadTemplates = async () => {
  loading.value = true
  try {
    const res = await templateApi.getList()
    templates.value = res.data
  } catch (error) {
    ElMessage.error('获取模板列表失败')
  } finally {
    loading.value = false
  }
}

const showUploadDialog = () => {
  uploadForm.value = {
    name: '',
    template_type: ''
  }
  selectedFile.value = null
  dialogVisible.value = true
}

const handleFileChange = (file: UploadFile) => {
  selectedFile.value = file.raw || null
}

const submitUpload = async () => {
  if (!uploadForm.value.name) {
    ElMessage.warning('请输入模板名称')
    return
  }
  if (!uploadForm.value.template_type) {
    ElMessage.warning('请选择模板类型')
    return
  }
  if (!selectedFile.value) {
    ElMessage.warning('请选择模板文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('name', uploadForm.value.name)
    formData.append('template_type', uploadForm.value.template_type)
    formData.append('file', selectedFile.value)

    await templateApi.upload(formData)
    ElMessage.success('上传成功')
    dialogVisible.value = false
    loadTemplates()
  } catch (error) {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
  }
}

const deleteTemplate = async (template: any) => {
  try {
    await ElMessageBox.confirm('确定要删除该模板吗？', '提示', {
      type: 'warning'
    })
    await templateApi.delete(template.id)
    ElMessage.success('删除成功')
    loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const previewTemplate = async (template: any) => {
  previewLoading.value = true
  previewDialogVisible.value = true
  previewContent.value = ''
  try {
    const res = await templateApi.preview(template.id)
    previewContent.value = res.data.content
  } catch (error) {
    ElMessage.error('预览失败')
  } finally {
    previewLoading.value = false
  }
}

const showVariablesDialog = async (template: any) => {
  currentTemplate.value = template
  variablesDialogVisible.value = true
  variablesLoading.value = true
  variables.value = []
  try {
    const res = await templateApi.getVariables(template.id)
    variables.value = res.data.variables || []
  } catch (error) {
    ElMessage.error('获取变量配置失败')
  } finally {
    variablesLoading.value = false
  }
}

const saveVariables = async () => {
  if (!currentTemplate.value) return
  savingVariables.value = true
  try {
    await templateApi.updateVariables(currentTemplate.value.id, {
      variables: variables.value
    })
    ElMessage.success('变量映射配置已保存')
    variablesDialogVisible.value = false
  } catch (error) {
    ElMessage.error('保存配置失败')
  } finally {
    savingVariables.value = false
  }
}

const checkTemplate = async (template: any) => {
  checkLoading.value = true
  checkDialogVisible.value = true
  checkResult.value = {}
  try {
    const res = await templateApi.check(template.id)
    checkResult.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '兼容性检查失败')
    checkDialogVisible.value = false
  } finally {
    checkLoading.value = false
  }
}

const formatDate = (date: string) => {
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.templates {
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
  max-height: 500px;
  overflow: auto;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
