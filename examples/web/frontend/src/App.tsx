import { AppShell, Group, NavLink } from "@mantine/core";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import HistoryPage from "./routes/HistoryPage";
import LiveTrialPage from "./routes/LiveTrialPage";
import ResultsPage from "./routes/ResultsPage";
import SetupPage from "./routes/SetupPage";

function AppNav() {
  const location = useLocation();
  return (
    <Group h="100%" px="md" gap="xs">
      <NavLink
        component={Link} to="/" label="New trial"
        active={location.pathname === "/"} style={{ width: "auto" }}
      />
      <NavLink
        component={Link} to="/trials" label="History"
        active={location.pathname === "/trials"} style={{ width: "auto" }}
      />
    </Group>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell header={{ height: 56 }} padding="md">
        <AppShell.Header>
          <AppNav />
        </AppShell.Header>
        <AppShell.Main>
          <Routes>
            <Route path="/" element={<SetupPage />} />
            <Route path="/trial/:trialId" element={<LiveTrialPage />} />
            <Route path="/trial/:trialId/result" element={<ResultsPage />} />
            <Route path="/trials" element={<HistoryPage />} />
          </Routes>
        </AppShell.Main>
      </AppShell>
    </BrowserRouter>
  );
}
