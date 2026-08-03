export default function TradeTable({ entries }) {
  return (
    <div className="panel">
      <h2>Trade Journal</h2>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Symbol</th>
            <th>Score</th>
            <th>Decision</th>
            <th>Execution</th>
          </tr>
        </thead>
        <tbody>
          {entries
            ?.slice(-10)
            .reverse()
            .map((e, i) => (
              <tr key={i}>
                <td>{new Date(e.timestamp).toLocaleTimeString()}</td>
                <td>{e.symbol}</td>
                <td>{e.ai_score?.score}</td>
                <td>{e.final_decision?.decision}</td>
                <td>{e.execution?.status}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
