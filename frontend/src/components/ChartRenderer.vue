<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{ config: any }>()
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function render() {
  if (!el.value || !props.config || props.config.type === 'table') return
  if (!chart) chart = echarts.init(el.value)
  const { type, title, x, series } = props.config
  const option: any = {
    title: { text: title || '', left: 'center', textStyle: { fontSize: 14 } },
    tooltip: {},
    grid: { left: 50, right: 24, top: 50, bottom: 70 },
    xAxis: { type: 'category', data: x || [], axisLabel: { interval: 0, rotate: 30, fontSize: 12 } },
    yAxis: { type: 'value' },
    series: series || [],
  }
  if (type === 'bar') {
    option.series = (series || []).map((s: any) => ({ ...s, type: 'bar' }))
  }
  if (type === 'line') {
    option.series = (series || []).map((s: any) => ({ ...s, type: 'line', smooth: true }))
  }
  if (type === 'gauge') {
    chart.setOption(
      {
        title: { text: title || '', left: 'center', textStyle: { fontSize: 14 } },
        series: [{ type: 'gauge', min: 0, max: 100, detail: { formatter: '{value}%' }, data: [{ value: props.config.value, name: title || '' }] }],
      },
      true,
    )
    return
  }
  chart.setOption(option, true)
}

function resize() {
  chart?.resize()
}

onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})
watch(() => props.config, render, { deep: true })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>

<template>
  <div ref="el" class="chart"></div>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 280px;
  margin-top: 8px;
}
</style>
