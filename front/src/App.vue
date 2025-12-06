<template>
  <div class="app-container">
    <h2>酒店空调管理系统</h2>
    <!-- 空调面板（101-105房间） -->
    <div style="display: flex; flex-wrap: wrap;">
      <AcPanel roomId="101" />
      <AcPanel roomId="102" />
      <AcPanel roomId="103" />
      <AcPanel roomId="104" />
      <AcPanel roomId="105" />
    </div>

    <!-- 前台界面 -->
    <FrontDesk />

    <!-- 监控大屏 -->
    <MonitorScreen />
  </div>
</template>

<script setup>
import AcPanel from './components/AcPanel.vue';
import FrontDesk from './components/FrontDesk.vue';
import MonitorScreen from './components/MonitorScreen.vue';
</script>

<style>
.app-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
</style>