import { FormEvent, useEffect, useState } from "react";
import { AuthError, Role, login, setToken } from "./api";
import { Lang, messages } from "./i18n";
import EnergyFeedstock from "./pages/EnergyFeedstock";
import ForecastDecision from "./pages/ForecastDecision";
import ProcessIntelligence from "./pages/ProcessIntelligence";
import QualityPrediction from "./pages/QualityPrediction";

export default function App() {
  const [lang, setLang] = useState<Lang>("fa");
  const [role, setRole] = useState<Role | null>(null);
  const t = messages[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
  }, [lang]);

  const logout = () => {
    setToken("");
    setRole(null);
  };

  return (
    <main>
      <header>
        <h1>{t.title}</h1>
        <div>
          {role && <button onClick={logout}>{t.logout}</button>}{" "}
          <button onClick={() => setLang(lang === "fa" ? "en" : "fa")}>{lang === "fa" ? "EN" : "فا"}</button>
        </div>
      </header>
      <div className="notice">{t.scaffoldNotice}</div>
      {role ? <Shell role={role} lang={lang} onAuthLost={logout} /> : <Login lang={lang} onLogin={setRole} />}
    </main>
  );
}

function Shell({ role, lang, onAuthLost }: { role: Role; lang: Lang; onAuthLost: () => void }) {
  const [tab, setTab] = useState<"process" | "energy" | "quality" | "forecast">("process");
  const t = messages[lang].tabs;
  return (
    <>
      <nav className="tabs">
        {(["process", "energy", "quality", "forecast"] as const).map((k) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>
            {t[k]}
          </button>
        ))}
      </nav>
      {tab === "process" && <ProcessIntelligence onAuthLost={onAuthLost} />}
      {tab === "energy" && <EnergyFeedstock onAuthLost={onAuthLost} />}
      {tab === "quality" && <QualityPrediction onAuthLost={onAuthLost} />}
      {tab === "forecast" && <ForecastDecision onAuthLost={onAuthLost} />}
      <p style={{ margin: "0 1.25rem", fontSize: "0.8rem", color: "#666" }}>role: {role}</p>
    </>
  );
}

function Login({ lang, onLogin }: { lang: Lang; onLogin: (r: Role) => void }) {
  const t = messages[lang];
  const [u, setU] = useState("admin");
  const [p, setP] = useState("");
  const [err, setErr] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      onLogin(await login(u, p));
    } catch (e) {
      if (e instanceof AuthError) setErr(true);
    }
  };

  return (
    <form className="card" onSubmit={submit} style={{ maxWidth: 320 }}>
      <label>
        {t.username}
        <input value={u} onChange={(e) => setU(e.target.value)} style={{ display: "block", width: "100%" }} />
      </label>
      <label>
        {t.password}
        <input
          type="password"
          value={p}
          onChange={(e) => setP(e.target.value)}
          style={{ display: "block", width: "100%" }}
        />
      </label>
      {err && <p style={{ color: "#c0392b" }}>{t.loginError}</p>}
      <button type="submit">{t.login}</button>
    </form>
  );
}
