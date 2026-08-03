import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  ColorType,
  type CandlestickData,
} from "lightweight-charts";

import { getKlines } from "../../services/api";

type PriceChartProps = {
  symbol: string;
};

export default function PriceChart({ symbol }: PriceChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const container = chartContainerRef.current;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 400,
      layout: {
        background: {
          type: ColorType.Solid,
          color: "#101827",
        },
        textColor: "#ffffff",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries);

    async function loadCandles() {
      const response = await getKlines(symbol, "15m", 100);

      const candles: CandlestickData[] = response.data.map((item: any) => ({
        time: item.time,
        open: item.open,
        high: item.high,
        low: item.low,
        close: item.close,
      }));

      candleSeries.setData(candles);
      chart.timeScale().fitContent();
    }

    loadCandles();

    const handleResize = () => {
      chart.applyOptions({
        width: container.clientWidth,
      });
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [symbol]);

  return (
    <div className="panel">
      <h2>{symbol} Live Chart</h2>
      <div ref={chartContainerRef} style={{ width: "100%", height: "400px" }} />
    </div>
  );
}
