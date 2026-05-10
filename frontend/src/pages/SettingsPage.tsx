import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { authorizeBaidu, fetchSettings, updateSettings } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError } from "../types/api";
import { formatBytes } from "../utils/format";

export function SettingsPage() {
  const session = useRequireSession();
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: session.data?.authenticated === true,
  });
  const [storageBackend, setStorageBackend] = useState("mock");
  const [baiduRootPath, setBaiduRootPath] = useState("");
  const [cacheLimitBytes, setCacheLimitBytes] = useState("0");
  const [oauthCode, setOauthCode] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!settingsQuery.data) return;
    setStorageBackend(settingsQuery.data.storage_backend);
    setBaiduRootPath(settingsQuery.data.baidu_root_path);
    setCacheLimitBytes(String(settingsQuery.data.cache_limit_bytes));
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () =>
      updateSettings({
        storage_backend: storageBackend,
        baidu_root_path: baiduRootPath,
        cache_limit_bytes: Number(cacheLimitBytes),
      }),
    onSuccess: async () => {
      setFeedback("设置已保存。");
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  const oauthMutation = useMutation({
    mutationFn: () => authorizeBaidu(oauthCode),
    onSuccess: async () => {
      setFeedback("百度 OAuth code 已提交。");
      setError(null);
      setOauthCode("");
      await queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (exc: ApiError) => {
      setError(exc.message);
      setFeedback(null);
    },
  });

  if (session.isLoading || (session.data?.authenticated !== true && !session.isError)) {
    return <p className="state-text">正在加载设置...</p>;
  }

  const settings = settingsQuery.data;
  return (
    <div className="page-stack">
      <Surface>
        <p className="eyebrow">Settings</p>
        <h1>运行设置</h1>
        <p className="muted">这里继续沿用当前 FastAPI 设置接口，只是前端代码已经迁回 frontend/。</p>
      </Surface>

      {error ? (
        <Surface>
          <p className="error-text">{error}</p>
        </Surface>
      ) : null}
      {feedback ? (
        <Surface>
          <p>{feedback}</p>
        </Surface>
      ) : null}

      <Surface>
        <h2>运行配置</h2>
        <div className="form-stack">
          <input className="text-input" onChange={(event) => setStorageBackend(event.target.value)} placeholder="mock 或 baidu" value={storageBackend} />
          <input className="text-input" onChange={(event) => setBaiduRootPath(event.target.value)} placeholder="Baidu root path" value={baiduRootPath} />
          <input className="text-input" inputMode="numeric" onChange={(event) => setCacheLimitBytes(event.target.value)} placeholder="缓存字节数" value={cacheLimitBytes} />
          <button className="primary-button" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()} type="button">
            {saveMutation.isPending ? "保存中..." : "保存设置"}
          </button>
        </div>
        {settings ? <p className="muted">当前缓存上限：{formatBytes(settings.cache_limit_bytes)} · 当前存储后端：{settings.storage_backend}</p> : null}
      </Surface>

      <Surface>
        <h2>百度授权</h2>
        <p className="muted">首次接入百度仍然需要管理员手工完成一次 OAuth 授权码流程。</p>
        {settings?.baidu_authorize_url ? (
          <a className="primary-button link-button" href={settings.baidu_authorize_url} rel="noreferrer" target="_blank">
            打开百度授权页
          </a>
        ) : (
          <p className="muted">当前还没有可用的授权链接，请先配置环境变量。</p>
        )}
        <div className="form-stack top-gap">
          <input className="text-input" onChange={(event) => setOauthCode(event.target.value)} placeholder="粘贴百度返回的 code" value={oauthCode} />
          <button className="primary-button" disabled={oauthMutation.isPending || oauthCode.trim().length === 0} onClick={() => oauthMutation.mutate()} type="button">
            {oauthMutation.isPending ? "提交中..." : "提交 OAuth code"}
          </button>
        </div>
        <p className="muted">Refresh Token 状态：{settings?.baidu_has_refresh_token ? "已存在" : "未配置"}</p>
      </Surface>
    </div>
  );
}
