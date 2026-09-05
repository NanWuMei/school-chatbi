<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type UserInfo } from './api'
import LoginView from './components/LoginView.vue'
import ChatView from './components/ChatView.vue'

const user = ref<UserInfo | null>(null)
const ready = ref(false)

onMounted(async () => {
  if (localStorage.getItem('chatbi_token')) {
    try {
      user.value = await api.me()
    } catch {
      localStorage.removeItem('chatbi_token')
    }
  }
  ready.value = true
})

function handleLogin(nextUser: UserInfo) {
  user.value = nextUser
}

function handleLogout() {
  localStorage.removeItem('chatbi_token')
  localStorage.removeItem('chatbi_session')
  user.value = null
}
</script>

<template>
  <div v-if="!ready" class="loading-wrap">加载中…</div>
  <LoginView v-else-if="!user" @login="handleLogin" />
  <ChatView v-else :user="user" @logout="handleLogout" />
</template>

<style>
html, body, #app {
  margin: 0;
  height: 100%;
  background: #f5f7fb;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}
.loading-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
}
</style>

