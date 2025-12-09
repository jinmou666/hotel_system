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
        <span v-if="isRunning" class="running-text">
          ⚠️ 测试运行中...
        </span>
        <span v-if="isFinished" class="finished-text">
          ✅ 测试已结束 (温度已锁定)
        </span>
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
              <th width="60">房间</th>
              <th width="80">室温</th>
              <th width="80">目标</th>
              <th width="80">风速</th>
              <th width="100">状态</th>
              <th width="80">费率</th>
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
let testTimeoutId = null;
let startTime = 0;

// === 核心修正：改回 10000ms (10秒) ===
// 现实 10秒 = 系统 1分钟
// 这样才能匹配后端的 TIME_KX = 6.0
const TICK_INTERVAL = 10000;

const formatNum = (val) => {
  if (val === undefined || val === null) return '0.00';
  return Number(val).toFixed(2);
};

const formatStatus = (status) => {
  const map = { 'RUNNING': '送风', 'WAITING': '等待', 'READY': '就绪', 'IDLE': '待机', 'OFF': '关机' };
  return map[status] || status;
};

const isAllRoomsOff = () => {
  if (!roomList.value || roomList.value.length === 0) return false;
  return roomList.value.every(r => r.power_status === 'OFF');
};

const fetchStatus = async () => {
  const ids = ['101', '102', '103', '104', '105'];
  try {
      const promises = ids.map(id => request.get(`/ac/roomState/${id}`).catch(() => null));
      const results = await Promise.all(promises);
      const validResults = results.filter(r => r !== null);
      if (validResults.length > 0) {
          if (roomList.value.length === 0) {
              roomList.value = validResults;
          } else {
              validResults.forEach(newRoom => {
                  const idx = roomList.value.findIndex(r => r.room_id === newRoom.room_id);
                  if (idx !== -1) roomList.value[idx] = newRoom;
              });
          }
      }
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
    alert("启动失败");
    return;
  }

  isRunning.value = true;
  logs.value.push(`>>> 测试启动`);
  startTime = Date.now();

  systemTime.value = 0;
  await executeEventsForTime(0);

  // 规划下一分钟
  scheduleNextTick(1);
};

const scheduleNextTick = (targetSysTime) => {
    if (!isRunning.value) return;

    // 严谨的时间轴计算：startTime + (分钟数 * 10秒)
    const targetPhysicalTime = startTime + (targetSysTime * TICK_INTERVAL);
    const now = Date.now();
    const delay = Math.max(0, targetPhysicalTime - now);

    testTimeoutId = setTimeout(async () => {
        if (!isRunning.value) return;

        systemTime.value = targetSysTime;
        await executeEventsForTime(systemTime.value);

        const maxTime = Math.max(...props.scriptEvents.map(e => e.time));

        if (systemTime.value >= maxTime) {
             // 给予缓冲时间，等待最后状态同步
             setTimeout(async () => {
                 await fetchStatus();
                 if (isAllRoomsOff()) {
                    logs.value.push(">>> 全员关机，测试结束。");
                    finishTest();
                 } else {
                    if (systemTime.value > maxTime + 2) {
                        logs.value.push(">>> 超时强制结束。");
                        finishTest();
                    } else {
                        logs.value.push(`>>> 等待关机...`);
                        scheduleNextTick(targetSysTime + 1);
                    }
                 }
             }, 3000); // 3秒缓冲
        } else {
            scheduleNextTick(targetSysTime + 1);
        }
    }, delay);
};

const finishTest = async () => {
  isRunning.value = false;
  isFinished.value = true;
  if (testTimeoutId) clearTimeout(testTimeoutId);

  try {
    await request.post('/ac/stopSimulation');
    logs.value.push(">>> ✅ 物理引擎已暂停，温度锁定。");
    await fetchStatus();
  } catch (e) {
    logs.value.push(">>> ⚠️ 锁定失败");
  }
};

const executeEventsForTime = async (time) => {
  const currentEvents = props.scriptEvents.filter(e => e.time === time);
  if (currentEvents.length > 0) {
    logs.value.push(`--- 第 ${time} 分钟 ---`);
    const roomEventsMap = {};
    currentEvents.forEach(e => {
        if (!roomEventsMap[e.room]) roomEventsMap[e.room] = [];
        roomEventsMap[e.room].push(e);
    });

    const promises = Object.keys(roomEventsMap).map(async (roomId) => {
        const events = roomEventsMap[roomId];
        for (const e of events) {
            try {
                logs.value.push(`[执行] R${e.room} -> ${e.action} ${e.temp || ''} ${e.fan || ''}`);
                if (e.action === 'ON') {
                     await request.post(`/ac/togglePower/${e.room}`, { power_status: 'ON', target_temp: e.temp, fan_speed: e.fan });
                } else if (e.action === 'OFF') {
                     await request.post(`/ac/togglePower/${e.room}`, { power_status: 'OFF' });
                } else if (e.action === 'TEMP') {
                     await request.post(`/ac/setTemp/${e.room}`, { target_temp: e.temp });
                } else if (e.action === 'FAN') {
                     await request.post(`/ac/setFanSpeed/${e.room}`, { fan_speed: e.fan });
                }
            } catch (err) {
                logs.value.push(`[超时/失败] R${e.room}`);
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
  if (testTimeoutId) clearTimeout(testTimeoutId);
});
</script>

<style scoped>
.data-table { width: 100%; border-collapse: collapse; background: white; table-layout: fixed; }
th, td { border: 1px solid #eee; padding: 8px 4px; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 0.9em; }
.status-badge { display: inline-block; width: 60px; text-align: center; padding: 2px 0; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
.status-badge.RUNNING { background-color: #67c23a; color: white; }
.status-badge.WAITING { background-color: #e6a23c; color: white; }
.status-badge.READY { background-color: #409eff; color: white; }
.status-badge.IDLE { background-color: #909399; color: white; }
.status-badge.OFF { background-color: #f4f4f5; color: #909399; border: 1px solid #dcdfe6; }
.monitor-screen { display: flex; flex-direction: column; height: 100%; }
.top-control-bar { display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
.status-box .time { font-weight: bold; color: #409eff; font-size: 1.4em; }
.tag { padding: 2px 8px; border-radius: 4px; color: white; font-size: 0.8em; margin-left: 5px; }
.tag.HIGH { background: #f56c6c; }
.tag.MID, .tag.MEDIUM { background: #e6a23c; }
.tag.LOW { background: #67c23a; }
.tag.running { background: #67c23a; }
.tag.paused { background: #e6a23c; }
.tag.finished { background: #909399; }
.start-btn { background: #67c23a; color: white; padding: 10px 25px; border: none; border-radius: 4px; cursor: pointer; }
.next-btn { background: #409eff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
.main-content { display: flex; gap: 20px; height: 500px; }
.monitor-panel { flex: 3; overflow-y: auto; }
.log-panel { flex: 1; background: #2b2b2b; color: #ccc; display: flex; flex-direction: column; border-radius: 8px; }
.log-header { background: #1a1a1a; padding: 10px; font-weight: bold; }
.log-content { flex: 1; overflow-y: auto; padding: 10px; font-family: monospace; }
.active-row { background-color: #f0f9eb; }
.temp { color: #f56c6c; font-weight: bold; }
.total { color: #67c23a; }
.running-text { color: #e6a23c; font-weight: bold; margin-left: 10px; }
.finished-text { color: #67c23a; font-weight: bold; margin-left: 10px; font-size: 1.1em; }
</style>