<template>
  <div class="script-control">
    <h3>第三步：测试脚本加载</h3>
    <div class="layout">
      <div class="editor">
        <p>请输入测试脚本 (格式: 分钟,房间号,动作,温度,风速)</p>
        <p class="tip">动作支持: ON(开机), TEMP(调温), FAN(调风), OFF(关机)</p>
        <textarea v-model="scriptContent" rows="15"></textarea>
      </div>
      <div class="controls">
        <div class="timer-box">
             <span class="label">当前系统时间:</span>
             <span class="time">{{ currentTime }} min</span>
        </div>
        <button class="run-btn" @click="startSimulation" :disabled="isRunning">
          {{ isRunning ? '测试运行中...' : '开始模拟' }}
        </button>
        <div class="logs" ref="logContainer">
          <div v-for="(log, i) in logs" :key="i" class="log-item">{{ log }}</div>
        </div>
        <button class="skip-btn" @click="$emit('next')">结束测试，进入监控</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue';
import request from '../utils/request';

// 默认脚本 (对应你的 Excel 示例)
const scriptContent = ref(`0,101,ON,25,HIGH
1,102,ON,25,MID
2,103,ON,25,LOW
3,101,TEMP,24,HIGH
4,102,FAN,25,HIGH
5,103,OFF,0,0
6,101,OFF,0,0`);

const isRunning = ref(false);
const currentTime = ref(0);
const logs = ref([]);
const logContainer = ref(null);

// 1分钟(系统) = 10秒(现实)，所以定时间隔是 10000ms
const TICK_INTERVAL = 10000;

const startSimulation = () => {
  if (!confirm('确认开始执行脚本？这将自动控制空调。')) return;

  isRunning.value = true;
  currentTime.value = 0;
  logs.value = ['>>> 模拟开始，等待第 0 分钟指令...'];

  const lines = scriptContent.value.split('\n').filter(l => l.trim());
  const events = lines.map(l => {
    // 解析 CSV 行
    const parts = l.split(',').map(s => s.trim());
    return {
        time: parseInt(parts[0]),
        room: parts[1],
        action: parts[2].toUpperCase(),
        temp: parts[3],
        fan: parts[4]
    };
  });

  // 立即执行第0分钟
  processEvents(0, events);

  const timer = setInterval(() => {
    currentTime.value++;
    processEvents(currentTime.value, events);

    // 自动滚动日志
    nextTick(() => {
        if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight;
    });

  }, TICK_INTERVAL);
};

const processEvents = (time, events) => {
  const currentEvents = events.filter(e => e.time === time);

  if (currentEvents.length > 0) {
      logs.value.push(`--- 第 ${time} 分钟 ---`);
      currentEvents.forEach(async (e) => {
        logs.value.push(`> 房间${e.room} 执行 ${e.action}`);
        try {
          // 串行调用接口确保状态正确
          if (e.action === 'ON') {
             // 开机前先设置参数，确保开机即是正确状态
             await request.post(`/ac/setTemp/${e.room}`, { target_temp: e.temp });
             await request.post(`/ac/setFanSpeed/${e.room}`, { fan_speed: e.fan });
             await request.post(`/ac/togglePower/${e.room}`, { power_status: 'ON' });

          } else if (e.action === 'OFF') {
             await request.post(`/ac/togglePower/${e.room}`, { power_status: 'OFF' });

          } else if (e.action === 'TEMP') {
             await request.post(`/ac/setTemp/${e.room}`, { target_temp: e.temp });

          } else if (e.action === 'FAN') {
             await request.post(`/ac/setFanSpeed/${e.room}`, { fan_speed: e.fan });
          }
        } catch (err) {
          logs.value.push(`[Error] 房间${e.room} 操作失败`);
        }
      });
  }
};
</script>

<style scoped>
.layout { display: flex; gap: 20px; height: 500px; }
.editor { flex: 1; display: flex; flex-direction: column; }
textarea { flex: 1; width: 100%; font-family: monospace; padding: 10px; border: 1px solid #ccc; resize: none; }
.controls { flex: 1; display: flex; flex-direction: column; gap: 10px; }
.timer-box { font-size: 1.2em; background: #fff; padding: 10px; border: 1px solid #eee; text-align: center; }
.timer-box .time { font-weight: bold; color: #409eff; font-size: 1.5em; margin-left: 10px; }
.logs { flex: 1; background: #1e1e1e; color: #00ff00; padding: 10px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 14px; border-radius: 4px; }
.run-btn { background: #e6a23c; color: white; padding: 12px; border: none; cursor: pointer; font-size: 1.1em; border-radius: 4px; }
.run-btn:disabled { background: #f3d19e; cursor: wait; }
.skip-btn { background: #409eff; color: white; padding: 12px; border: none; cursor: pointer; border-radius: 4px; }
.tip { font-size: 0.9em; color: #666; margin-bottom: 5px; }
</style>