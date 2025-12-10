<template>
  <div class="app-layout">
    <!-- 左侧侧边栏 -->
    <aside class="sidebar">
      <div class="logo-area">
        <h2>酒店空调</h2>
        <p>管理系统</p>
      </div>
      <nav class="nav-links">
        <div
          class="nav-item"
          :class="{ active: currentTab === 'checkin' }"
          @click="currentTab = 'checkin'"
        >
          <span class="icon">🏨</span> 入住管理
        </div>
        <div
          class="nav-item"
          :class="{ active: currentTab === 'control' }"
          @click="currentTab = 'control'"
        >
          <span class="icon">🎮</span> 温控界面
        </div>
        <div
          class="nav-item"
          :class="{ active: currentTab === 'monitor' }"
          @click="currentTab = 'monitor'"
        >
          <span class="icon">📊</span> 实时监控
        </div>
        <div
          class="nav-item"
          :class="{ active: currentTab === 'checkout' }"
          @click="currentTab = 'checkout'"
        >
          <span class="icon">💳</span> 结账离店
        </div>
      </nav>
    </aside>

    <!-- 右侧主内容区 -->
    <main class="main-content-area">
      <!-- 核心修改：加入 CheckIn 到缓存列表 -->
      <KeepAlive include="MonitorScreen,ControlPanel,CheckIn">
        <component
          :is="currentView"
          :script-events="scriptData"
          :start-trigger="startTrigger"
          :reset-trigger="resetTrigger"
          @start-test="handleStartTest"
          @reset-system="handleSystemReset"
        />
      </KeepAlive>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import CheckIn from './components/CheckIn.vue';
import ControlPanel from './components/ControlPanel.vue';
import MonitorScreen from './components/MonitorScreen.vue';
import CheckOut from './components/CheckOut.vue';

const currentTab = ref('checkin');
const scriptData = ref([]);
const startTrigger = ref(0);
const resetTrigger = ref(0);

const currentView = computed(() => {
  switch(currentTab.value) {
    case 'checkin': return CheckIn;
    case 'control': return ControlPanel;
    case 'monitor': return MonitorScreen;
    case 'checkout': return CheckOut;
    default: return CheckIn;
  }
});

const handleStartTest = (events) => {
  scriptData.value = events;
  startTrigger.value++;
  currentTab.value = 'monitor';
};

const handleSystemReset = () => {
  resetTrigger.value++;
  scriptData.value = [];
};
</script>

<style scoped>
.app-layout { display: flex; width: 100vw; height: 100vh; background: #f5f7fa; color: #333; }

.sidebar { width: 220px; background: #2c3e50; color: white; display: flex; flex-direction: column; flex-shrink: 0; }
.logo-area { padding: 30px 20px; border-bottom: 1px solid #34495e; text-align: center; }
.logo-area h2 { margin: 0; font-size: 1.5em; color: #409eff; }
.logo-area p { margin: 5px 0 0; font-size: 0.8em; color: #909399; }

.nav-links { padding: 20px 0; display: flex; flex-direction: column; gap: 5px; }
.nav-item { padding: 15px 25px; cursor: pointer; transition: 0.3s; display: flex; align-items: center; gap: 10px; font-size: 15px; }
.nav-item:hover { background: #34495e; }
.nav-item.active { background: #409eff; color: white; font-weight: bold; border-right: 4px solid #fff; }
.icon { font-size: 1.2em; }

.main-content-area { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; }
.main-content-area > * { flex: 1; }
</style>