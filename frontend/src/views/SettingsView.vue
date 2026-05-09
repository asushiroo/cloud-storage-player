<script setup lang="ts">
import axios from "axios";
import { onMounted, ref } from "vue";
import * as settingsApi from "../api/settings";
import AppShell from "../components/AppShell.vue";

const baiduRootPath = ref("");
const cacheLimitBytes = ref(0);
const loading = ref(false);
const saving = ref(false);
const message = ref("");
const error = ref("");

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const settings = await settingsApi.fetchSettings();
    baiduRootPath.value = settings.baidu_root_path;
    cacheLimitBytes.value = settings.cache_limit_bytes;
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "读取设置失败。";
    } else {
      error.value = "读取设置失败。";
    }
  } finally {
    loading.value = false;
  }
}

async function submit(): Promise<void> {
  saving.value = true;
  error.value = "";
  message.value = "";
  try {
    const updated = await settingsApi.updateSettings({
      baidu_root_path: baiduRootPath.value,
      cache_limit_bytes: cacheLimitBytes.value,
    });
    baiduRootPath.value = updated.baidu_root_path;
    cacheLimitBytes.value = updated.cache_limit_bytes;
    message.value = "设置已保存。";
  } catch (exc) {
    if (axios.isAxiosError(exc)) {
      error.value = exc.response?.data?.detail ?? "保存设置失败。";
    } else {
      error.value = "保存设置失败。";
    }
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <AppShell>
    <section class="panel stack">
      <h2>设置</h2>
      <p class="muted">当前只暴露非敏感配置，敏感 Baidu 凭据仍由后端环境变量管理。</p>

      <p v-if="loading" class="muted">加载中...</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="message">{{ message }}</p>

      <div class="field">
        <label for="baidu-root-path">Baidu Root Path</label>
        <input id="baidu-root-path" v-model="baiduRootPath" />
      </div>

      <div class="field">
        <label for="cache-limit-bytes">Cache Limit Bytes</label>
        <input id="cache-limit-bytes" v-model.number="cacheLimitBytes" type="number" min="1" />
      </div>

      <div class="button-row">
        <button class="button" type="button" :disabled="saving" @click="submit">
          {{ saving ? "保存中..." : "保存设置" }}
        </button>
      </div>
    </section>
  </AppShell>
</template>
