<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type UserInfo } from '../api'

const emit = defineEmits<{ (e: 'login', user: UserInfo): void }>()
const loading = ref(false)
const form = reactive({ user_id: '', password: '' })

const demoAccounts = [
  { label: '学生', id: '20230001', password: 'student123' },
  { label: '班长', id: 'monitor01', password: 'monitor123' },
  { label: '辅导员', id: 'counselor01', password: 'counselor123' },
]

async function submit() {
  loading.value = true
  try {
    const data = await api.login(form.user_id, form.password)
    localStorage.setItem('chatbi_token', data.access_token)
    localStorage.removeItem('chatbi_session')
    emit('login', data.user)
  } catch (err: any) {
    ElMessage.error(err.message || '登录失败')
  } finally {
    loading.value = false
  }
}

function fill(account: { id: string; password: string }) {
  form.user_id = account.id
  form.password = account.password
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1>学业 ChatBI</h1>
      <p class="subtitle">对话式成绩智能分析助手</p>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="form.user_id" placeholder="请输入学号或工号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" @keyup.enter="submit" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          登录
        </el-button>
      </el-form>
      <div class="demo-tip">演示账号：</div>
      <div class="demo-accounts">
        <el-button v-for="account in demoAccounts" :key="account.id" size="small" @click="fill(account)">
          {{ account.label }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef5ff 0%, #f7f0ff 100%);
}
.login-card {
  width: 400px;
  padding: 12px;
}
h1 {
  margin: 0 0 4px;
  font-size: 26px;
  color: #1f2d3d;
}
.subtitle {
  margin: 0 0 20px;
  color: #888;
}
.demo-tip {
  margin: 18px 0 8px;
  color: #666;
  font-size: 13px;
}
.demo-accounts {
  display: flex;
  gap: 8px;
}
</style>
