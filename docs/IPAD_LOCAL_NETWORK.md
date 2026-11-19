# Testing on the iPad over your local Wi-Fi

The Lenovo runs the app; the iPad opens it in Safari over the same Wi-Fi. Nothing is
put on the internet: the app is only reachable from devices on your local network, it
needs an access code, and no router settings (such as port forwarding) are changed.

Do **Windows setup** ([WINDOWS_CPU_SETUP.md](WINDOWS_CPU_SETUP.md)) first.

## 1. Use a private network

Use your **home Wi-Fi** (or the laptop hotspot below). Do not do this on public Wi-Fi
(cafés, malls).

Tell Windows that your home Wi-Fi is private (trusted):

1. **Start** → **Settings** → **Network & internet** → **Wi-Fi**.
2. Click your network's name (e.g. *MyHome-5G*) → **Properties**.
3. Under **Network profile type**, choose **Private network**.

Connect the iPad to the **same** Wi-Fi network.

## 2. Start the app for the iPad

In `C:\DnT\DnT_Sketch_to_3D`, double-click:

- **`Start-Demo-for-iPad.bat`**: demo mode (sample models, fast). Start with this.
- **`Start-AI-for-iPad.bat`**: real AI on the laptop CPU.

The black window shows something like:

```
D&T Sketch-to-3D is reachable from other devices on this network
On the iPad, open Safari and go to:  http://192.168.1.23:8000
Access code:  K7QX2M
```

### The first time: Windows Firewall

Windows asks **"Do you want to allow public and private networks to access this app?"**
for `python.exe`:

- Tick **Private networks** only. Leave **Public networks** unticked.
- Click **Allow**.

If you clicked Cancel by mistake: **Start** → type `Allow an app through Windows Firewall` →
**Change settings** → find **python.exe** (there may be two; do both) → tick **Private**,
untick **Public** → **OK**.

## 3. Open it on the iPad

1. Open **Safari** on the iPad.
2. Type the address from the black window **exactly**, including `http://` and `:8000`,
   e.g. `http://192.168.1.23:8000`.
3. Enter the **access code** from the black window and tap **Connect**.

Safari may show **Not Secure** next to the address. That is expected for a home test
(see *HTTP limitations* below).

**Finding the laptop's address yourself:** open PowerShell and run `ipconfig`. Under
**Wireless LAN adapter Wi-Fi**, use the **IPv4 Address** (usually starts with `192.168.`
or `10.`).

## 4. Stop safely

Click the black window and press **Ctrl + C** (type **Y** if asked), or close the window.
The iPad immediately loses access. The access code changes every time you start, so an
old code stops working.

## If the iPad cannot connect

| Check | How |
|---|---|
| Same network? | iPad: **Settings → Wi-Fi**. Laptop: Wi-Fi icon. The names must match (some routers have separate 2.4 GHz and 5 GHz names, so use the same one). |
| Network is Private? | Step 1 above. A *Public* profile blocks incoming connections. |
| Firewall allowed? | Step 2 above. |
| Address typed right? | `http://` (not `https://`), the numbers, and `:8000`. |
| VPN on the laptop? | Turn it off while testing. |
| School or office Wi-Fi? | These usually block device-to-device connections ("client isolation"). Use the laptop hotspot below. |

### Alternative: the laptop's own hotspot

1. Laptop: **Settings → Network & internet → Mobile hotspot**. Turn it on and note the
   network name and password.
2. iPad: join that network in **Settings → Wi-Fi**.
3. Start `Start-Demo-for-iPad.bat` and use the address it shows (often `192.168.137.1`).

## HTTP limitations (and why they do not block testing)

The local test uses plain `http://`, not `https://`. Browsers limit some features on
plain HTTP. This app was designed around that:

| Feature | Works over local HTTP? |
|---|---|
| Choosing a picture, **Take a photo** (opens the iPad Camera app) | Yes. It uses a normal file picker, not live camera access. |
| Crop, rotate, brightness, contrast | Yes |
| 3D viewer (rotate, pinch, pan) | Yes |
| Downloading STL / 3MF to the Files app | Yes |
| Live camera preview inside the web page | Not used. It would need HTTPS. |
| "Add to Home Screen" as an offline app | Not used in this stage. |

**Privacy:** on plain HTTP, traffic on your Wi-Fi is not encrypted. That is acceptable
for testing at home with **fictional sketches**, but **not** for real student work. A
school deployment will need HTTPS and proper accounts (a later stage).
