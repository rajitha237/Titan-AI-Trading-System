async function refresh() {
  const response = await fetch("/api/v1/auto-testnet/run");

  const data = await response.json();

  document.getElementById("output").textContent = JSON.stringify(data, null, 2);
}

refresh();

setInterval(refresh, 10000);
