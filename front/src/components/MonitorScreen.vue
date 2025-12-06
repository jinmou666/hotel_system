<template>
  <div class="monitor-screen">
    <h3>酒店空调监控大屏</h3>
    <table>
      <thead>
        <tr>
          <th>房间号</th>
          <th>当前温度</th>
          <th>目标温度</th>
          <th>风速</th>
          <th>开关状态</th>
          <th>当前费用</th>
          <th>房间状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="room in roomList" :key="room.room_id">
          <td>{{ room.room_id }}</td>
          <td>{{ room.current_temp }}°C</td>
          <td>{{ room.target_temp }}°C</td>
          <td>{{ room.fan_speed }}</td>
          <td :class="room.power_status === 'ON' ? 'on' : 'off'">
            {{ room.power_status === 'ON' ? '开启' : '关闭' }}
          </td>
          <td>¥{{ room.current_fee }}</td>
          <td>{{ room.status }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import request from '../utils/request';

// 5个房间列表（固定101-105）
const roomList = ref([
  { room_id: '101', current_temp: 0, target_temp: 0, fan_speed: '', power_status: '', current_fee: 0, status: '' },
  { room_id: '102', current_temp: 0, target_temp: 0, fan_speed: '', power_status: '', current_fee: 0, status: '' },
  { room_id: '103', current_temp: 0, target_temp: 0, fan_speed: '', power_status: '', current_fee: 0, status: '' },
  { room_id: '104', current_temp: 0, target_temp: 0, fan_speed: '', power_status: '', current_fee: 0, status: '' },
  { room_id: '105', current_temp: 0, target_temp: 0, fan_speed: '', power_status: '', current_fee: 0, status: '' },
]);

// 定时器
let refreshTimer = null;

// 获取所有房间状态
const getAllRoomState = async () => {
  try {
    // 循环获取每个房间的状态
    for (const room of roomList.value) {
      const res = await request.get(`/ac/roomState/${room.room_id}`);
      // 更新当前房间数据
      Object.assign(room, res);
    }
  } catch (err) {
    console.error('获取监控数据失败：', err);
  }
};

// 挂载时初始化+每秒刷新
onMounted(() => {
  getAllRoomState();
  refreshTimer = setInterval(getAllRoomState, 1000);
});

// 卸载时清除定时器
onUnmounted(() => {
  clearInterval(refreshTimer);
});
</script>

<style scoped>
.monitor-screen {
  padding: 20px;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
}
th, td {
  border: 1px solid #ccc;
  padding: 10px;
  text-align: center;
}
th {
  background: #f5f5f5;
}
.on {
  color: #67c23a;
  font-weight: bold;
}
.off {
  color: #909399;
}
</style>