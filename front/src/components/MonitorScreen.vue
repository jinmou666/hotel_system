<template>
  <div class="monitor-screen">
    <div class="top-control-bar">
      <div class="left-info">
        <h3>第四步：实时监控 & 测试执行</h3>
        <div class="status-box">
           系统时间: <span class="time">{{ systemTime }} min</span>
           <span v-if="isRunning" class="tag running">运行中</span>
           <span v-else class="tag paused">等待启动</span>
        </div>
      </div>

      <div class="center-actions">
        <button v-if="!isRunning && !isFinished" class="start-btn" @click="startTest">▶ 开始执行测试用例</button>
        <button v-else-if="isRunning" class="stop-btn" @click="stopTest">⏸ 暂停/停止</button>
        <span v-else class="finished-text">✅ 测试已结束</span>
      </div>

      <div class="right-actions">
        <button class="next-btn" @click="$emit('next')">进入结账环节 →</button>
      </div>
    </div>

    <div class="main-content">
      <div class="monitor-panel">
        <table class="data-table">
          <thead>
            <tr>
              <th>房间</th>
              <th>室温</th>
              <th>目标</th>
              <th>风速</th>
              <th>运行状态</th> <!-- 修改列名 -->
              <th>费率</th>
              <th>当前费</th>
              <th>总费</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="room in roomList" :key="room.room_id" :class="{ 'active-row': room.power_status === 'ON' }">
              <td class="room-id">{{ room.room_id }}</td>
              <td class="temp">{{ room.current_temp }}°C</td>
              <td>{{ room.target_temp }}°C</td>
              <td><span class="tag" :class="room.fan_speed">{{ room.fan_speed }}</span></td>
              <td>
                <!-- 核心修改：使用 sched_status 显示真实调度状态 -->
                <span class="status-badge" :class="room.sched_status">
                  {{ formatStatus(room.sched_status) }}
                </span>
              </td>
              <td>{{ room.fee_rate }}</td>
              <td>{{ room.current_fee }}</td>
              <td class="total">{{ room.total_fee }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="log-panel">
        <div class="log-header">执行日志 ({{ scriptEvents.length }} 条待执行)</div>
        <div class="log-content" ref="logRef">
          <div v-for="(log, i) in logs" :key="i" class="log-item">{{ log }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import request from '../utils/request';

const props = defineProps({
  scriptEvents: { type: Array, default: () => [] }
});

const roomList = ref([]);
const logs = ref(['>>> 等待开始...']);
const systemTime = ref(0);
const isRunning = ref(false);
const isFinished = ref(false);
const logRef = ref(null);

let monitorTimer = null;
let scriptTimer = null;
const TICK_INTERVAL = 10000;

const formatStatus = (status) => {
  const map = {
    'RUNNING': '送风中',
    'WAITING': '等待调度',
    'IDLE': '待机/回温',
    'OFF': '关机'
  };
  return map[status] || status;
};

const fetchStatus = async () => {
  const ids = ['101', '102', '103', '104', '105'];
  try {
      const promises = ids.map(id => request.get(`/ac/roomState/${id}`));
      const results = await Promise.all(promises);
      roomList.value = results;
  } catch (e) { console.error("监控刷新失败", e); }
};

const startTest = () => {
  if (props.scriptEvents.length === 0) {
    alert("未检测到脚本数据！");
    return;
  }
  isRunning.value = true;
  logs.value.push(`>>> 测试启动`);
  executeEventsForTime(systemTime.value);
  scriptTimer = setInterval(() => {
    systemTime.value++;
    executeEventsForTime(systemTime.value);
    const maxTime = Math.max(...props.scriptEvents.map(e => e.time));
    if (systemTime.value > maxTime + 2) { // 多等2分钟观察回温
       stopTest();
       isFinished.value = true;
       logs.value.push(">>> 测试结束");
    }
  }, TICK_INTERVAL);
};

const stopTest = () => {
  isRunning.value = false;
  if (scriptTimer) clearInterval(scriptTimer);
};

const executeEventsForTime = async (time) => {
  const currentEvents = props.scriptEvents.filter(e => e.time === time);
  if (currentEvents.length > 0) {
    logs.value.push(`--- 第 ${time} 分钟 ---`);
    // 按房间分组串行
    const roomEventsMap = {};
    currentEvents.forEach(e => {
        if (!roomEventsMap[e.room]) roomEventsMap[e.room] = [];
        roomEventsMap[e.room].push(e);
    });

    const promises = Object.keys(roomEventsMap).map(async (roomId) => {
        const events = roomEventsMap[roomId];
        for (const e of events) {
            try {
                logs.value.push(`[发送] R${e.room} -> ${e.action}`);
                if (e.action === 'ON') {
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
                logs.value.push(`[Error] R${e.room}: ${err.message}`);
            }
        }
    });
    await Promise.all(promises);
    nextTick(() => { if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight; });
  }
};

onMounted(() => {
  fetchStatus();
  monitorTimer = setInterval(fetchStatus, 1000);
});

onUnmounted(() => {
  clearInterval(monitorTimer);
  clearInterval(scriptTimer);
});
</script>

<style scoped>
/* 复用之前的样式，增加状态徽章样式 */
.monitor-screen { display: flex; flex-direction: column; height: 100%; }
.top-control-bar { display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
.status-box .time { font-weight: bold; color: #409eff; font-size: 1.4em; }
.tag { padding: 2px 8px; border-radius: 4px; color: white; font-size: 0.8em; }
.tag.running { background: #67c23a; }
.tag.paused { background: #909399; }
.start-btn { background: #67c23a; color: white; padding: 10px 25px; border: none; border-radius: 4px; cursor: pointer; }
.stop-btn { background: #e6a23c; color: white; padding: 10px 25px; border: none; border-radius: 4px; cursor: pointer; }
.next-btn { background: #409eff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
.main-content { display: flex; gap: 20px; height: 500px; }
.monitor-panel { flex: 3; overflow-y: auto; }
.log-panel { flex: 1; background: #2b2b2b; color: #ccc; display: flex; flex-direction: column; border-radius: 8px; }
.log-header { background: #1a1a1a; padding: 10px; font-weight: bold; }
.log-content { flex: 1; overflow-y: auto; padding: 10px; font-family: monospace; }
.data-table { width: 100%; border-collapse: collapse; background: white; }
th, td { border: 1px solid #eee; padding: 10px; text-align: center; }
.active-row { background-color: #f0f9eb; }
.temp { color: #f56c6c; font-weight: bold; }
.total { color: #67c23a; }
.tag.HIGH { background: #f56c6c; }
.tag.MID, .tag.MEDIUM { background: #e6a23c; }
.tag.LOW { background: #67c23a; }

/* 新增：状态徽章样式 */
.status-badge { padding: 4px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold; }
.status-badge.RUNNING { background-color: #67c23a; color: white; } /* 绿色 */
.status-badge.WAITING { background-color: #e6a23c; color: white; } /* 黄色 */
.status-badge.IDLE { background-color: #909399; color: white; }    /* 灰色 */
.status-badge.OFF { background-color: #333; color: #999; border: 1px solid #999; }
</style>