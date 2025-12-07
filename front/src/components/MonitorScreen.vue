        <template>
  <div class="monitor-screen">
    <div class="bar">
      <h3>第四步：实时监控大屏</h3>
      <div class="tips">系统每 10 秒刷新一次 (系统时间 1 分钟)</div>
      <button class="next-btn" @click="$emit('next')">进入结账环节</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>房间号</th>
          <th>当前室温</th>
          <th>目标温度</th>
          <th>风速</th>
          <th>状态</th>
          <th>费率 (元/分)</th>
          <th>当前费用</th>
          <th>累计费用</th>
          <th>调度状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="room in roomList" :key="room.room_id" :class="{ 'active-row': room.power_status === 'ON' }">
          <td class="room-id">{{ room.room_id }}</td>
          <td class="temp">{{ room.current_temp }}°C</td>
          <td>{{ room.target_temp }}°C</td>
          <td>
             <span class="tag" :class="room.fan_speed">{{ room.fan_speed }}</span>
          </td>
          <td>
            <span class="status-dot" :class="room.power_status === 'ON' ? 'on' : 'off'"></span>
            {{ room.power_status === 'ON' ? '运行中' : '关机' }}
          </td>
          <td>{{ room.fee_rate }}</td>
          <td>¥{{ room.current_fee }}</td>
          <td class="total">¥{{ room.total_fee }}</td>
          <td>{{ room.status }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import request from '../utils/request';

const roomList = ref([]);
let timer = null;

const fetchStatus = async () => {
  const ids = ['101', '102', '103', '104', '105'];
  const list = [];
  // 并行请求提高速度
  try {
      const promises = ids.map(id => request.get(`/ac/roomState/${id}`));
      const results = await Promise.all(promises);
      roomList.value = results;
  } catch (e) {
      console.error("监控刷新失败", e);
  }
};

onMounted(() => {
  fetchStatus();
  timer = setInterval(fetchStatus, 1000); // 1秒刷新一次界面，虽然系统逻辑是10秒
});

onUnmounted(() => clearInterval(timer));
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.tips { color: #666; font-size: 0.9em; }
.data-table { width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
th, td { border: 1px solid #ebeef5; padding: 15px; text-align: center; }
th { background: #fafafa; color: #606266; font-weight: 600; }
.active-row { background-color: #f0f9eb; }
.room-id { font-weight: bold; }
.temp { color: #f56c6c; font-weight: bold; }
.total { color: #67c23a; font-weight: bold; }

/* 风速标签 */
.tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; color: white; }
.tag.HIGH { background: #f56c6c; }
.tag.MEDIUM { background: #e6a23c; }
.tag.LOW { background: #67c23a; }

.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
.status-dot.on { background: #67c23a; }
.status-dot.off { background: #909399; }

.next-btn { background: #409eff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 1em; }
.next-btn:hover { background: #66b1ff; }
</style>