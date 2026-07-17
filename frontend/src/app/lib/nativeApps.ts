export type NativeRecruitmentApps = {
  openZhaopin: () => string;
  openZhaopinSearch?: () => string;
};

declare global {
  interface Window {
    CareerPilotNativeApps?: NativeRecruitmentApps;
  }
}

const launchMessages: Record<string, string> = {
  app_opened: "已打开智联招聘 App",
  store_opened: "未安装智联招聘，已打开应用商店",
  website_opened: "未安装智联招聘，已打开智联招聘官网",
  failed: "无法打开智联招聘，请稍后重试",
};

export function openRecruitmentPlatformInNativeApp(
  platformKey: string,
  bridge: NativeRecruitmentApps | undefined = typeof window === "undefined"
    ? undefined
    : window.CareerPilotNativeApps,
) {
  if (platformKey !== "zhaopin" || !bridge) return null;
  try {
    const result = bridge.openZhaopin();
    return launchMessages[result] ?? "已请求打开智联招聘";
  } catch {
    return launchMessages.failed;
  }
}

export function openZhaopinSearchInNativeApp(
  bridge: NativeRecruitmentApps | undefined = typeof window === "undefined"
    ? undefined
    : window.CareerPilotNativeApps,
) {
  if (!bridge?.openZhaopinSearch) return null;
  try {
    const result = bridge.openZhaopinSearch();
    return launchMessages[result] ?? "已打开智联招聘，请在 App 内搜索职位";
  } catch {
    return launchMessages.failed;
  }
}
