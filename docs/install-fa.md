# راهنمای نصب SMH Panel

## پیش‌نیازها

- سرور Ubuntu 22.04/24.04 یا Debian 12 (amd64 یا arm64) با دسترسی root
- حداقل ~۵۰۰ مگابایت فضای آزاد
- (اختیاری) دامنه‌ای که به IP سرور اشاره می‌کند — برای HTTPS معتبر

## نصب با یک دستور

مخزن را روی GitHub منتشر کن (مثلاً `SMH-AI-Dev/smh-vpn-panel`) و سپس روی سرور:

```bash
# حالت IP (بدون دامنه) — Reality + گواهی خودامضای پنل
bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh)

# حالت دامنه — گواهی Let's Encrypt برای پنل
bash <(curl -fsSL https://raw.githubusercontent.com/SMH-AI-Dev/smh-vpn-panel/main/install.sh) --domain panel.example.com --email admin@example.com
```

اگر فایل‌ها را دستی روی سرور کپی کرده‌ای: `sudo bash install.sh` از داخل پوشهٔ پروژه.

### فلگ‌های نصب‌کننده

| فلگ | پیش‌فرض | توضیح |
|---|---|---|
| `--domain <domain>` | — | دامنهٔ پنل؛ گواهی Let's Encrypt با acme.sh نصب می‌شود |
| `--email <email>` | `admin@<domain>` | ایمیل ثبت Let's Encrypt |
| `--public-host <host>` | تشخیص خودکار IP | آدرسی که در لینک‌های کلاینت می‌آید |
| `--panel-port <port>` | `2053` | پورت پنل |
| `--admin-user <name>` | `admin` | نام کاربری ادمین |
| `--admin-pass <pass>` | تصادفی | رمز ادمین (در غیر این صورت رمز تصادفی ساخته و چاپ می‌شود) |
| `--no-tls` | — | اجرای پنل بدون HTTPS (توصیه نمی‌شود) |
| `--no-wireguard` | — | بدون راه‌اندازی WireGuard |
| `--wg-port` / `--wg-subnet` | `51820` / `10.66.66.0/24` | تنظیمات WireGuard |
| `--no-ufw` / `--no-fail2ban` / `--no-auto-updates` | — | غیرفعال‌کردن هر یک از سخت‌سازی‌ها |
| `--gh-proxy <prefix>` | — | پروکسی برای دانلود از GitHub (مثلاً `https://ghproxy.net/`) |
| `--xray-version <ver>` | آخرین نسخه | نصب نسخهٔ خاص Xray |
| `--check` | — | فقط بررسی پیش‌نیازها، بدون نصب |

## نصب‌کننده چه کارهایی انجام می‌دهد؟

1. **پکیج‌ها**: python3 + venv، sqlite3، curl/unzip/jq، ufw، fail2ban، socat، wireguard-tools
2. **Xray-core**: با اسکریپت رسمی XTLS (و دانلود مستقیم در صورت شکست)
3. **پنل**: کپی در `/opt/smhpanel` + virtualenv + سرویس `smhpanel.service` با محدودسازی‌های systemd
4. **دسترسی root محدود**: ۹ اسکریپت helper در `/usr/local/sbin` با اعتبارسنجی ورودی + sudoers فقط برای همان‌ها
5. **امنیت**: ufw (فقط پورت SSH، پنل و ۸۰ و پورت WireGuard باز است)، fail2ban برای SSH (۵ تلاش → ۱ ساعت بن)، به‌روزرسانی امنیتی خودکار
6. **کارایی**: BBR، fq، افزایش بک‌لاگ و فایل‌لیمیت‌ها، `ip_forward` برای WireGuard
7. **رمز ادمین** تصادفی + ذخیره در `/root/smhpanel-credentials.txt` (فقط root)

## بررسی پس از نصب

```bash
systemctl status smhpanel xray fail2ban
ufw status verbose
jq '.panel' /etc/smhpanel/config.json
journalctl -u smhpanel -n 50
```

آدرس پنل در انتهای خروجی نصب چاپ می‌شود: `https://<host>:<port>`

## حالت دامنه — نکات

- رکورد `A` دامنه باید به IP سرور اشاره کند (قبل از اجرا).
- پورت ۸۰ باید خالی و قابل‌دسترس باشد (برای acme.sh standalone).
- گواهی به‌صورت خودکار در `/etc/smhpanel/certs/<domain>.crt` نصب و تمدید می‌شود (کرون acme.sh).
- برای اینباندهای TLS هم می‌توانی از همین گواهی یا زیرِدامنهٔ جدید استفاده کنی (بخش «تنظیمات → گواهی‌ها»).

## حالت بدون دامنه (IP)

- پنل با گواهی خودامضا اجرا می‌شود؛ مرورگر هشدار می‌دهد (طبیعی است).
- برای دریافت لینک اشتراک در بعضی اپ‌ها باید گزینهٔ «اجازهٔ گواهی نامعتبر» فعال باشد؛ در غیر این صورت از لینک/QR مستقیم استفاده کن.
- پروتکل پیشنهادی بدون دامنه: **VLESS + Reality** (نیازی به گواهی ندارد).

## به‌روزرسانی پنل

همان دستور نصب را دوباره اجرا کن — کدها به‌روز می‌شوند و دیتابیس/تنظیمات حفظ می‌شوند. یا:

```bash
systemctl stop smhpanel
/opt/smhpanel/venv/bin/pip install -r /opt/smhpanel/app/requirements.txt
systemctl start smhpanel
```

## حذف پنل

اسکریپت `uninstall.sh` در ریشهٔ مخزن قرار دارد:

- `bash uninstall.sh` → سرویس و فایل‌های اجرایی پنل را برمی‌دارد، داده‌ها (DB/تنظیمات) حفظ می‌شوند
- `bash uninstall.sh --purge` → داده‌ها و کاربر سیستمی هم پاک می‌شوند

Xray، ufw و fail2ban دست‌نخورده می‌مانند.
