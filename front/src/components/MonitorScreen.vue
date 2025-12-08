<template>
  <div class="monitor-screen">
    <div class="top-control-bar">
      <div class="left-info">
        <h3>第四步：实时监控 & 测试执行</h3>
        <div class="status-box">
           系统时间: <span class="time">{{ systemTime }} min</span>
           <span v-if="isRunning" class="tag running">运行中</span>
           <span v-else-if="isFinished" class="tag finished">已结束</span>
           <span v-else class="tag paused">等待启动</span>
        </div>
      </div>

      <div class="center-actions">
        <button v-if="!isRunning && !isFinished" class="start-btn" @click="startTest">
          ▶ 开始执行测试用例
        </button>
        <button v-else-if="isRunning" class="stop-btn" @click="stopTest">
          ⏸ 暂停/停止
        </button>
        <span v-else class="finished-text">✅ 测试已结束 (温度已锁定)</span>
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
              <th width="80">房间</th>
              <th width="100">室温</th>
              <th width="80">目标</th>
              <th width="80">风速</th>
              <th width="120">运行状态</th>
              <th width="100">费率</th>
              <th width="100">当前费</th>
              <th width="100">总费</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="room in roomList" :key="room.room_id" :class="{ 'active-row': room.power_status === 'ON' }">
              <td class="room-id">{{ room.room_id }}</td>
              <td class="temp">{{ formatNum(room.current_temp) }}°C</td>
              <td>{{ formatNum(room.target_temp) }}°C</td>
              <td><span class="tag" :class="room.fan_speed">{{ room.fan_speed }}</span></td>
              <td>
                <span class="status-badge" :class="room.sched_status">
                  {{ formatStatus(room.sched_status) }}
                </span>
              </td>
              <td>{{ formatNum(room.fee_rate) }}</td>
              <td>{{ formatNum(room.current_fee) }}</td>
              <td class="total">{{ formatNum(room.total_fee) }}</td>
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

// 数值格式化 helper: 强制保留2位小数
const formatNum = (val) => {
  if (val === undefined || val === null) return '0.00';
  return Number(val).toFixed(2);
};

const formatStatus = (status) => {
  const map = {
    'RUNNING': '送风中',
    'WAITING': '等待调度',
    'READY': '准备就绪',
    'IDLE': '待机/回温',
    'OFF': '关机'
  };
  return map[status] || status;
};

const isAllRoomsOff = () => {
  return roomList.value.every(r => r.power_status === 'OFF');
};

const fetchStatus = async () => {
  const ids = ['101', '102', '103', '104', '105'];
  try {
      const list = [];
      for (const id of ids) {
          const res = await request.get(`/ac/roomState/${id}`);
          list.push(res);
      }
      roomList.value = list;
  } catch (e) { }
};

const startTest = async () => {
  if (props.scriptEvents.length === 0) {
    alert("未检测到脚本数据！");
    return;
  }

  try {
    await request.post('/ac/startSimulation');
    logs.value.push(">>> 物理引擎已启动！");
  } catch(e) {
    alert("启动失败，请检查网络");
    return;
  }

  isRunning.value = true;
  logs.value.push(`>>> 测试启动`);

  await executeEventsForTime(systemTime.value);

  scriptTimer = setInterval(async () => {
    systemTime.value++;
    await executeEventsForTime(systemTime.value);

    const maxTime = Math.max(...props.scriptEvents.map(e => e.time));
    if (systemTime.value > maxTime) {
        if (isAllRoomsOff()) {
            logs.value.push(">>> 指令结束且全员关机，提前结束测试。");
            await finishTest();
        } else {
            if (systemTime.value > maxTime + 1) {
                logs.value.push(">>> 超时强制结束。");
                await finishTest();
            } else {
                logs.value.push(`>>> 等待关机中... (T=${systemTime.value})`);
            }
        }
    }
  }, TICK_INTERVAL);
};

const stopTest = () => {
  isRunning.value = false;
  if (scriptTimer) clearInterval(scriptTimer);
  logs.value.push(">>> 测试被手动暂停");
};

const finishTest = async () => {
  isRunning.value = false;
  isFinished.value = true;
  if (scriptTimer) clearInterval(scriptTimer);
  try {
    await request.post('/ac/stopSimulation');
    logs.value.push(">>> ✅ 物理引擎已暂停，温度锁定。");
  } catch (e) { }
};

const executeEventsForTime = async (time) => {
  const currentEvents = props.scriptEvents.filter(e => e.time === time);
  if (currentEvents.length > 0) {
    logs.value.push(`--- 第 ${time} 分钟 ---`);
    for (const e of currentEvents) {
        try {
            logs.value.push(`[执行] R${e.room} -> ${e.action}`);
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
            logs.value.push(`[超时] R${e.room} 跳过`);
        }
    }
    nextTick(() => { if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight; });
  }
};

onMounted(() => {
  fetchStatus();
  monitorTimer = setInterval(fetchStatus, 1500);
});

onUnmounted(() => {
  clearInterval(monitorTimer);
  clearInterval(scriptTimer);
});
</script>

<style scoped>
/* 固定表格布局，彻底解决跳动问题 */
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  table-layout: fixed; /* 核心 CSS */
}

th, td {
  border: 1px solid #eee;
  padding: 10px;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.monitor-screen { display: flex; flex-direction: column; height: 100%; }
.top-control-bar { display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
.status-box .time { font-weight: bold; color: #409eff; font-size: 1.4em; }
.tag { padding: 2px 8px; border-radius: 4px; color: white; font-size: 0.8em; margin-left: 5px; }
.tag.running { background: #67c23a; }
.tag.paused { background: #e6a23c; }
.tag.finished { background: #909399; }
.start-btn { background: #67c23a; color: white; padding: 10px 25px; border: none; border-radius: 4px; cursor: pointer; }
.stop-btn { background: #e6a23c; color: white; padding: 10px 25px; border: none; border-radius: 4px; cursor: pointer; }
.next-btn { background: #409eff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
.main-content { display: flex; gap: 20px; height: 500px; }
.monitor-panel { flex: 3; overflow-y: auto; }
.log-panel { flex: 1; background: #2b2b2b; color: #ccc; display: flex; flex-direction: column; border-radius: 8px; }
.log-header { background: #1a1a1a; padding: 10px; font-weight: bold; }
.log-content { flex: 1; overflow-y: auto; padding: 10px; font-family: monospace; }
.active-row { background-color: #f0f9eb; }
.temp { color: #f56c6c; font-weight: bold; }
.total { color: #67c23a; }
.tag.HIGH { background: #f56c6c; }
.tag.MID, .tag.MEDIUM { background: #e6a23c; }
.tag.LOW { background: #67c23a; }
.status-badge { padding: 4px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold; }
.status-badge.RUNNING { background-color: #67c23a; color: white; }
.status-badge.WAITING { background-color: #e6a23c; color: white; }
.status-badge.READY { background-color: #409eff; color: white; }
.status-badge.IDLE { background-color: #909399; color: white; }
.status-badge.OFF { background-color: #333; color: #999; border: 1px solid #999; }
.finished-text { color: #67c23a; font-weight: bold; margin-left: 10px; font-size: 1.1em; }
</style>