import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Layout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="pulse" aria-hidden="true" />
          QvaPay P2P
        </div>

        <button
          className="hamburger"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Cerrar menú" : "Abrir menú"}
          aria-expanded={open}
        >
          {open ? "✕" : "☰"}
        </button>

        <nav className={`nav ${open ? "open" : ""}`} onClick={() => setOpen(false)}>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/rules">Reglas</NavLink>
          <NavLink to="/history">Historial</NavLink>
        </nav>

        <div className={`user ${open ? "open" : ""}`}>
          <span className="muted">{user?.username ?? user?.uuid}</span>
          <button className="btn btn-ghost" onClick={() => logout()}>
            Salir
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
