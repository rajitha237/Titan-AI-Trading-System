import axios from "axios";

const API_ROOT = (
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

const API_BASE = `${API_ROOT}/api/v1`;

const api = axios.create({
  baseURL: API_BASE,
});

export async function getTitanStatus() {
  const response = await api.get("/auto-testnet/run");
  return response.data;
}

export async function getJournal() {
  const response = await api.get("/journal");
  return response.data;
}

export async function getTestnetStatus() {
  const response = await api.get("/testnet/status");
  return response.data;
}

export async function getKlines(
  symbol: string = "BTCUSDT",
  interval: string = "15m",
  limit: number = 100,
) {
  const response = await api.get(
    `/market/klines?symbol=${symbol}&interval=${interval}&limit=${limit}`,
  );

  return response.data;
}
