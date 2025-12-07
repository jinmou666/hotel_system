<template>
  <div class="check-in-container">
    <h3>第二步：办理入住</h3>
    <div class="room-grid">
      <div v-for="room in rooms" :key="room" class="room-card">
        <h4>房间 {{ room }}</h4>
        <div class="input-group">
           <label>客户ID:</label>
           <input v-model="formData[room].customer_id" placeholder="客户ID" />
        </div>
        <div class="input-group">
           <label>身份证:</label>
           <input v-model="formData[room].id_number" placeholder="身份证号" />
        </div>
        <button @click="checkIn(room)" :disabled="checkedIn[room]" :class="{ done: checkedIn[room] }">
          {{ checkedIn[room] ? '已入住' : '办理入住' }}
        </button>
      </div>
    </div>
    <div class="actions">
      <button class="next-btn" @click="$emit('next')">完成入住，进入下一步</button>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue';
import request from '../utils/request';

const rooms = ['101', '102', '103', '104', '105'];
const checkedIn = reactive({});
const formData = reactive({});

// 初始化表单
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
.room-grid { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; }
.room-card {
  border: 1px solid #ddd; padding: 15px; border-radius: 8px;
  background: white; width: 200px; text-align: left;
}
.input-group { margin-bottom: 8px; }
.input-group label { display: block; font-size: 12px; color: #666; }
input { width: 90%; padding: 5px; border: 1px solid #ccc; border-radius: 4px; }
button { width: 100%; margin-top: 5px; background: #67c23a; color: white; border: none; padding: 8px; border-radius: 4px; cursor: pointer; }
button:disabled { background: #f0f9eb; color: #67c23a; border: 1px solid #c2e7b0; cursor: default; }
.actions { text-align: center; margin-top: 30px; }
.next-btn { font-size: 1.2em; padding: 10px 30px; background: #409eff; color: white; border: none; border-radius: 6px; cursor: pointer; }
</style>