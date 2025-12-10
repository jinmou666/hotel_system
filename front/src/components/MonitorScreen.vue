<template>
  <div class="monitor-screen">
    <div class="top-control-bar">
      <div class="left-info">
        <h3>实时监控大屏</h3>
        <div class="status-box">
           系统时间: <span class="time">{{ systemTime }} min</span>
           <span v-if="isRunning" class="tag running">测试运行中</span>
           <span v-else-if="isFinished" class="tag finished">测试结束</span>
           <span v-else class="tag paused">等待指令</span>
        </div>
      </div>

      <!-- 已移除中间的状态提示文字 -->
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

      <!-- 已移除 log-panel DOM 结构，彻底隐藏日志 -->
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import request from '../utils/request';

defineOptions({ name: 'MonitorScreen' });

const props = defineProps({
  scriptEvents: { type: Array, default: () => [] },
  startTrigger: { type: Number, default: 0 },
  resetTrigger: { type: Number, default: 0 }
});

const roomList = ref([]);
// 日志数据虽然不再显示，但在逻辑中保留以防后续需要恢复或用于调试
const logs = ref([]);
const systemTime = ref(0);
const isRunning = ref(false);
const isFinished = ref(false);

let monitorTimer = null;
let testTimeoutId = null;
let startTime = 0;

const TICK_INTERVAL = 10000;

// --- 监听重置信号 ---
watch(() => props.resetTrigger, (newVal) => {
  if (newVal > 0) {
    isRunning.value = false;
    isFinished.value = false;
    if (testTimeoutId) clearTimeout(testTimeoutId);
    systemTime.value = 0;
    fetchStatus();
  }
});

// --- 监听启动信号 ---
watch(() => props.startTrigger, (newVal) => {
  if (newVal > 0 && props.scriptEvents.length > 0) {
    startTest();
  }
});

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
  try {
    await request.post('/ac/startSimulation');
  } catch(e) {
    alert("启动失败");
    return;
  }

  isRunning.value = true;
  isFinished.value = false;
  startTime = Date.now();

  systemTime.value = 0;
  await executeEventsForTime(0);

  scheduleNextTick(1);
};

const scheduleNextTick = (targetSysTime) => {
    if (!isRunning.value) return;

    const targetPhysicalTime = startTime + (targetSysTime * TICK_INTERVAL);
    const now = Date.now();
    const delay = Math.max(0, targetPhysicalTime - now);

    testTimeoutId = setTimeout(async () => {
        if (!isRunning.value) return;

        systemTime.value = targetSysTime;
        await executeEventsForTime(systemTime.value);

        const maxTime = Math.max(...props.scriptEvents.map(e => e.time));

        if (systemTime.value >= maxTime) {
             setTimeout(async () => {
                 await fetchStatus();
                 if (isAllRoomsOff()) {
                    finishTest();
                 } else {
                    if (systemTime.value > maxTime + 2) {
                        finishTest();
                    } else {
                        scheduleNextTick(targetSysTime + 1);
                    }
                 }
             }, 3000);
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
    await fetchStatus();
  } catch (e) {}
};

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const executeEventsForTime = async (time) => {
  const currentEvents = props.scriptEvents.filter(e => e.time === time);
  if (currentEvents.length > 0) {
    const roomEventsMap = {};
    currentEvents.forEach(e => {
        if (!roomEventsMap[e.room]) roomEventsMap[e.room] = [];
        roomEventsMap[e.room].push(e);
    });

    const roomIds = Object.keys(roomEventsMap);
    for (const roomId of roomIds) {
        const events = roomEventsMap[roomId];
        for (const e of events) {
            try {
                await sleep(300);
                if (e.action === 'ON') {
                     await request.post(`/ac/togglePower/${e.room}`, { power_status: 'ON', target_temp: e.temp, fan_speed: e.fan });
                } else if (e.action === 'OFF') {
                     await request.post(`/ac/togglePower/${e.room}`, { power_status: 'OFF' });
                } else if (e.action === 'TEMP') {
                     await request.post(`/ac/setTemp/${e.room}`, { target_temp: e.temp });
                } else if (e.action === 'FAN') {
                     await request.post(`/ac/setFanSpeed/${e.room}`, { fan_speed: e.fan });
                }
            } catch (err) {}
        }
    }
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
.data-table { width: 100%; border-collapse: collapse; background: white; table-layout: fixed; font-size: 13px; }
th, td { border: 1px solid #ebeef5; padding: 10px 4px; text-align: center; }
th { background: #fafafa; color: #909399; }
.status-badge { display: inline-block; width: 50px; text-align: center; padding: 2px 0; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
.status-badge.RUNNING { background-color: #67c23a; color: white; }
.status-badge.WAITING { background-color: #e6a23c; color: white; }
.status-badge.READY { background-color: #409eff; color: white; }
.status-badge.IDLE { background-color: #909399; color: white; }
.status-badge.OFF { background-color: #f4f4f5; color: #909399; border: 1px solid #dcdfe6; }

.monitor-screen { display: flex; flex-direction: column; height: 100%; gap: 15px; }
.top-control-bar { display: flex; justify-content: space-between; align-items: center; background: white; padding: 15px 20px; border-radius: 8px; border: 1px solid #eee; }
.status-box .time { font-weight: bold; color: #409eff; font-size: 1.4em; }
.tag { padding: 4px 10px; border-radius: 4px; color: white; font-size: 0.8em; margin-left: 10px; }
.tag.HIGH { background: #f56c6c; }
.tag.MID, .tag.MEDIUM { background: #e6a23c; }
.tag.LOW { background: #67c23a; }
.tag.running { background: #67c23a; }
.tag.paused { background: #e6a23c; }
.tag.finished { background: #909399; }

.main-content { display: flex; gap: 20px; flex: 1; min-height: 0; }
.monitor-panel { flex: 1; overflow-y: auto; background: white; border-radius: 8px; border: 1px solid #eee; }
.active-row { background-color: #f0f9eb; }
.temp { color: #f56c6c; font-weight: bold; }
.total { color: #67c23a; font-weight: bold; }
</style>