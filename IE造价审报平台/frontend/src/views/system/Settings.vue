<template>
  <div class="settings-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>系统设置</span>
        </div>
      </template>

      <el-form :model="settingsForm" label-width="180px" v-loading="loading">
        <el-form-item label="公司名称">
          <el-input v-model="settingsForm.company_name" />
        </el-form-item>

        <el-form-item label="报告标题前缀">
          <el-input v-model="settingsForm.report_title_prefix" />
        </el-form-item>

        <el-form-item label="最大上传文件大小(MB)">
          <el-input-number v-model="settingsForm.max_upload_size_mb" :min="1" :max="100" />
        </el-form-item>

        <el-form-item label="支持的工程类型">
          <el-input
            v-model="settingsForm.supported_engineering_types"
            type="textarea"
            :rows="3"
            placeholder="多个类型用逗号分隔"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="handleSave" :loading="saving">保存设置</el-button>
          <el-button @click="loadSettings">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { settingsApi } from '../../api'

const loading = ref(false)
const saving = ref(false)

const settingsForm = reactive({
  company_name: '',
  report_title_prefix: '',
  max_upload_size_mb: 10,
  supported_engineering_types: ''
})

const loadSettings = async () => {
  loading.value = true
  try {
    const res = await settingsApi.getAll()
    const settings = res.data

    const getSettingValue = (key: string, defaultValue: string = '') => {
      const setting = settings.find((s: any) => s.key === key)
      return setting ? setting.value : defaultValue
    }

    settingsForm.company_name = getSettingValue('company_name', 'IE工程造价咨询公司')
    settingsForm.report_title_prefix = getSettingValue('report_title_prefix', '工程造价评审报告')
    settingsForm.max_upload_size_mb = Number(getSettingValue('max_upload_size_mb', '10'))
    settingsForm.supported_engineering_types = getSettingValue('supported_engineering_types', '')
  } catch (error) {
    console.error('加载设置失败:', error)
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    await Promise.all([
      settingsApi.update('company_name', { key: 'company_name', value: settingsForm.company_name }),
      settingsApi.update('report_title_prefix', { key: 'report_title_prefix', value: settingsForm.report_title_prefix }),
      settingsApi.update('max_upload_size_mb', { key: 'max_upload_size_mb', value: String(settingsForm.max_upload_size_mb) }),
      settingsApi.update('supported_engineering_types', { key: 'supported_engineering_types', value: settingsForm.supported_engineering_types })
    ])

    ElMessage.success('设置已保存')
  } catch (error) {
    console.error('保存设置失败:', error)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<style scoped>
.settings-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
