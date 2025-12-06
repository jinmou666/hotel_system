<template>
  <div class="front-desk">
    <h3>前台管理</h3>
    
    <!-- 入住表单 -->
    <div class="form-card">
      <h4>客户入住</h4>
      <form @submit.prevent="checkIn">
        <div class="form-item">
          <label>客户ID：</label>
          <input v-model="checkInForm.customer_id" type="text" placeholder="请输入客户ID" required />
        </div>
        <div class="form-item">
          <label>房间号：</label>
          <input v-model="checkInForm.room_id" type="text" placeholder="如101" required />
        </div>
        <div class="form-item">
          <label>身份证号：</label>
          <input v-model="checkInForm.id_number" type="text" placeholder="请输入身份证号" required />
        </div>
        <div class="form-item">
          <label>联系电话：</label>
          <input v-model="checkInForm.phone" type="tel" placeholder="请输入手机号" />
        </div>
        <button type="submit">提交入住</button>
      </form>
    </div>

    <!-- 退房表单 -->
    <div class="form-card">
      <h4>客户退房</h4>
      <form @submit.prevent="checkOut">
        <div class="form-item">
          <label>房间号：</label>
          <input v-model="checkOutForm.room_id" type="text" placeholder="如101" required />
        </div>
        <div class="form-item">
          <label>客户ID：</label>
          <input v-model="checkOutForm.customer_id" type="text" placeholder="请输入客户ID" required />
        </div>
        <button type="submit">提交退房</button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import request from '../utils/request';

// 入住表单数据
const checkInForm = ref({
  customer_id: '',
  room_id: '',
  id_number: '',
  phone: '',
});

// 退房表单数据
const checkOutForm = ref({
  room_id: '',
  customer_id: '',
});

// 入住提交
const checkIn = async () => {
  try {
    await request.post('/front/checkIn', checkInForm.value);
    alert('入住成功！');
    // 清空表单
    checkInForm.value = { customer_id: '', room_id: '', id_number: '', phone: '' };
  } catch (err) {
    console.error('入住失败：', err);
    alert('入住失败，请检查信息！');
  }
};

// 退房提交
const checkOut = async () => {
  try {
    await request.post('/front/checkOut', checkOutForm.value);
    alert('退房成功！');
    // 清空表单
    checkOutForm.value = { room_id: '', customer_id: '' };
  } catch (err) {
    console.error('退房失败：', err);
    alert('退房失败，请检查信息！');
  }
};
</script>

<style scoped>
.front-desk {
  padding: 20px;
}
.form-card {
  margin: 20px 0;
  padding: 20px;
  border: 1px solid #eee;
  border-radius: 8px;
  width: 400px;
}
.form-item {
  margin: 10px 0;
  display: flex;
  align-items: center;
}
.form-item label {
  width: 80px;
}
.form-item input {
  flex: 1;
  padding: 6px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
button {
  padding: 8px 16px;
  background: #67c23a;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  margin-top: 10px;
}
</style>