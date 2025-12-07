<template>
  <div class="checkout-container">
    <div class="top-bar">
      <h3>第五步：结账离店 & 报表导出</h3>
      <button class="back-btn" @click="$emit('prev')">← 返回监控</button>
    </div>

    <div class="room-list">
      <div v-for="id in rooms" :key="id" class="checkout-card">
        <h4>房间 {{ id }}</h4>
        <div class="btn-group">
          <button @click="checkOut(id)" class="checkout-btn">办理退房</button>
          <div class="divider"></div>
          <p class="label">数据导出:</p>
          <button @click="download(id, 'bill')" class="export-btn">📄 账单(含费用)</button>
          <button @click="download(id, 'detail')" class="export-btn">📊 空调详单</button>
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
    alert(`退房成功！\n总费用：¥${res.data.total_amount}\n(含住宿费 + 空调费)`);
  } catch (err) {
    alert('退房失败，请检查是否已入住或网络连接');
  }
};

const download = (roomId, type) => {
  const endpoint = type === 'bill' ? 'exportBill' : 'exportDetail';
  // 直接在新窗口打开下载链接
  window.open(`${baseURL}/${endpoint}/${roomId}`);
};
</script>

<style scoped>
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
.room-list { display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; }
.checkout-card {
  border: 1px solid #e4e7ed; padding: 20px; border-radius: 8px;
  background: white; width: 200px; box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
  display: flex; flex-direction: column; align-items: center;
}
.checkout-card h4 { margin-top: 0; color: #303133; }
.btn-group { display: flex; flex-direction: column; gap: 10px; width: 100%; }
.checkout-btn { background: #f56c6c; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; width: 100%; transition: 0.3s; }
.checkout-btn:hover { background: #f78989; }

.divider { height: 1px; background: #eee; margin: 5px 0; }
.label { font-size: 12px; color: #909399; margin: 0; text-align: left; }

.export-btn { background: #e6a23c; color: white; padding: 8px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; text-align: left; padding-left: 15px; }
.export-btn:hover { background: #ebb563; }

.back-btn { background: #909399; color: white; border: none; padding: 8px 15px; cursor: pointer; border-radius: 4px; }
</style>