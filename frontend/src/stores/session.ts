import { defineStore } from "pinia";
import { ref } from "vue";
import * as authApi from "../api/auth";

export const useSessionStore = defineStore("session", () => {
  const authenticated = ref(false);
  const loaded = ref(false);

  async function refresh(): Promise<void> {
    const session = await authApi.fetchSession();
    authenticated.value = session.authenticated;
    loaded.value = true;
  }

  async function login(password: string): Promise<void> {
    const session = await authApi.login(password);
    authenticated.value = session.authenticated;
    loaded.value = true;
  }

  async function logout(): Promise<void> {
    const session = await authApi.logout();
    authenticated.value = session.authenticated;
    loaded.value = true;
  }

  return {
    authenticated,
    loaded,
    refresh,
    login,
    logout,
  };
});
