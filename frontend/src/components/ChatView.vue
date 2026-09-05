<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, type Message, type UserInfo } from '../api'
import ChartRenderer from './ChartRenderer.vue'

const props = defineProps<{ user: UserInfo }>()
const emit = defineEmits<{ (e: 'logout'): void }>()

const messages = ref<Message[]>([])
const input = ref('')
const loading = ref(false)
const sessionId = ref('')
const courses = ref<{ key: string; label: string }[]>([])
type SkillName = 'overall_distribution' | 'risk_warning' | 'class_compare' | 'course_deep' | 'trend_compare' | 'group_diff'

const demoQuestions = [
  '我高数多少分',
  '我们班挂科率是多少',
  '年级各科平均分',
  '各班平均分对比',
]

async function init() {
  try {
    const meta = await api.metaIndicators()
    courses.value = meta.courses || []
    const saved = localStorage.getItem('chatbi_session')
    if (saved) {
      sessionId.value = saved
      messages.value = (await api.listMessages(saved)).map((m) => ({ ...m, can_feedback: m.role === 'assistant' }))
    } else {
      const created = await api.createSession()
      sessionId.value = created.session_id
      localStorage.setItem('chatbi_session', created.session_id)
    }
  } catch (err: any) {
    ElMessage.error(err.message || '初始化失败')
  }
}

onMounted(init)

async function send(text?: string) {
  const query = (text ?? input.value).trim()
  if (!query || loading.value) return
  messages.value.push({ id: Date.now(), role: 'user', text: query, created_at: new Date().toISOString() })
  input.value = ''
  loading.value = true
  scrollToBottom()
  try {
    const data = await api.chat(sessionId.value, query)
    messages.value.push({
      id: data.message_id,
      role: 'assistant',
      text: data.text,
      answer_type: data.answer_type,
      chart_config: data.chart_config,
      data_rows: data.data_rows,
      generated_sql: data.generated_sql,
      suggestions: data.suggestions,
      can_feedback: true,
      created_at: new Date().toISOString(),
    })
  } catch (err: any) {
    messages.value.push({ id: Date.now(), role: 'assistant', text: err.message || '请求失败', created_at: new Date().toISOString() })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function runSkill(skill: SkillName) {
  if (loading.value) return
  loading.value = true
  try {
    const data = await api.runSkill(skill)
    messages.value.push({
      id: Date.now(),
      role: 'assistant',
      text: data.text,
      answer_type: data.answer_type,
      chart_config: data.chart_config,
      data_rows: data.data_rows,
      generated_sql: data.generated_sql,
      created_at: new Date().toISOString(),
    })
  } catch (err: any) {
    ElMessage.error(err.message || 'Skill 执行失败')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function runAttribution() {
  if (loading.value) return
  loading.value = true
  try {
    const data = await api.attribution({})
    messages.value.push({
      id: Date.now(),
      role: 'assistant',
      text: data.text,
      answer_type: data.answer_type,
      data_rows: data.data_rows,
      created_at: new Date().toISOString(),
    })
  } catch (err: any) {
    ElMessage.error(err.message || '归因分析失败')
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function sendFeedback(msg: Message, feedback: 1 | -1) {
  if (!msg.can_feedback || typeof msg.id !== 'number') return
  let reason: string | null = null
  if (feedback === -1) {
    const result = await ElMessageBox.prompt('请填写点踩原因', '反馈', {
      inputPlaceholder: '数据不准确 / 计算逻辑错误 / 内容不满足 / 捏造数据 / 其他',
      confirmButtonText: '提交',
      cancelButtonText: '取消',
    }).catch(() => null)
    if (!result) return
    reason = result.value || null
  }
  try {
    await api.feedback({ message_id: msg.id, feedback, feedback_reason: reason })
    ElMessage.success('感谢反馈')
  } catch (err: any) {
    ElMessage.error(err.message || '反馈失败')
  }
}

function tableColumns(msg: Message) {
  const cols = msg.chart_config?.columns || []
  if (cols.length) return cols
  if (msg.data_rows?.length) {
    return Object.keys(msg.data_rows[0]).map((key) => ({ prop: key, label: key }))
  }
  return []
}

function downloadCsv(msg: Message) {
  if (!msg.data_rows?.length) return
  const keys = Object.keys(msg.data_rows[0])
  const rows = [keys.join(',')]
  for (const row of msg.data_rows) {
    rows.push(keys.map((key) => JSON.stringify(row[key] ?? '')).join(','))
  }
  const blob = new Blob(['\ufeff' + rows.join('\n')], { type: 'text/csv;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'chatbi-report.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

function downloadMarkdown(msg: Message) {
  const lines = [msg.text || '', '', '## 生成SQL', '```sql', msg.generated_sql || '', '```']
  if (msg.data_rows?.length) {
    lines.push('', '## 数据')
    const keys = Object.keys(msg.data_rows[0])
    lines.push('| ' + keys.join(' | ') + ' |')
    lines.push('| ' + keys.map(() => '---').join(' | ') + ' |')
    for (const row of msg.data_rows) {
      lines.push('| ' + keys.map((key) => String(row[key] ?? '')).join(' | ') + ' |')
    }
  }
  const blob = new Blob(['\ufeff' + lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'chatbi-report.md'
  a.click()
  URL.revokeObjectURL(a.href)
}

function chooseCourse(course: string) {
  send(`${course}平均分`)
}

function chooseSuggestion(item: any) {
  if (item.options && item.key === 'course') {
    return
  }
  if (item.key === 'metric' && item.options) {
    const first = item.options[0]
    if (first?.label) send(`查询${first.label}`)
    return
  }
  send(`查询${item.label || item.key}`)
}

function scrollToBottom() {
  nextTick(() => {
    const box = document.querySelector('.messages')
    if (box) box.scrollTop = box.scrollHeight
  })
}

function logout() {
  emit('logout')
}

const roleClass = computed(() => ({
  1: 'student',
  2: 'monitor',
  3: 'counselor',
}[props.user.role] || 'student'))
</script>

<template>
  <div class="chat-page">
    <header class="topbar">
      <div class="brand">学业 ChatBI</div>
      <div class="user-box">
        <span class="role-badge" :class="roleClass">{{ user.role_name }}</span>
        <span>{{ user.name }}</span>
        <el-button link type="primary" @click="logout">退出</el-button>
      </div>
    </header>

    <div class="layout">
      <aside class="sidebar">
        <div class="side-title">快捷分析</div>
        <el-button type="primary" plain style="width: 100%; margin-bottom: 10px" @click="runSkill('overall_distribution')">
          整体成绩分布
        </el-button>
        <el-button type="warning" plain style="width: 100%" @click="runSkill('risk_warning')">
          挂科风险预警
        </el-button>
        <el-button type="success" plain style="width: 100%; margin-top: 10px" @click="runSkill('class_compare')">
          班级横向对比
        </el-button>
        <el-button type="success" plain style="width: 100%; margin-top: 10px" @click="runSkill('course_deep')">
          单科深度分析
        </el-button>
        <el-button type="success" plain style="width: 100%; margin-top: 10px" @click="runSkill('trend_compare')">
          纵向趋势对比
        </el-button>
        <el-button type="success" plain style="width: 100%; margin-top: 10px" @click="runSkill('group_diff')">
          群体差异分析
        </el-button>
        <el-button type="danger" plain style="width: 100%; margin-top: 10px" @click="runAttribution">
          归因分析
        </el-button>
        <div class="side-title demo-title">试试这样问</div>
        <div class="demo-list">
          <el-button v-for="q in demoQuestions" :key="q" text size="small" @click="send(q)">
            {{ q }}
          </el-button>
        </div>
      </aside>

      <main class="conversation">
        <div class="messages">
          <div v-for="msg in messages" :key="`${msg.role}-${msg.id}`" class="message" :class="msg.role">
            <div class="bubble">
              <div class="text">{{ msg.text }}</div>
              <ChartRenderer v-if="msg.chart_config" :config="msg.chart_config" />
              <el-table
                v-if="msg.data_rows && msg.data_rows.length && (msg.chart_config?.type === 'table' || msg.chart_config?.show_table || (msg.answer_type === 'text' && !msg.generated_sql))"
                :data="msg.data_rows"
                border
                size="small"
                class="data-table"
              >
                <el-table-column
                  v-for="col in tableColumns(msg)"
                  :key="col.prop"
                  :prop="col.prop"
                  :label="col.label"
                />
              </el-table>
              <div v-if="msg.answer_type === 'clarify'" class="suggestions">
                <template v-for="suggestion in msg.suggestions || []" :key="suggestion.key">
                  <div class="suggestion-group">
                    <div class="suggestion-label">{{ suggestion.label }}</div>
                    <el-button
                      v-if="suggestion.key === 'course'"
                      v-for="course in suggestion.options"
                      :key="course"
                      size="small"
                      @click="chooseCourse(course)"
                    >
                      {{ course }}
                    </el-button>
                    <el-button v-else size="small" @click="chooseSuggestion(suggestion)">
                      {{ suggestion.label }}
                    </el-button>
                  </div>
                </template>
              </div>
              <div v-if="msg.generated_sql" class="sql-block">
                <code>{{ msg.generated_sql }}</code>
              </div>
              <div v-if="msg.role === 'assistant'" class="message-actions">
                <el-button
                  v-if="msg.can_feedback"
                  size="small"
                  text
                  @click="sendFeedback(msg, 1)"
                >
                  点赞
                </el-button>
                <el-button
                  v-if="msg.can_feedback"
                  size="small"
                  text
                  @click="sendFeedback(msg, -1)"
                >
                  点踩
                </el-button>
                <el-button
                  v-if="msg.data_rows?.length"
                  size="small"
                  text
                  @click="downloadCsv(msg)"
                >
                  导出CSV
                </el-button>
                <el-button size="small" text @click="downloadMarkdown(msg)">
                  导出Markdown
                </el-button>
              </div>
            </div>
          </div>
          <div v-if="loading" class="message assistant">
            <div class="bubble">正在分析…</div>
          </div>
        </div>

        <footer class="composer">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="输入问题，例如：我们班高数平均分是多少？"
            @keydown.enter.exact.prevent="send()"
          />
          <el-button type="primary" :loading="loading" @click="send()">发送</el-button>
        </footer>
      </main>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}
.brand {
  font-weight: 700;
  color: #1f2d3d;
}
.user-box {
  display: flex;
  align-items: center;
  gap: 10px;
}
.role-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  background: #eef2ff;
  color: #3b5bdb;
}
.role-badge.monitor {
  background: #e6f7ff;
  color: #0066cc;
}
.role-badge.counselor {
  background: #fff1e6;
  color: #cc6600;
}
.layout {
  flex: 1;
  display: flex;
  min-height: 0;
}
.sidebar {
  width: 230px;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  padding: 16px;
  overflow: auto;
}
.side-title {
  font-size: 13px;
  color: #999;
  margin-bottom: 8px;
}
.demo-title {
  margin-top: 22px;
}
.demo-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.conversation {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.message {
  display: flex;
  margin-bottom: 16px;
}
.message.user {
  justify-content: flex-end;
}
.message.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 720px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px 14px;
  line-height: 1.7;
}
.message.user .bubble {
  background: #eef2ff;
}
.text {
  white-space: pre-wrap;
}
.suggestions {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.suggestion-group {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.suggestion-label {
  color: #888;
  font-size: 13px;
}
.data-table {
  margin-top: 10px;
}
.sql-block {
  margin-top: 8px;
  background: #f7f8fa;
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
  overflow: auto;
  color: #555;
}
.message-actions {
  margin-top: 8px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  border-top: 1px solid #eef0f3;
  padding-top: 8px;
}
.composer {
  padding: 14px 24px 20px;
  background: #fff;
  border-top: 1px solid #e5e7eb;
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
</style>
