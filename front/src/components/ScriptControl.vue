<template>
  <div class="script-control">
    <h3>第三步：导入测试用例脚本</h3>

    <div class="layout">
      <!-- 左侧：输入区域 -->
      <div class="input-area">
        <div class="format-guide">
          <h4>📂 标准格式说明 (CSV)</h4>
          <p>请上传 UTF-8 编码的文本文件，每行一条指令。支持同一时间点多条指令。</p>
          <div class="code-block">
            时间(分),房间号,动作,目标温度,风速
            0,101,ON,22,HIGH
            0,102,ON,24,MID   <-- 支持同一分钟并发
            1,101,TEMP,20,HIGH
            2,103,OFF,0,0
          </div>
          <p class="tip">动作代码: ON(开机), OFF(关机), TEMP(调温), FAN(调风)</p>
        </div>

        <div class="upload-box">
          <input type="file" ref="fileInput" @change="handleFileUpload" accept=".csv,.txt" />
          <p>或直接粘贴内容：</p>
          <textarea v-model="rawContent" placeholder="在此粘贴测试用例内容..."></textarea>
        </div>
      </div>

      <!-- 右侧：预览区域 -->
      <div class="preview-area">
        <div class="header-row">
          <h4>📜 解析预览 (共 {{ parsedEvents.length }} 条指令)</h4>
          <button class="confirm-btn" @click="confirmAndNext" :disabled="parsedEvents.length === 0">
            确认并加载脚本 →
          </button>
        </div>

        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>时间 (min)</th>
                <th>房间</th>
                <th>动作</th>
                <th>参数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(ev, index) in parsedEvents" :key="index">
                <td>{{ ev.time }}</td>
                <td>{{ ev.room }}</td>
                <td>
                  <span :class="['badge', ev.action]">{{ ev.action }}</span>
                </td>
                <td>
                  <span v-if="ev.action !== 'OFF'">{{ ev.temp }}℃ / {{ ev.fan }}</span>
                  <span v-else>-</span>
                </td>
              </tr>
              <tr v-if="parsedEvents.length === 0">
                <td colspan="4" style="text-align:center; color:#999;">暂无有效数据</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const emit = defineEmits(['next']);
const rawContent = ref('');
const parsedEvents = ref([]);
const fileInput = ref(null);

// 默认示例 (方便调试)
rawContent.value = `0,101,ON,22,HIGH
0,102,ON,25,MID
1,103,ON,24,LOW
1,101,TEMP,20,HIGH
3,102,FAN,25,HIGH
5,101,OFF,0,0`;

// 监听内容变化，实时解析
watch(rawContent, (newVal) => {
  parseContent(newVal);
});

// 处理文件上传
const handleFileUpload = (event) => {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    rawContent.value = e.target.result;
  };
  reader.readAsText(file);
};

// 核心解析逻辑
const parseContent = (text) => {
  const lines = text.split('\n');
  const events = [];

  lines.forEach(line => {
    line = line.trim();
    // 跳过空行或表头(如果包含中文/字母表头)
    if (!line || line.startsWith('时间') || line.startsWith('Time')) return;

    const parts = line.split(/,|，/); // 支持中英文逗号
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

  // 按时间排序，确保执行顺序
  parsedEvents.value = events.sort((a, b) => a.time - b.time);
};

// 提交数据给 App.vue
const confirmAndNext = () => {
  emit('next', parsedEvents.value);
};

// 初始化解析一次
parseContent(rawContent.value);
</script>

<style scoped>
.layout { display: flex; gap: 20px; height: 500px; }
.input-area { flex: 1; display: flex; flex-direction: column; gap: 15px; }
.preview-area { flex: 1; display: flex; flex-direction: column; border-left: 1px solid #eee; padding-left: 20px; }

.format-guide { background: #f0f9eb; padding: 15px; border-radius: 6px; font-size: 0.9em; }
.code-block { background: #fff; padding: 10px; border: 1px solid #dcdfe6; font-family: monospace; white-space: pre; margin: 5px 0; color: #666; }

.upload-box { flex: 1; display: flex; flex-direction: column; }
textarea { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; resize: none; }

.header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.confirm-btn { background: #409eff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; }
.confirm-btn:disabled { background: #a0cfff; cursor: not-allowed; }

.table-wrapper { flex: 1; overflow-y: auto; border: 1px solid #ebeef5; border-radius: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 0.9em; }
th { background: #fafafa; position: sticky; top: 0; }
th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ebeef5; }

.badge { padding: 2px 6px; border-radius: 4px; font-size: 0.8em; color: white; }
.badge.ON { background: #67c23a; }
.badge.OFF { background: #909399; }
.badge.TEMP { background: #e6a23c; }
.badge.FAN { background: #409eff; }
</style>