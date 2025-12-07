<template>
  <div class="app-container">
    <div class="header">
      <h2>酒店空调管理系统 (验收版)</h2>
      <div class="steps">
        <span :class="{ active: currentStep === 0 }">1. 模式设定</span> &gt;
        <span :class="{ active: currentStep === 1 }">2. 办理入住</span> &gt;
        <span :class="{ active: currentStep === 2 }">3. 导入脚本</span> &gt;
        <span :class="{ active: currentStep === 3 }">4. 监控运行</span> &gt;
        <span :class="{ active: currentStep === 4 }">5. 结账离店</span>
      </div>
    </div>

    <div class="content">
      <ModeSelection v-if="currentStep === 0" @next="nextStep" />
      <CheckIn v-if="currentStep === 1" @next="nextStep" />

      <!-- Step 3: 负责产生 scriptEvents 数据 -->
      <ScriptControl
        v-if="currentStep === 2"
        @next="handleScriptLoaded"
      />

      <!-- Step 4: 接收 scriptEvents 数据并执行 -->
      <MonitorScreen
        v-if="currentStep === 3"
        :script-events="scriptData"
        @next="nextStep"
      />

      <CheckOut v-if="currentStep === 4" @prev="currentStep = 3" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import ModeSelection from './components/ModeSelection.vue';
import CheckIn from './components/CheckIn.vue';
import ScriptControl from './components/ScriptControl.vue';
import MonitorScreen from './components/MonitorScreen.vue';
import CheckOut from './components/CheckOut.vue';

const currentStep = ref(0);
const scriptData = ref([]); // 存储解析后的脚本事件

const nextStep = () => {
  if (currentStep.value < 4) {
    currentStep.value++;
  }
};

// Step 3 完成时，保存解析好的脚本数据，并跳转
const handleScriptLoaded = (events) => {
  scriptData.value = events;
  nextStep();
};
</script>

<style scoped>
.app-container {
  max-width: 1200px;
  margin: 0 auto;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}
.header {
  text-align: center;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eee;
}
.steps span {
  color: #999;
  font-weight: bold;
  margin: 0 10px;
}
.steps span.active {
  color: #409eff;
  font-size: 1.1em;
}
.content {
  padding: 20px;
  background: #f9f9f9;
  border-radius: 8px;
  min-height: 500px;
}
</style>