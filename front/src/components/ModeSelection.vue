<template>
  <div class="step-card">
    <h3>第一步：请选择系统工作模式</h3>
    <p class="hint">注意：切换模式将重置所有房间状态至初始温度。</p>

    <div class="mode-btns">
      <div class="mode-box cool" @click="setMode('COOL')">
        <span class="icon">❄️</span>
        <span>制冷模式</span>
        <div class="desc">18℃ - 28℃</div>
      </div>

      <div class="mode-box heat" @click="setMode('HEAT')">
        <span class="icon">☀️</span>
        <span>制热模式</span>
        <div class="desc">25℃ - 30℃</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import request from '../utils/request';

const emit = defineEmits(['next']);

const setMode = async (mode) => {
  if(!confirm(`确认将系统重置为【${mode === 'COOL' ? '制冷' : '制热'}】模式吗？`)) return;

  try {
    await request.post('/ac/setMode', { mode });
    alert('模式设置成功，系统已重置！');
    emit('next');
  } catch (err) {
    alert('设置失败，请检查后端服务。');
  }
};
</script>

<style scoped>
.step-card { text-align: center; padding: 40px; }
.mode-btns { display: flex; justify-content: center; gap: 40px; margin-top: 30px; }
.mode-box {
  width: 200px; height: 200px;
  border: 2px solid #ddd;
  border-radius: 12px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: white;
}
.mode-box:hover { transform: translateY(-5px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
.mode-box .icon { font-size: 4em; margin-bottom: 10px; }
.cool:hover { border-color: #409eff; color: #409eff; }
.heat:hover { border-color: #f56c6c; color: #f56c6c; }
.desc { margin-top: 10px; color: #666; font-size: 0.9em; }
</style>