<template>
  <div class="account-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>账号管理</span>
          <div class="header-actions">
            <el-tag type="info" size="large">员工总数：{{ total }}</el-tag>
            <el-button type="primary" @click="openCreateDialog">
              <el-icon><Plus /></el-icon>
              新增员工
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" stripe size="small">
        <el-table-column prop="id" label="编号" width="80" align="center" />
        <el-table-column prop="username" label="用户名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="display_name" label="显示名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="role" label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'success'" size="small">
              {{ row.role === 'admin' ? '管理员' : '员工' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="warning"
              link
              size="small"
              :disabled="row.role === 'admin'"
              @click="resetPassword(row)"
            >
              重置密码
            </el-button>
            <el-button
              type="danger"
              link
              size="small"
              :disabled="row.role === 'admin' || row.id === currentUserId"
              @click="deleteUser(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增员工对话框 -->
    <el-dialog v-model="createDialogVisible" title="新增员工" width="480px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="至少 2 个字符" />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="createForm.display_name" placeholder="选填，默认与用户名相同" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input :value="defaultPassword" disabled>
            <template #append>默认</template>
          </el-input>
          <div class="form-tip">新增员工初始密码为 <b>{{ defaultPassword }}</b>，员工登录后可自行修改</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">确认新增</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { userApi } from '../../api'

const loading = ref(false)
const users = ref<any[]>([])
const total = ref(0)
const defaultPassword = '123456'

const createDialogVisible = ref(false)
const creating = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  username: '',
  display_name: ''
})

const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度在 2 到 50 个字符', trigger: 'blur' }
  ]
}

const currentUserId = computed(() => {
  try {
    const userStr = localStorage.getItem('user')
    if (userStr) return JSON.parse(userStr).id
  } catch {}
  return null
})

const formatDate = (date: string) => {
  if (!date) return ''
  return new Date(date).toLocaleString('zh-CN')
}

const loadUsers = async () => {
  loading.value = true
  try {
    const res = await userApi.getList()
    users.value = res.data.items
    total.value = res.data.total
  } catch {
    ElMessage.error('获取员工列表失败')
  } finally {
    loading.value = false
  }
}

const openCreateDialog = () => {
  createForm.username = ''
  createForm.display_name = ''
  createDialogVisible.value = true
}

const submitCreate = async () => {
  if (!createFormRef.value) return
  await createFormRef.value.validate(async (valid) => {
    if (!valid) return
    creating.value = true
    try {
      await userApi.create({
        username: createForm.username,
        display_name: createForm.display_name || undefined
      })
      ElMessage.success(`员工新增成功，初始密码：${defaultPassword}`)
      createDialogVisible.value = false
      loadUsers()
    } catch {
      // 错误已由拦截器提示
    } finally {
      creating.value = false
    }
  })
}

const resetPassword = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确认将员工 "${row.username}" 的密码重置为 ${defaultPassword}？`,
      '重置密码确认',
      { type: 'warning' }
    )
    await userApi.resetPassword(row.id)
    ElMessage.success(`密码已重置为 ${defaultPassword}`)
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      // 错误已由拦截器提示
    }
  }
}

const deleteUser = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确认删除员工 "${row.username}"？此操作不可恢复。`,
      '删除员工确认',
      { type: 'warning' }
    )
    await userApi.delete(row.id)
    ElMessage.success('员工已删除')
    loadUsers()
  } catch (e: any) {
    if (e !== 'cancel' && e?.message !== 'cancel') {
      // 错误已由拦截器提示
    }
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.account-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
  line-height: 1.5;
}
</style>
