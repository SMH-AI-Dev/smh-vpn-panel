<div align="center">

# 🎛️ SMH Panel

### پنل مدیریت VPN — ساده برای استفاده، حرفه‌ای در زیرساخت

**Xray (VLESS / Reality / VMess / Trojan / Shadowsocks) + WireGuard، با رابط فارسی راست‌به‌چپ و نصب تک‌دستوری**

[![Version](https://img.shields.io/github/v/tag/SMH-AI-Dev/smh-vpn-panel?label=version&color=blueviolet&style=for-the-badge)](https://github.com/SMH-AI-Dev/smh-vpn-panel/releases)
[![CI](https://github.com/SMH-AI-Dev/smh-vpn-panel/actions/workflows/ci.yml/badge.svg)](https://github.com/SMH-AI-Dev/smh-vpn-panel/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-2ea44f?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-ffd343?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Platform](https://img.shields.io/badge/platform-Ubuntu%2022.04%20%7C%2024.04%20%7C%20Debian%2012-e95420?style=for-the-badge&logo=ubuntu&logoColor=white)](#-پیشنیازها)
![UI Environments](https://img.shields.io/badge/UI%20environments-63%2B-ff69b4?style=for-the-badge)

<img src="https://img.shields.io/badge/🇮🇷_Persian_UI-RTL-26a69a?style=flat-square" /> <img src="https://img.shields.io/badge/⚡_One--Command_Install-ready-ff9800?style=flat-square" /> <img src="https://img.shields.io/badge/🛡_Hardened_by_default-yes-3f51b5?style=flat-square" /> <img src="https://img.shields.io/badge/🎨_63%2B_UI_Environments-colorful-e91e63?style=flat-square" />

</div>

---

## 🌟 معرفی

**SMH Panel** یک پنل وب شخصی برای مدیریت VPN روی سرور خودت است: در چند کلیک اینباند بساز، کاربر اضافه کن، سهمیه و انقضا بده و لینک / QR / لینک اشتراک را تحویل بگیر. همه‌چیز فارسیِ راست‌به‌چپ، سریع و بدون وابستگی به سرویس خارجی.

یک دستور نصب، و علاوه بر پنل، **همهٔ تنظیمات امنیتی و بهینه‌سازی سرور** هم خودکار اعمال می‌شود: فایروال، fail2ban، BBR، به‌روزرسانی امنیتی خودکار و…

> 💡 **فلسفهٔ پنل:** ابزار خوب، کار بزرگ را ساده می‌کند؛ تو فقط به مسیر فکر کن.

## ✨ ویژگی‌ها

- 🧩 **مدیریت کامل اینباندها** — VLESS (Reality / TLS / WS / gRPC)، VMess، Trojan، Shadowsocks (از جمله 2022)، WireGuard
- 👥 **مدیریت کاربران** — UUID/رمز، سهمیهٔ GB، تاریخ انقضا، فعال/غیرفعال، ریست مصرف، با <span title="auto disable">غیرفعال‌سازی خودکار</span>
- 🔗 **لینک و اشتراک** — لینک استاندارد vless/vmess/trojan/ss، کانفیگ WireGuard، لینک Subscription (base64 / raw / Clash)، QR کد
- 📊 **آمار مصرف** — خواندن مستقیم شمارنده‌های Xray با تحمل ری‌استارت‌ها
- 🖥️ **مشخصات کامل سرور** — پردازنده، حافظهٔ کل/مصرف‌شده/آزاد، سواپ، دیسک، کرنل و معماری
- 🎨 **۶۰+ محیط کاربری** — استخراج‌شده از مجموعه‌های واقعی (HyprPanel و PasarGuard) + پیش‌تنظیم‌های چیدمان (فشرده/جادار/صاف)
- 🇮🇷 **رابط فارسی RTL** با حالت انگلیسی، پوستهٔ تیره/روشن و فونت‌های داخلی
- 🔒 **امنیت** — نشست امن + CSRF، هش bcrypt، محدودیت تلاش ورود، لاگ رویدادها، دسترسی root فقط از طریق helperهای اعتبارسنجی‌شده
- 🛠️ **نصب تک‌دستوری** — پنل + امنیت + بهینه‌سازی سرور، همه با یک دستور
- 💾 **بکاپ/بازیابی**، گزارش رویدادها، کنترل سرویس‌ها و روشن/خاموش کردن همه‌چیز از داخل مرورگر

## 🚀 نصب تک‌دستوری

روی سرور (ترجیحاً تازهٔ Ubuntu 22.04/24.04 یا Debian 12) با کاربر root یا sudo:

**۱) نصب بدون دامنه (IP + گواهی خودامضا — Reality بدون دامنه هم عالی کار می‌کند):**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh)
```

**۲) نصب با دامنه (گواهی Let's Encrypt خودکار برای پنل):**

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh) --domain panel.example.com --email me@example.com
```

> 🔐 اگر سرور به GitHub دسترسی ندارد، `--gh-proxy https://ghproxy.net/` را اضافه کن؛ یا کل مخزن را منتقل کن و `sudo bash install.sh` بزن.
> 📖 جزئیات کامل فلگ‌ها: [docs/install-fa.md](docs/install-fa.md)

## 🧭 بعد از نصب

1. آدرس پنل را باز کن: `https://<IP یا دامنه>:2053`
2. یک اینباند بساز — پیشنهاد: **VLESS + TCP + Reality** روی پورت ۴۴۳
3. کاربر بساز و لینک/QR یا لینک اشتراک را در اپ (v2rayNG، Hiddify، Streisand، v2rayN، Nekoray…) وارد کن

راهنمای استفاده: [docs/usage-fa.md](docs/usage-fa.md) · رفع اشکال: [docs/troubleshooting-fa.md](docs/troubleshooting-fa.md)

## 🎨 محیط‌های کاربری (۶۰+ محیط آماده)

محیط‌های کاربری از دل نمونه‌های واقعی استخراج و به پنل اضافه شدهاند — نه فقط رنگ؛ بلکه رنگ‌بندی کامل تمام اجزای پنل؛ به‌علاوهٔ بخش **چیدمان** که فشردگی، سایه‌ها و گردی گوشه‌ها را هم عوض می‌کند:

- 🍭 **۴۵ محیط از مجموعهٔ HyprPanel** — Catppuccin (Latte/Frappe/Macchiato/Mocha)، Dracula، Nord، Gruvbox، Tokyo Night (+Moon)، Rosé Pine (+Moon)، Cyberpunk، Everforest، One Dark، Monochrome — هر کدام در سه حالت **base / split / vivid**
- 🟨 **۱۶ محیط از سیستم تم PasarGuard** — ترکیب رنگ‌های پایه (Slate/Zinc/Neutral/Mauve/Olive/Mist/Stone/Gray) با لهجه‌ها (Blue/Cyan/Violet/Indigo/Rose/Green/Teal/Amber/Red) در دو حالت تیره/روشن
- 🧩 **چیدمان‌ها (از PasarGuard):** vega (راحت) · nova (فشرده) · maia (جادار) · lyra (صاف)
- 🖥️ همه از داخل پنل: دکمهٔ «🎨 محیط کاربری» با جست‌وجو و پیش‌نمایش زنده

## 📡 پروتکل‌ها

| پروتکل | حالت‌ها | پیشنهاد |
|---|---|---|
| 🚀 VLESS | Reality (TCP)، TLS، WS، gRPC | ✅ Reality روی ۴۴۳ — مقاوم و سریع، بدون نیاز به دامنه |
| 🧱 VMess | WS، TCP (+TLS) | سازگاری با کلاینت‌های قدیمی‌تر |
| 🐴 Trojan | TCP، WS (TLS) | با دامنه و گواهی معتبر |
| 🥷 Shadowsocks | 2022 و AES/ChaCha | سبک و سریع، بدون گواهی |
| 🧵 WireGuard | UDP، NAT خودکار | موبایل و گیمینگ |

## 🛡 نصب‌کننده چه چیزهایی را خودش تنظیم می‌کند؟

- 🔥 فایروال ufw — فقط پورت‌های لازم باز می‌شود (SSH، پنل، ۸۰ و WireGuard)
- 🚫 fail2ban — محافظت SSH (۵ تلاش ← ۱ ساعت بن)
- ⚡ BBR + fq + تنظیمات شبکه برای سرعت بیشتر
- 🔁 به‌روزرسانی امنیتی خودکار (بدون ری‌استارت خودکار)
- 🔑 رمز ادمین تصادفی + ذخیرهٔ امن در `/root/smhpanel-credentials.txt`
- 🌐 `ip_forward` برای NAT وایرگارد + سرویس systemd سخت‌شده

## 🧰 مدیریت از ترمینال

```bash
smhpanel status                          # وضعیت سرویس‌ها و آمار
smhpanel backup --out /root/backup.tar.gz
smhpanel reset-admin-password --user admin
systemctl restart smhpanel               # ری‌استارت پنل
journalctl -u smhpanel -n 100 -f         # لاگ پنل
journalctl -u xray -n 100 -f             # لاگ Xray
```

## ❓ سوالات متداول

<details>
<summary>🔌 کلاینت وصل نمی‌شود؟</summary>

1. مطمئن شو کاربر فعال است و سهمیه/انقضا تمام نشده
2. برای Reality، SNI انتخابی باید از سرور قابل‌دست‌رس باشد (پیش‌فرض‌ها تست‌شده‌اند)
3. ساعت سرور را چک کن (`timedatectl`)
4. اگر شبکه‌ات ترافیک را محدود می‌کند، WireGuard (UDP) را امتحان کن
</details>

<details>
<summary>🔒 لینک اشتراک در اپ باز نمی‌شود؟</summary>

در حالت بدون دامنه، گواهی خودامضاست؛ گزینهٔ «اجازهٔ گواهی نامعتبر / Allow insecure» را فعال کن یا از لینک/QR مستقیم استفاده کن. راه بهتر: یک دامنه بگیر و با `--domain` دوباره نصب کن.
</details>

<details>
<summary>🌐 وضعیت شبکهٔ سرور را از بیرون چطور تست کنم؟</summary>

از تب Actions ← **Network probe** می‌توانی سرور را از شبکهٔ GitHub تست کنی (دانلود سلامت، پورت‌ها و…).
</details>

## 🗂 ساختار پروژه

```
smh-vpn-panel/
├── install.sh / uninstall.sh     # نصب و حذف تک‌دستوری
├── app/                          # پنل (FastAPI + SPA)
│   ├── smhpanel/                 # بک‌اند: API، سرویس‌ها، Xray/WG، ترافیک
│   ├── static/                   # رابط فارسی + فونت‌ها + ۱۱ پوسته
│   └── tests/                    # تست‌های pytest
├── deploy/                       # systemd، helperها، sudoers، sysctl، fail2ban
├── docs/                         # راهنماهای فارسی
└── proto/                        # StatsService برای خواندن ترافیک Xray
```

## 🧑‍💻 توسعه و تست

```bash
cd app
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

جزئیات محیط توسعه: [app/dev.md](app/dev.md)

---

## 👤 سازنده

<div align="center">

### **سید مهدی حسینی**

**Seyed Mehdi Hosseini**

💻 Computer Software Engineer & AI Specialist

[![Email](https://img.shields.io/badge/Email-dev.smh.ai@gmail.com-ea4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:dev.smh.ai@gmail.com)
[![Phone](https://img.shields.io/badge/Phone-%2B98%20902%20491%202785-25d366?style=for-the-badge&logo=whatsapp&logoColor=white)](tel:+989024912785)
[![GitHub](https://img.shields.io/badge/GitHub-SMH--AI--Dev-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/SMH-AI-Dev/)
[![HuggingFace](https://img.shields.io/badge/🤗_HuggingFace-SMH--DEV--AI-ffcc4d?style=for-the-badge)](https://huggingface.co/SMH-DEV-AI/)

<sub>

👤 Seyed Mehdi Hosseini
💻 Computer Software Engineer and AI specialist
📧 dev.smh.ai@gmail.com
📱 +98 902 491 2785
🤗 https://huggingface.co/SMH-DEV-AI/
💻 https://github.com/SMH-AI-Dev/

</sub>

</div>

## 📄 لایسنس

MIT © [Seyed Mehdi Hosseini](https://github.com/SMH-AI-Dev/)

---

<div align="center"><sub>ساخته‌شده با ❤️ برای اینترنت آزادتر</sub></div>

## 🇬🇧 English (short)

SMH Panel is a self-hosted, Persian-first (RTL) web panel to manage VPN inbounds (VLESS/Reality, VMess, Trojan, Shadowsocks, WireGuard) on Ubuntu/Debian servers: clients, quotas, expiry, share links, subscriptions, QR codes, traffic accounting, 11 color themes, backups — installed with a single command that also applies server hardening (ufw, fail2ban, BBR, auto security updates). See `docs/` for details. MIT licensed.
