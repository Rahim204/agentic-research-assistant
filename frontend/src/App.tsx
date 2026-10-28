import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import QueryPage from "./pages/QueryPage";
import SessionPage from "./pages/SessionPage";
import DashboardPage from "./pages/DashboardPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<QueryPage />} />
        <Route path="/session/:sessionId" element={<SessionPage />} />
        <Route path="/session/:sessionId/results" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
