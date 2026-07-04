import { useAuthStore } from "./stores/useAuthStore";
import Admin from "./pages/Admin";
import Login from "./pages/Login";

export default function App() {
  const token = useAuthStore((s) => s.token);
  return token ? <Admin /> : <Login />;
}
