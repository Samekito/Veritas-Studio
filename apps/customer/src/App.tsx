import { NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Library from "./pages/Library";
import Passport from "./pages/Passport";
import Verify from "./pages/Verify";

export default function App() {
  return (
    <>
      <nav className="nav">
        <NavLink to="/" className="brand">
          <span className="dot" />
          Veritas Studio
        </NavLink>
        <div className="links">
          <NavLink to="/" end>
            Create
          </NavLink>
          <NavLink to="/library">Library</NavLink>
          <NavLink to="/verify">Verify</NavLink>
        </div>
        <div className="spacer" />
        <span className="badge">Genblaze · Backblaze B2</span>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/library" element={<Library />} />
        <Route path="/passport/:id" element={<Passport />} />
        <Route path="/verify" element={<Verify />} />
      </Routes>
    </>
  );
}
