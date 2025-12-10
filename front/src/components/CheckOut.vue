<template>
  <div class="checkout-container">
    <div class="page-header">
      <h3>结账离店</h3>
      <p class="subtitle">账单结算与报表导出</p>
    </div>

    <div class="room-list">
      <div v-for="id in rooms" :key="id" class="checkout-card">
        <h4>房间 {{ id }}</h4>
        <div class="btn-group">
          <button @click="checkOut(id)" class="checkout-btn">办理退房</button>
          <div class="divider"></div>
          <p class="label">数据导出 (Excel):</p>
          <button @click="download(id, 'bill')" class="export-btn">📄 账单</button>
          <button @click="download(id, 'detail')" class="export-btn">📊 详单</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import request from '../utils/request';

const rooms = ['101', '102', '103', '104', '105'];
const baseURL = 'http://127.0.0.1:5000/api/front';

const checkOut = async (roomId) => {
  try {
    const res = await request.post('/front/checkOut', { room_id: roomId });
    alert(`退房成功！\n总费用：¥${res.data.total_amount}\n(含住宿费 ¥${res.data.accommodation_fee})`);
  } catch (err) {
    alert('退房失败');
  }
};

const download = (roomId, type) => {
  const endpoint = type === 'bill' ? 'exportBill' : 'exportDetail';
  window.open(`${baseURL}/${endpoint}/${roomId}`);
};
</script>

<style scoped>
.checkout-container { padding: 20px; }
.page-header { margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
.page-header h3 { margin: 0; color: #303133; }
.subtitle { margin: 5px 0 0; font-size: 13px; color: #909399; }

.room-list { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; }
.checkout-card {
  border: 1px solid #e4e7ed; padding: 20px; border-radius: 8px;
  background: white; width: 220px; box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
  display: flex; flex-direction: column; align-items: center;
}
.checkout-card h4 { margin-top: 0; color: #303133; }
.btn-group { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.checkout-btn { background: #f56c6c; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; width: 100%; transition: 0.3s; }
.checkout-btn:hover { background: #f78989; }

.divider { height: 1px; background: #eee; margin: 5px 0; }
.label { font-size: 12px; color: #909399; margin: 0; text-align: left; }

.export-btn { background: #67c23a; color: white; padding: 8px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; text-align: center; }
.export-btn:hover { background: #85ce61; }
</style>