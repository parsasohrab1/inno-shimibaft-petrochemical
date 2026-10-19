export type Lang = "fa" | "en";

export const messages = {
  fa: {
    title: "SPRO1 — شیمی بافت",
    logout: "خروج",
    login: "ورود",
    username: "نام کاربری",
    password: "گذرواژه",
    loginError: "نام کاربری یا گذرواژه نادرست است",
    tabs: {
      process: "ماژول ۱ — هوش فرآیند",
      energy: "ماژول ۲ — انرژی و خوراک",
      quality: "ماژول ۳ — پیش‌بینی کیفیت",
      forecast: "ماژول ۴ — پیش‌بینی و تصمیم‌یار",
    },
    scaffoldNotice:
      "داده نمونه برچسب‌دار؛ بدون اتصال واقعی به DCS/Historian/LIMS. مدل‌های یادگیری ماشین واقعی هستند اما فقط روی داده سنتتیک آموزش دیده‌اند — نه داده واقعی کارخانه شیمی بافت.",
  },
  en: {
    title: "SPRO1 — Shimi Baft",
    logout: "Logout",
    login: "Login",
    username: "Username",
    password: "Password",
    loginError: "Invalid username or password",
    tabs: {
      process: "Module 1 — Process Intelligence",
      energy: "Module 2 — Energy & Feedstock",
      quality: "Module 3 — Quality Prediction",
      forecast: "Module 4 — Forecasting & Decision Support",
    },
    scaffoldNotice:
      "Labelled sample data; no real DCS/Historian/LIMS connection. The ML models are real but trained only on synthetic data — not real Shimi Baft plant data.",
  },
} as const;
