import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { authorizeBaidu, fetchSettings, updateSettings, type SettingsUpdatePayload } from "../api/client";
import { Surface } from "../components/Surface";
import { useRequireSession } from "../hooks/session";
import type { ApiError, PublicSettings } from "../types/api";
import { formatBytes } from "../utils/format";

const DEFAULT_TRANSFER_CONCURRENCY = "5";

const resolveTransferConcurrency = (
  primary: number | undefined,
  legacy: number | undefined,
  fallback: string,
): string => {
  if (typeof primary === "number" && Number.isFinite(primary)) {
    return String(primary);
  }
  if (typeof legacy === "number" && Number.isFinite(legacy)) {
    return String(legacy);
  }
  return fallback;
};

const hasSplitConcurrencyFields = (settings: PublicSettings | undefined): boolean =>
  typeof settings?.upload_transfer_concurrency === "number" &&
  typeof settings?.download_transfer_concurrency === "number";

const hasLegacyConcurrencyField = (settings: PublicSettings | undefined): boolean =>
  typeof settings?.remote_transfer_concurrency === "number";

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
  const [uploadTransferConcurrency, setUploadTransferConcurrency] = useState(DEFAULT_TRANSFER_CONCURRENCY);
  const [downloadTransferConcurrency, setDownloadTransferConcurrency] = useState(DEFAULT_TRANSFER_CONCURRENCY);
  const [oauthCode, setOauthCode] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applySettingsToForm = (settings: PublicSettings) => {
    setStorageBackend(settings.storage_backend);
    setBaiduRootPath(settings.baidu_root_path);
    setCacheLimitBytes(String(settings.cache_limit_bytes));
    setUploadTransferConcurrency((current) =>
      resolveTransferConcurrency(
        settings.upload_transfer_concurrency,
        settings.remote_transfer_concurrency,
        current || DEFAULT_TRANSFER_CONCURRENCY,
      ),
    );
    setDownloadTransferConcurrency((current) =>
      resolveTransferConcurrency(
        settings.download_transfer_concurrency,
        settings.remote_transfer_concurrency,
        current || DEFAULT_TRANSFER_CONCURRENCY,
      ),
    );
  };

  useEffect(() => {
    if (!settingsQuery.data) return;
    applySettingsToForm(settingsQuery.data);
  }, [settingsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const uploadConcurrency = Number(uploadTransferConcurrency);
      const downloadConcurrency = Number(downloadTransferConcurrency);
      const payload: SettingsUpdatePayload = {
        storage_backend: storageBackend,
        baidu_root_path: baiduRootPath,
        cache_limit_bytes: Number(cacheLimitBytes),
        upload_transfer_concurrency: uploadConcurrency,
        download_transfer_concurrency: downloadConcurrency,
      };

      if (!hasSplitConcurrencyFields(settingsQuery.data) && hasLegacyConcurrencyField(settingsQuery.data)) {
        if (uploadConcurrency !== downloadConcurrency) {
          const error: ApiError = {
            status: 409,
            message: "当前连接的后端进程还是旧版本，只支持单一并发数。请先重启后端，再分别保存上传并发和下载并发。",
          };
          throw error;
        }
        payload.remote_transfer_concurrency = uploadConcurrency;
      }

      return updateSettings(payload);
    },
    onSuccess: async (savedSettings) => {
      queryClient.setQueryData(["settings"], savedSettings);
      applySettingsToForm(savedSettings);
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
  const currentUploadConcurrency = resolveTransferConcurrency(
    settings?.upload_transfer_concurrency,
    settings?.remote_transfer_concurrency,
    uploadTransferConcurrency || DEFAULT_TRANSFER_CONCURRENCY,
  );
  const currentDownloadConcurrency = resolveTransferConcurrency(
    settings?.download_transfer_concurrency,
    settings?.remote_transfer_concurrency,
    downloadTransferConcurrency || DEFAULT_TRANSFER_CONCURRENCY,
  );
  const backendIsLegacyConcurrencyOnly =
    !hasSplitConcurrencyFields(settings) && hasLegacyConcurrencyField(settings);
  return (
    <div className="page-stack">
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
          <input
            className="text-input"
            inputMode="numeric"
            max={32}
            min={1}
            onChange={(event) => setUploadTransferConcurrency(event.target.value)}
            placeholder="上传并发数"
            type="number"
            value={uploadTransferConcurrency}
          />
          <input
            className="text-input"
            inputMode="numeric"
            max={32}
            min={1}
            onChange={(event) => setDownloadTransferConcurrency(event.target.value)}
            placeholder="下载并发数"
            type="number"
            value={downloadTransferConcurrency}
          />
          <button className="primary-button" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()} type="button">
            {saveMutation.isPending ? "保存中..." : "保存设置"}
          </button>
        </div>
        {settings ? (
          <p className="muted" style={{ marginTop: "1rem" }}>
            当前缓存上限：{formatBytes(settings.cache_limit_bytes)} 
          </p>
        ) : null}
      </Surface>

      <div className="section-divider" />

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
        <p className="muted" style={{ marginTop: "1rem" }}>Refresh Token 状态：{settings?.baidu_has_refresh_token ? "已存在" : "未配置"}</p>
      </Surface>
    </div>
  );
}
