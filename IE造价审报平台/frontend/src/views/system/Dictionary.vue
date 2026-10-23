<template>
  <div class="dictionary-page">
    <el-page-header @back="goBack" title="返回" content="数据字典管理" class="page-header" />

    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>字典分类</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            新增字典项
          </el-button>
        </div>
      </template>

      <el-tabs v-model="activeCategory" @tab-change="loadList">
        <el-tab-pane
          v-for="cat in categories"
          :key="cat"
          :label="categoryLabel(cat)"
          :name="cat"
        />
      </el-tabs>

      <el-table :data="items" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="showDialog" :title="editing ? '编辑字典项' : '新增字典项'" width="500">
      <el-form :model="form" label-width="80px" ref="formRef">
        <el-form-item label="分类" v-if="!editing">
          <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
            <el-option v-for="cat in categories" :key="cat" :label="categoryLabel(cat)" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码" v-if="!editing">
          <el-input v-model="form.code" placeholder="如 road、m2" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="如 道路工程、平方米" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="999" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { dictionaryApi } from '../../api'

const router = useRouter()
const categories = ref<string[]>([])
const activeCategory = ref('')
const items = ref<any[]>([])
const loading = ref(false)
const showDialog = ref(false)
const editing = ref(false)
const submitting = ref(false)
const form = ref({
  id: 0,
  category: '',
  code: '',
  name: '',
  description: '',
  sort_order: 0
})

const goBack = () => router.push('/')

const categoryLabel = (cat: string) => {
  const map: Record<string, string> = {
    engineering_type: '工程类型',
    unit: '单位',
    status: '项目状态'
  }
  return map[cat] || cat
}

const loadCategories = async () => {
  try {
    const res = await dictionaryApi.getCategories()
    categories.value = res.data
    if (categories.value.length > 0 && !activeCategory.value) {
      activeCategory.value = categories.value[0]
      loadList()
    }
  } catch (e) {
    // 错误已处理
  }
}

const loadList = async () => {
  if (!activeCategory.value) return
  loading.value = true
  try {
    const res = await dictionaryApi.getList({ category: activeCategory.value })
    items.value = res.data
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.value = {
    id: 0,
    category: activeCategory.value,
    code: '',
    name: '',
    description: '',
    sort_order: 0
  }
}

const handleAdd = () => {
  editing.value = false
  resetForm()
  showDialog.value = true
}

const handleEdit = (row: any) => {
  editing.value = true
  form.value = { ...row }
  showDialog.value = true
}

const handleSubmit = async () => {
  if (!form.value.name) {
    ElMessage.warning('请填写名称')
    return
  }
  submitting.value = true
  try {
    if (editing.value) {
      await dictionaryApi.update(form.value.id, {
        name: form.value.name,
        description: form.value.description,
        sort_order: form.value.sort_order
      })
      ElMessage.success('更新成功')
    } else {
      if (!form.value.category || !form.value.code) {
        ElMessage.warning('请填写分类和编码')
        submitting.value = false
        return
      }
      await dictionaryApi.create({
        category: form.value.category,
        code: form.value.code,
        name: form.value.name,
        description: form.value.description,
        sort_order: form.value.sort_order
      })
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    loadList()
  } catch (e) {
    // 错误已处理
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定要删除 "${row.name}" 吗？`, '删除确认', { type: 'warning' })
    await dictionaryApi.delete(row.id)
    ElMessage.success('删除成功')
    loadList()
  } catch (e) {
    if (e !== 'cancel') {
      // 错误已处理
    }
  }
}

onMounted(() => {
  loadCategories()
})
</script>

<style scoped>
.dictionary-page {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.page-header {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
