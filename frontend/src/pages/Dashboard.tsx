import { useEffect, useState } from "react";

import Header from "../components/layout/Header";
import StatCard from "../components/cards/StatCard";
import PositionCard from "../components/cards/PositionCard";
import TradeTable from "../components/tables/TradeTable";
import PriceChart from "../components/charts/PriceChart";

import { getTitanStatus, getJournal, getTestnetStatus } from "../services/api";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [journal, setJournal] = useState<any[]>([]);
  const [testnet, setTestnet] = useState<any>(null);

  async function loadData() {
    const [statusResult, journalResult, testnetResult] =
      await Promise.allSettled([
        getTitanStatus(),
        getJournal(),
        getTestnetStatus(),
      ]);

    if (statusResult.status === "fulfilled") {
      setStatus(statusResult.value);
    } else {
      console.error("Titan status request failed:", statusResult.reason);
    }

    if (journalResult.status === "fulfilled") {
      setJournal(journalResult.value?.entries || []);
    } else {
      console.error("Journal request failed:", journalResult.reason);
    }

    if (testnetResult.status === "fulfilled") {
      setTestnet(testnetResult.value);
    } else {
      console.error("Testnet status request failed:", testnetResult.reason);
    }
  }

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 10000);
    return () => clearInterval(timer);
  }, []);

  const best = status?.best_setup;
  const symbol = status?.symbol || "-";
  const score = best?.ai_score?.score || "-";
  const decision = best?.final_decision?.decision || "-";

  return (
    <>
      <Header />

      <div className="grid">
        <StatCard title="Best Coin" value={symbol} />
        <StatCard title="AI Score" value={score} />
        <StatCard title="Decision" value={decision} />
        <StatCard
          title="Balance"
          value={`${testnet?.balance?.availableBalance || "-"} USDT`}
        />
      </div>

      <div className="grid">
        <StatCard
          title="Order Book"
          value={best?.order_book?.pressure || "-"}
        />
        <StatCard title="Trend" value={best?.technical?.trend || "-"} />
        <StatCard title="RSI" value={best?.technical?.rsi || "-"} />
        <StatCard title="MACD" value={best?.technical?.macd_direction || "-"} />
      </div>

      <PriceChart symbol={symbol === "-" ? "BTCUSDT" : symbol} />

      <PositionCard positions={testnet?.open_positions || []} />
      <TradeTable entries={journal} />
    </>
  );
}
