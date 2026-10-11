import { useState } from "react";
import { Navbar, type Tab } from "./components/layout/Navbar";
import { BenchmarkPage } from "./pages/BenchmarkPage";
import { GraphPage } from "./pages/GraphPage";

export function App() {
  const [tab, setTab] = useState<Tab>("graph");

  return (
    <div>
      <Navbar active={tab} onChange={setTab} />
      {tab === "graph" ? <GraphPage /> : <BenchmarkPage />}
    </div>
  );
}
