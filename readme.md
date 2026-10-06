# SMH Panel

پنل مدیریت VPN شخصی برای سرورهای Ubuntu/Debian — ساده برای استفاده، حرفه‌ای در زیرساخت.

SMH Panel یک پنل وب فارسی (RTL) برای مدیریت **Xray-core** (VLESS / VMess / Trojan / Shadowsocks) و **WireGuard** است: ساخت اینباند و کاربر، سهمیه و انقضا، لینک اشتراک، QR، آمار ترافیک، مدیریت سرویس‌ها و بکاپ — همه از داخل مرورگر.

---

## ویژگی‌ها

- **مدیریت کامل اینباندها**: VLESS (Reality / TLS / WS / gRPC)، VMess، Trojan، Shadowsocks (از جمله 2022)، WireGuard
- **مدیریت کاربران**: UUID/رمز، سهمیه GB، تاریخ انقضا، فعال/غیرفعال، ریست مصرف — با غیرفعال‌سازی خودکار در صورت اتمام سهمیه یا انقضا
- **لینک و اشتراک**: لینک استاندارد vless/vmess/trojan/ss، کانفیگ WireGuard، لینک Subscription (base64 و Clash/Mihomo)، QR کد
- **آمار مصرف**: خواندن مستقیم شمارنده‌های Xray (gRPC StatsService) با تحمل ری‌استارت‌ها
- **مشخصات سرور**: نمایش کامل پردازنده، حافظهٔ کل/استفاده‌شده/آزاد، سواپ، دیسک، کرنل و معماری در داشبورد
- **رابط فارسی راست‌به‌چپ** با پوستهٔ تیره/روشن و حالت انگلیسی
- **امنیت**: نشست کوکی HttpOnly + CSRF، هش bcrypt، محدودیت تلاش ورود، لاگ رویدادها، دسترسی root فقط از طریق helperهای محدود و اعتبارسنجی‌شده
- **نصب تک‌دستوری** که علاوه بر پنل، تنظیمات امنیتی و بهینه‌سازی سرور را هم اعمال می‌کند

## پروتکل‌ها

| پروتکل | حالت‌ها | پیشنهاد |
|---|---|---|
| VLESS | Reality (TCP)، TLS، WS، gRPC | ✅ Reality روی 443 — مقاوم و سریع |
| VMess | WS، TCP (+TLS) | برای سازگاری با کلاینت‌های قدیمی |
| Trojan | TCP، WS (TLS) | نیاز به دامنه/گواهی |
| Shadowsocks | 2022 و AES/ChaCha | سبک، بدون گواهی |
| WireGuard | UDP، NAT خودکار | مناسب موبایل/گیمینگ |

## پیش‌نیاز سرور

- Ubuntu 22.04/24.04 یا Debian 12
- معماری amd64 یا arm64
- دسترسی root (sudo)
- دامنه اختیاری است (برای HTTPS معتبر توصیه می‌شود؛ بدون دامنه از گواهی خودامضا + Reality استفاده می‌شود)

## نصب تک‌دستوری

پس از انتشار مخزن روی GitHub (مثلاً `SMH-AI-Dev/smh-vpn-panel`):

```bash
# بدون دامنه (IP + گواهی خودامضا؛ Reality بدون دامنه هم کار می‌کند)
bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh)

# با دامنه (گواهی Let's Encrypt خودکار برای پنل)
bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh) --domain panel.example.com --email me@example.com
```

یا از داخل مخزن: `sudo bash install.sh`

نصب‌کننده به‌صورت خودکار: پکیج‌ها و Xray و WireGuard را نصب می‌کند، سرویس systemd می‌سازد، **ufw** و **fail2ban** و **BBR** و فورواردینگ WireGuard و به‌روزرسانی‌های امنیتی خودکار را فعال می‌کند، رمز ادمین تصادفی می‌سازد و همه‌چیز را در `/root/smhpanel-credentials.txt` ذخیره می‌کند.

جزئیات و همهٔ فلگ‌ها: [docs/install-fa.md](docs/install-fa.md)

## بعد از نصب

1. آدرس پنل را باز کن: `https://<IP یا دامنه>:2053` (در حالت بدون دامنه، هشدار گواهی را می‌توانی بپذیری)
2. یک اینباند بساز — پیشنهاد: **VLESS + TCP + Reality** روی پورت ۴۴۳
3. کاربر بساز و لینک/QR یا لینک اشتراک را در اپ (v2rayNG، Hiddify، Streisand، v2rayN، Nekoray…) وارد کن

راهنمای استفاده: [docs/usage-fa.md](docs/usage-fa.md) — رفع اشکال: [docs/troubleshooting-fa.md](docs/troubleshooting-fa.md)

## مدیریت از ترمینال

```bash
smhpanel status                          # وضعیت سرویس‌ها و آمار
smhpanel backup --out /root/backup.tar.gz
smhpanel reset-admin-password --user admin
systemctl restart smhpanel               # ری‌استارت پنل
systemctl restart xray                   # ری‌استارت Xray
systemctl restart wg-quick@wg0           # ری‌استارت وایرگارد
journalctl -u smhpanel -n 100 -f         # لاگ پنل
journalctl -u xray -n 100 -f             # لاگ Xray
```

## ساختار پروژه

```
smh-vpn-panel/
├── install.sh / uninstall.sh     # نصب و حذف تک‌دستوری
├── app/                          # پنل (FastAPI + SPA)
│   ├── smhpanel/                 # بک‌اند: API، سرویس‌ها، Xray/WG، ترافیک
│   ├── static/                   # رابط فارسی (بدون وابستگی خارجی)
│   └── tests/                    # تست‌های pytest
├── deploy/                       # systemd، helperها، sudoers، sysctl، fail2ban
├── docs/                         # راهنماهای فارسی
└── proto/                        # StatsService برای خواندن ترافیک Xray
```

## توسعه و تست

```bash
cd app
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests -q
```

جزئیات محیط توسعه: [app/dev.md](app/dev.md)

## English (short)

SMH Panel is a self-hosted, Persian-first web panel to manage VPN inbounds (VLESS/Reality, VMess, Trojan, Shadowsocks, WireGuard) on Ubuntu/Debian servers: clients, quotas, expiry, share links, subscriptions, QR codes, traffic accounting, backups — installed with a single command that also applies server hardening (ufw, fail2ban, BBR, auto security updates). See `docs/` for details.

## License

MIT © Seyed Mehdi Hosseini
