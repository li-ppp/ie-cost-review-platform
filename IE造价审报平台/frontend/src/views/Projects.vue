<template>
  <div class="projects">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>项目管理</span>
          <el-button v-if="isAdmin" type="primary" @click="showCreateDialog">
            <el-icon><Plus /></el-icon>
            新建项目
          </el-button>
        </div>
      </template>

      <el-table :data="projects" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="项目名称" />
        <el-table-column prop="client_name" label="建设单位" />
        <el-table-column prop="project_type" label="工程类型" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewProject(row)">
              查看
            </el-button>
            <el-button v-if="isAdmin" type="primary" link @click="editProject(row)">
              编辑
            </el-button>
            <el-button v-if="isAdmin" type="danger" link @click="deleteProject(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建/编辑项目对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑项目' : '新建项目'"
      width="500px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="建设单位" prop="client_name">
          <el-input v-model="form.client_name" placeholder="请输入建设单位" />
        </el-form-item>
        <el-form-item label="工程类型" prop="project_type">
          <el-select v-model="form.project_type" placeholder="请选择工程类型">
            <el-option label="道路工程" value="道路工程" />
            <el-option label="排水工程" value="排水工程" />
            <el-option label="交安工程" value="交安工程" />
            <el-option label="桥涵工程" value="桥涵工程" />
            <el-option label="照明工程" value="照明工程" />
            <el-option label="电力工程" value="电力工程" />
            <el-option label="通信工程" value="通信工程" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="form.status" placeholder="请选择状态">
            <el-option label="草稿" value="draft" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance } from 'element-plus'
import { projectApi } from '../api'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const projects = ref<any[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref<FormInstance>()
const currentProjectId = ref<number>()
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

const form = ref({
  name: '',
  client_name: '',
  project_type: '',
  status: 'draft'
})

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  client_name: [{ required: true, message: '请输入建设单位', trigger: 'blur' }],
  project_type: [{ required: true, message: '请选择工程类型', trigger: 'change' }]
}

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

const showCreateDialog = () => {
  isEdit.value = false
  form.value = {
    name: '',
    client_name: '',
    project_type: '',
    status: 'draft'
  }
  dialogVisible.value = true
}

const editProject = (project: any) => {
  isEdit.value = true
  currentProjectId.value = project.id
  form.value = { ...project }
  dialogVisible.value = true
}

const viewProject = (project: any) => {
  router.push(`/projects/${project.id}`)
}

const deleteProject = async (project: any) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目吗？', '提示', {
      type: 'warning'
    })
    await projectApi.delete(project.id)
    ElMessage.success('删除成功')
    loadProjects()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const submitForm = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (isEdit.value && currentProjectId.value) {
        await projectApi.update(currentProjectId.value, form.value)
        ElMessage.success('更新成功')
      } else {
        await projectApi.create(form.value)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      loadProjects()
    } catch (error) {
      ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
    } finally {
      submitting.value = false
    }
  })
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

onMounted(() => {
  checkAdmin()
  loadProjects()
})
</script>

<style scoped>
.projects {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
