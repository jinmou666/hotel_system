<template>
  <div class="control-panel">
    <div class="panel-header">
      <div>
        <h3 style="margin:0;">温控配置中心</h3>
        <p class="subtitle">模式设定与手动控制</p>
      </div>
      <button class="reset-all-btn" @click="handleReset" v-if="modeSet">
        🔄 一键重置系统
      </button>
    </div>

    <!-- 区域 1: 模式设定 -->
    <div class="section-card mode-section">
      <div class="section-title">工作模式设定</div>
      <div class="mode-buttons">
        <button
          class="mode-btn cool"
          :class="{ active: currentMode === 'COOL' }"
          @click="setMode('COOL')"
        >
          ❄️ 制冷模式
        </button>
        <!-- FIX: 这里必须传 'HEAT'，不能是 'HEATING' -->
        <button
          class="mode-btn heat"
          :class="{ active: currentMode === 'HEAT' }"
          @click="setMode('HEAT')"
        >
          ☀️ 制热模式
        </button>
      </div>
      <p class="status-hint" v-if="!modeSet">⚠️ 请先选择工作模式以激活控制面板</p>
    </div>

    <!-- 区域 2: 房间独立控制面板 -->
    <div class="section-card rooms-section" :class="{ disabled: !modeSet }">
      <div class="section-title">房间控制面板</div>
      <div class="rooms-grid">
        <div v-for="room in rooms" :key="room" class="room-control-card">
          <div class="room-header">
            <span class="room-title">Room {{ room }}</span>
            <button
              class="power-btn"
              :class="{ on: roomStates[room].isOn }"
              @click="togglePower(room)"
            >
              <span class="power-icon">⏻</span>
            </button>
          </div>

          <div class="control-row temp-row">
            <label>目标温度</label>
            <div class="stepper">
              <button @click="adjustTemp(room, -1)">-</button>
              <span class="temp-display">{{ roomStates[room].targetTemp }}°C</span>
              <button @click="adjustTemp(room, 1)">+</button>
            </div>
          </div>

          <div class="control-row fan-row">
            <label>风速</label>
            <div class="fan-options">
              <span
                v-for="speed in ['LOW', 'MID', 'HIGH']"
                :key="speed"
                class="fan-opt"
                :class="{ active: roomStates[room].fanSpeed === speed }"
                @click="setFan(room, speed)"
              >
                {{ speed[0] }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 区域 3: 脚本录入 -->
    <div class="section-card script-section" :class="{ disabled: !modeSet }">
      <div class="section-title">测试脚本加载</div>
      <div class="script-layout">
        <div class="input-area">
          <textarea
            v-model="rawScript"
            placeholder="在此粘贴 CSV 指令...&#10;格式: 时间,房间,动作,参数&#10;0,101,ON,22,HIGH"
          ></textarea>
          <div class="file-upload">
             <input type="file" @change="handleFileUpload" accept=".csv,.txt" />
          </div>
        </div>
        <div class="action-area">
          <div class="preview-info" v-if="parsedEvents.length > 0">
            指令数: <strong>{{ parsedEvents.length }}</strong>
            <br>
            时长: {{ parsedEvents[parsedEvents.length-1].time }} min
          </div>
          <button
            class="start-test-btn"
            @click="emitStartTest"
            :disabled="parsedEvents.length === 0"
          >
            ▶ 开始测试
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import request from '../utils/request';

defineOptions({ name: 'ControlPanel' });

const emit = defineEmits(['start-test', 'reset-system']);

const rooms = ['101', '102', '103', '104', '105'];
const modeSet = ref(false);
const currentMode = ref('');
const rawScript = ref('');
const parsedEvents = ref([]);

const roomStates = reactive({});
const initRoomStates = () => {
  rooms.forEach(id => {
    // 默认值重置，不带模式倾向
    roomStates[id] = { isOn: false, targetTemp: 22, fanSpeed: 'MID' };
  });
};
initRoomStates();

const setMode = async (mode) => {
  if(modeSet.value && !confirm(`确认切换到【${mode === 'COOL' ? '制冷' : '制热'}】？当前测试将被中断。`)) return;

  try {
    await request.post('/ac/setMode', { mode });
    currentMode.value = mode;
    modeSet.value = true;

    // FIX: 制冷默认25，制热默认23
    const defaultTemp = mode === 'COOL' ? 25 : 23;

    rooms.forEach(id => {
      roomStates[id].targetTemp = defaultTemp;
      roomStates[id].isOn = false;
      roomStates[id].fanSpeed = 'MID';
    });

    emit('reset-system');

  } catch (err) {
    alert('设置失败，请检查后端');
  }
};

const handleReset = async () => {
  if(!confirm("确认重置所有系统状态？这将清除所有运行中的任务。")) return;

  try {
    await request.post('/ac/stopSimulation');

    modeSet.value = false;
    currentMode.value = '';
    rawScript.value = '';
    parsedEvents.value = [];
    initRoomStates();

    emit('reset-system');

  } catch(e) {
    alert("重置失败");
  }
};

const togglePower = async (roomId) => {
  const newState = !roomStates[roomId].isOn;
  roomStates[roomId].isOn = newState;
  try {
    await request.post(`/ac/togglePower/${roomId}`, {
      power_status: newState ? 'ON' : 'OFF',
      target_temp: roomStates[roomId].targetTemp,
      fan_speed: roomStates[roomId].fanSpeed
    });
  } catch(e) {}
};

const adjustTemp = async (roomId, delta) => {
  if (!roomStates[roomId].isOn) return;
  roomStates[roomId].targetTemp += delta;
  try {
    await request.post(`/ac/setTemp/${roomId}`, { target_temp: roomStates[roomId].targetTemp });
  } catch(e) {}
};

const setFan = async (roomId, speed) => {
  if (!roomStates[roomId].isOn) return;
  roomStates[roomId].fanSpeed = speed;
  try {
    await request.post(`/ac/setFanSpeed/${roomId}`, { fan_speed: speed });
  } catch(e) {}
};

watch(rawScript, (val) => parseContent(val));

const handleFileUpload = (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => { rawScript.value = e.target.result; };
  reader.readAsText(file);
};

const parseContent = (text) => {
  const lines = text.split('\n');
  const events = [];
  lines.forEach(line => {
    line = line.trim();
    if (!line || line.startsWith('时间') || line.startsWith('Time')) return;
    const parts = line.split(/,|，/);
    if (parts.length >= 3) {
      events.push({
        time: parseInt(parts[0].trim()),
        room: parts[1].trim(),
        action: parts[2].trim().toUpperCase(),
        temp: parts[3] ? parseFloat(parts[3].trim()) : 0,
        fan: parts[4] ? parts[4].trim().toUpperCase() : 'MID'
      });
    }
  });
  parsedEvents.value = events.sort((a, b) => a.time - b.time);
};

const emitStartTest = () => {
  if (parsedEvents.value.length === 0) return;
  emit('start-test', parsedEvents.value);
};
</script>

<style scoped>
.control-panel { padding: 20px; display: flex; flex-direction: column; gap: 20px; text-align: left; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.subtitle { margin: 5px 0 0; font-size: 13px; color: #909399; }
.reset-all-btn { background: #f56c6c; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-size: 13px; transition: 0.3s; }
.reset-all-btn:hover { background: #f78989; }

.section-card { background: white; padding: 20px; border-radius: 8px; border: 1px solid #eee; box-shadow: 0 2px 8px rgba(0,0,0,0.05); transition: 0.3s; }
.section-title { font-weight: bold; color: #303133; border-left: 4px solid #409eff; padding-left: 10px; margin-bottom: 20px; }
.section-card.disabled { opacity: 0.5; pointer-events: none; filter: grayscale(1); }

.mode-buttons { display: flex; gap: 20px; justify-content: center; }
.mode-btn { padding: 15px 40px; font-size: 1.1em; border: 2px solid #ddd; background: #fff; border-radius: 8px; cursor: pointer; transition: 0.2s; color: #666; }
.mode-btn.cool.active { border-color: #409eff; color: #409eff; background: #ecf5ff; }
.mode-btn.heat.active { border-color: #e6a23c; color: #e6a23c; background: #fdf6ec; }
.status-hint { text-align: center; color: #f56c6c; font-size: 0.9em; margin-top: 10px; }

.rooms-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 15px; }
.room-control-card { border: 1px solid #e4e7ed; border-radius: 6px; padding: 12px; background: #fcfcfc; }
.room-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.room-title { font-weight: bold; color: #606266; }
.power-btn { background: #dcdfe6; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; border: none; cursor: pointer; color: white; transition: 0.3s; }
.power-btn.on { background: #67c23a; box-shadow: 0 0 8px rgba(103, 194, 58, 0.4); }

.control-row { margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
.control-row label { font-size: 12px; color: #909399; }
.stepper { display: flex; align-items: center; border: 1px solid #dcdfe6; border-radius: 4px; overflow: hidden; }
.stepper button { border: none; background: #fff; padding: 2px 8px; cursor: pointer; }
.stepper button:hover { background: #f5f7fa; }
.temp-display { padding: 0 8px; font-size: 13px; font-weight: bold; color: #409eff; min-width: 35px; text-align: center; }

.fan-options { display: flex; gap: 2px; }
.fan-opt { font-size: 10px; padding: 2px 5px; background: #f0f2f5; cursor: pointer; color: #909399; border-radius: 2px; }
.fan-opt.active { background: #409eff; color: white; }

.script-layout { display: flex; gap: 20px; height: 180px; }
.input-area { flex: 2; display: flex; flex-direction: column; gap: 10px; }
.input-area textarea { flex: 1; padding: 10px; border: 1px solid #dcdfe6; border-radius: 4px; font-family: monospace; resize: none; font-size: 12px; }
.action-area { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #f5f7fa; border-radius: 4px; padding: 10px; }
.start-test-btn { background: #67c23a; color: white; border: none; padding: 12px 20px; border-radius: 6px; font-size: 14px; font-weight: bold; cursor: pointer; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: 0.2s; }
.start-test-btn:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 12px rgba(0,0,0,0.15); }
.start-test-btn:disabled { background: #c0c4cc; cursor: not-allowed; box-shadow: none; }
.preview-info { margin-bottom: 15px; font-size: 13px; color: #606266; text-align: center; }
</style>