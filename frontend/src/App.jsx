import { ThemeProvider } from "./context/ThemeContext";
import { AppRoutes } from "./routes";
import "./App.css";

function App() {
  return (
    <ThemeProvider>
      <AppRoutes />
    </ThemeProvider>
  );
}

export default App;
