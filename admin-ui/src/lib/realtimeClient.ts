import { AppSyncClient } from "./appSyncClient";

const APPSYNC_API_URL = process.env.NEXT_PUBLIC_APPSYNC_API_URL || "";
const APPSYNC_REGION = process.env.NEXT_PUBLIC_APPSYNC_REGION || "us-east-1";
const APPSYNC_API_KEY = process.env.NEXT_PUBLIC_APPSYNC_API_KEY || "";
const APPSYNC_NAMESPACE = process.env.NEXT_PUBLIC_APPSYNC_NAMESPACE || "default";

let appSyncClientSingleton: AppSyncClient | null = null;

export function getAppSyncClient(): AppSyncClient {
  if (!appSyncClientSingleton) {
    appSyncClientSingleton = new AppSyncClient(APPSYNC_API_URL, {
      region: APPSYNC_REGION,
      apiKey: APPSYNC_API_KEY,
      namespace: APPSYNC_NAMESPACE,
      enabledTransports: ["ws", "wss"],
      forceTLS: true,
    });
  }
  return appSyncClientSingleton;
}
