import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import HistoryPage from "./routes/HistoryPage";
import LiveTrialPage from "./routes/LiveTrialPage";
import ResultsPage from "./routes/ResultsPage";
import SetupPage from "./routes/SetupPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav className="app-nav">
        <Link to="/">New trial</Link>
        <Link to="/trials">History</Link>
      </nav>
      <Routes>
        <Route path="/" element={<SetupPage />} />
        <Route path="/trial/:trialId" element={<LiveTrialPage />} />
        <Route path="/trial/:trialId/result" element={<ResultsPage />} />
        <Route path="/trials" element={<HistoryPage />} />
      </Routes>
    </BrowserRouter>
  );
}
