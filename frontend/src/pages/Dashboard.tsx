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
    const [s, j, t] = await Promise.all([
      getTitanStatus(),
      getJournal(),
      getTestnetStatus(),
    ]);

    setStatus(s);
    setJournal(j.entries || []);
    setTestnet(t);
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
