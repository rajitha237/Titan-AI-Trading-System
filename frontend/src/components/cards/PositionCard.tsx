export default function PositionCard({ positions }: { positions: any[] }) {
  return (
    <div className="panel">
      <h2>Open Positions</h2>
      {positions?.length ? (
        <pre>{JSON.stringify(positions, null, 2)}</pre>
      ) : (
        <p>No open positions</p>
      )}
    </div>
  );
}
