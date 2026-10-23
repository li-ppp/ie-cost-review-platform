<template>
  <div class="backup-page">
    <el-page-header @back="goBack" title="返回" content="数据备份与恢复" class="page-header" />

    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>备份记录</span>
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            创建备份
          </el-button>
        </div>
      </template>

      <el-alert
        title="提示：恢复操作会覆盖当前所有数据，请谨慎操作。建议恢复后重启服务。"
        type="warning"
        :closable="false"
        show-icon
        class="warning-alert"
      />

      <el-table :data="backups" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="filename" label="备份名称" min-width="200" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="warning" @click="handleRestore(row)">恢复</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建备份对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建数据备份" width="500">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="描述">
          <el-input
            v-model="createForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选：备份描述信息"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">确认备份</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { backupApi } from '../../api'

const router = useRouter()
const backups = ref<any[]>([])
const loading = ref(false)
const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({ description: '' })

const goBack = () => router.push('/')

const formatDate = (d: string) => {
  if (!d) return ''
  return new Date(d).toLocaleString('zh-CN')
}

const formatSize = (bytes: number) => {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

const loadBackups = async () => {
  loading.value = true
  try {
    const res = await backupApi.list()
    backups.value = res.data
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  creating.value = true
  try {
    await backupApi.create({ description: createForm.value.description })
    ElMessage.success('备份创建成功')
    showCreateDialog.value = false
    createForm.value.description = ''
    loadBackups()
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    creating.value = false
  }
}

const handleRestore = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要从备份 "${row.filename}" 恢复数据吗？此操作会覆盖当前所有数据，且不可撤销！`,
      '恢复确认',
      { type: 'warning', confirmButtonText: '确认恢复', cancelButtonText: '取消' }
    )
    await backupApi.restore(row.id)
    ElMessage.success('数据恢复成功，建议重启服务')
    loadBackups()
  } catch (e) {
    if (e !== 'cancel') {
      // 错误已由拦截器处理
    }
  }
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除备份 "${row.filename}" 吗？`,
      '删除确认',
      { type: 'warning' }
    )
    await backupApi.delete(row.id)
    ElMessage.success('备份已删除')
    loadBackups()
  } catch (e) {
    if (e !== 'cancel') {
      // 错误已由拦截器处理
    }
  }
}

onMounted(() => {
  loadBackups()
})
</script>

<style scoped>
.backup-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  margin-bottom: 20px;
}
.main-card {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.warning-alert {
  margin-bottom: 16px;
}
</style>
