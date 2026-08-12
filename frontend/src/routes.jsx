import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { AssetsProcessingPage } from "./features/assets/pages/AssetsProcessingPage";
import { AssetsResultsPage } from "./features/assets/pages/AssetsResultsPage";
import { AssetsUploadPage } from "./features/assets/pages/AssetsUploadPage";
import { MembersProcessingPage } from "./features/members/pages/MembersProcessingPage";
import { MembersResultsPage } from "./features/members/pages/MembersResultsPage";
import { MembersReviewPage } from "./features/members/pages/MembersReviewPage";
import { MembersUploadPage } from "./features/members/pages/MembersUploadPage";
import { ImportTypePage } from "./pages/ImportTypePage";
import { LandingPage } from "./pages/LandingPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/single-upload" element={<ImportTypePage />} />
        <Route
          path="/single-upload/members/upload"
          element={<MembersUploadPage />}
        />
        <Route
          path="/single-upload/members/processing"
          element={<MembersProcessingPage />}
        />
        <Route
          path="/single-upload/members/review"
          element={<MembersReviewPage />}
        />
        <Route
          path="/single-upload/members/results"
          element={<MembersResultsPage />}
        />
        <Route
          path="/single-upload/assets/upload"
          element={<AssetsUploadPage />}
        />
        <Route
          path="/single-upload/assets/processing"
          element={<AssetsProcessingPage />}
        />
        <Route
          path="/single-upload/assets/results"
          element={<AssetsResultsPage />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
