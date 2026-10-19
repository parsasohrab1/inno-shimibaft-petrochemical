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
      "اسکلت — داده نمونه برچسب‌دار؛ بدون اتصال واقعی به DCS/Historian/LIMS و بدون مدل یادگیری ماشین آموزش‌دیده.",
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
      "Scaffold — labelled sample data only; no real DCS/Historian/LIMS connection and no trained ML model.",
  },
} as const;
