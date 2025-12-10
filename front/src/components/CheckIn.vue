<template>
  <div class="check-in-container">
    <div class="page-header">
      <h3>入住管理</h3>
      <p class="subtitle">前台接待系统</p>
    </div>

    <div class="room-grid">
      <div v-for="room in rooms" :key="room" class="room-card" :class="{ 'is-frozen': checkedIn[room] }">
        <div class="card-header">
          <h4>房间 {{ room }}</h4>
          <span v-if="checkedIn[room]" class="badge-done">已入住</span>
        </div>

        <div class="input-group">
           <label>客户ID:</label>
           <input
             v-model="formData[room].customer_id"
             placeholder="客户ID"
             :disabled="checkedIn[room]"
           />
        </div>
        <div class="input-group">
           <label>身份证:</label>
           <input
             v-model="formData[room].id_number"
             placeholder="身份证号"
             :disabled="checkedIn[room]"
           />
        </div>
        <button
          @click="checkIn(room)"
          :disabled="checkedIn[room]"
          :class="{ done: checkedIn[room] }"
        >
          {{ checkedIn[room] ? '登记完成' : '办理入住' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue';
import request from '../utils/request';

defineOptions({ name: 'CheckIn' });

const rooms = ['101', '102', '103', '104', '105'];
const checkedIn = reactive({});
const formData = reactive({});

rooms.forEach(r => {
  formData[r] = { customer_id: `CUST_${r}`, id_number: '11010119900101000' + r.slice(-1) };
  checkedIn[r] = false;
});

const checkIn = async (roomId) => {
  try {
    await request.post('/front/checkIn', {
      room_id: roomId,
      customer_id: formData[roomId].customer_id,
      id_number: formData[roomId].id_number
    });
    checkedIn[roomId] = true;
  } catch (err) {
    alert('入住失败，请检查后端');
  }
};
</script>

<style scoped>
.check-in-container { padding: 20px; }
.page-header { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
.page-header h3 { margin: 0; color: #303133; }
.subtitle { margin: 5px 0 0; font-size: 13px; color: #909399; }

.room-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 20px; }
.room-card {
  border: 1px solid #ddd; padding: 20px; border-radius: 8px;
  background: white; text-align: left; transition: 0.3s;
}
.room-card.is-frozen { background: #f5f7fa; border-color: #ebeef5; }

.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
.card-header h4 { margin: 0; color: #303133; }
.badge-done { font-size: 12px; background: #f0f9eb; color: #67c23a; padding: 2px 6px; border-radius: 4px; border: 1px solid #e1f3d8; }

.input-group { margin-bottom: 12px; }
.input-group label { display: block; font-size: 12px; color: #606266; margin-bottom: 4px; }
input { width: 100%; padding: 8px; border: 1px solid #dcdfe6; border-radius: 4px; box-sizing: border-box; transition: 0.2s; }
input:focus { border-color: #409eff; outline: none; }
input:disabled { background: #f5f7fa; color: #c0c4cc; cursor: not-allowed; }

button { width: 100%; margin-top: 10px; background: #409eff; color: white; border: none; padding: 10px; border-radius: 4px; cursor: pointer; font-weight: 500; transition: 0.3s; }
button:hover:not(:disabled) { background: #66b1ff; }
button.done { background: #909399; cursor: not-allowed; opacity: 0.7; }
button:disabled { cursor: not-allowed; }
</style>