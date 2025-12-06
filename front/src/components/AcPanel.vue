<template>
  <div class="ac-panel">
    <h3>房间 {{ roomId }} 空调面板</h3>
    
    <!-- 开关机按钮 -->
    <button 
      class="power-btn" 
      :class="{ active: roomState.power_status === 'ON' }"
      @click="togglePower"
    >
      {{ roomState.power_status === 'ON' ? '关机' : '开机' }}
    </button>

    <!-- 温度显示与调节 -->
    <div class="temp-control">
      <p>当前温度：{{ roomState.current_temp }}°C</p>
      <p>目标温度：{{ roomState.target_temp }}°C</p>
      <button @click="adjustTemp(-1)" :disabled="roomState.power_status === 'OFF'">-</button>
      <button @click="adjustTemp(1)" :disabled="roomState.power_status === 'OFF'">+</button>
    </div>

    <!-- 风速调节 -->
    <div class="fan-control">
      <p>当前风速：{{ roomState.fan_speed }}</p>
      <button @click="setFanSpeed('LOW')" :disabled="roomState.power_status === 'OFF'">低风</button>
      <button @click="setFanSpeed('MEDIUM')" :disabled="roomState.power_status === 'OFF'">中风</button>
      <button @click="setFanSpeed('HIGH')" :disabled="roomState.power_status === 'OFF'">高风</button>
    </div>

    <!-- 费用显示 -->
    <div class="fee-info">
      <p>当前累计费用：¥{{ roomState.current_fee }}</p>
      <p>总费用：¥{{ roomState.total_fee }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import request from '../utils/request';

// 接收房间ID参数
const props = defineProps({
  roomId: {
    type: String,
    required: true, // 传入101/102/103/104/105
  },
});

// 房间状态数据
const roomState = ref({
  current_temp: 22.0,
  target_temp: 22.0,
  fan_speed: 'MEDIUM',
  power_status: 'OFF',
  current_fee: 0.0,
  total_fee: 0.0,
});

// 定时器（1秒刷新状态）
let refreshTimer = null;

// 获取房间状态
const getRoomState = async () => {
  try {
    const res = await request.get(`/ac/roomState/${props.roomId}`);
    roomState.value = res; // 后端返回的房间状态对象
  } catch (err) {
    console.error(`获取房间${props.roomId}状态失败：`, err);
  }
};

// 切换开关机
const togglePower = async () => {
  try {
    await request.post(`/ac/togglePower/${props.roomId}`, {
      power_status: roomState.value.power_status === 'ON' ? 'OFF' : 'ON',
    });
    await getRoomState(); // 刷新状态
  } catch (err) {
    console.error('切换开关机失败：', err);
  }
};

// 调节温度
const adjustTemp = async (step) => {
  const newTemp = Number(roomState.value.target_temp) + step;
  // 温度范围限制（18-28℃）
  if (newTemp < 18 || newTemp > 28) return;
  
  try {
    await request.post(`/ac/setTemp/${props.roomId}`, { target_temp: newTemp });
    await getRoomState();
  } catch (err) {
    console.error('调节温度失败：', err);
  }
};

// 设置风速
const setFanSpeed = async (speed) => {
  try {
    await request.post(`/ac/setFanSpeed/${props.roomId}`, { fan_speed: speed });
    await getRoomState();
  } catch (err) {
    console.error('设置风速失败：', err);
  }
};

// 挂载时初始化+启动定时器
onMounted(() => {
  getRoomState();
  refreshTimer = setInterval(getRoomState, 1000); // 每秒刷新
});

// 卸载时清除定时器（防止内存泄漏）
onUnmounted(() => {
  clearInterval(refreshTimer);
});
</script>

<style scoped>
.ac-panel {
  width: 300px;
  padding: 20px;
  border: 1px solid #ccc;
  border-radius: 8px;
  margin: 20px;
}
.power-btn {
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.power-btn.active {
  background: #f56c6c;
}
.temp-control, .fan-control {
  margin: 15px 0;
}
button {
  margin: 0 5px;
  padding: 4px 8px;
  cursor: pointer;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}
.fee-info {
  margin-top: 15px;
  color: #666;
}
</style>