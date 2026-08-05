# SilverSpoon (previously FitGirlDownloader)

> **Note:** Currently supports `fuckingfast.co` and `datanodes.to` links (commonly used by FitGirl Repacks and direct download mirrors). Support for additional hosts may be added in the future.

A Python-based bulk downloader designed to bypass Cloudflare protections on file-hosting sites like *fuckingfast.co* and *datanodes.to*. It automates the process of extracting direct download links and supports concurrent downloading with pause and resume capabilities.

## Features

* **Auto-Updater:** (Windows only) Automatically checks for, downloads, and applies new updates so you are always on the latest version without manual `.zip` downloads.
* **Cross-Platform Extraction:** Built-in auto-extraction support for Windows (bundled `7z`), as well as Linux and macOS (via `/usr/bin/7z` / `p7zip`).
* **Cloudflare Turnstile Bypass:** Uses a hidden Chromium browser (via `nodriver`) to auto-solve Cloudflare Turnstile challenges invisibly, then downloads via `curl_cffi` with TLS impersonation. No manual CAPTCHA solving needed for normal IPs.
* **Persistent Download History:** Automatically saves your task queue, progress, and folder groupings across sessions. Close the app anytime without losing your place!
* **Grouped Batch Folders:** Downloads are neatly organized into collapsible dropdown trees, showing aggregated progress, speed, and ETA for entire batches.
* **Smart Folder Grouping & Batching:** Automatically suggests a unified folder name for a batch of links, perfectly grouping main game parts and messy optional files together.
* **Persistent Settings:** Your preferences (save directory, concurrent workers, extraction options) are saved and remembered for your next session.
* **Download Scheduler:** Set up scheduled download windows (weekly or one-off) for off-peak downloading, with optional Windows wake timers and sleep prevention.
* **Bandwidth Limiter:** Set a global download speed limit in Settings to reserve network bandwidth for other apps.
* **Import Links & Smart Clipboard Extraction:** Load link lists from `.txt` files or paste text/HTML directly — SilverSpoon automatically extracts valid `http` links from formatted webpage clipboard data.
* **Inline Progress Bars:** Visual progress bars painted directly behind filenames and batch folders in the queue.
* **Live Speed & ETAs:** Features a real-time global download speed tracker and calculates Estimated Time Remaining (ETA) for both individual files and total batch completions.
* **Context Menu Actions:** Right-click tasks to manually extract archives ("Extract Now"), open download directories ("Open Folder"), schedule intervals, retry, or force redownload.
* **Customizable UI & Shortcuts:** Interactive, resizable columns that save their state, responsive button feedback (hover/pressed/disabled states), plus right-click context menus and handy keyboard shortcuts (e.g., `Space` to pause/resume, `Delete` to remove tasks).
* **Auto-Retry & CAPTCHA Timeout:** Configurable options to automatically retry failed downloads up to 3 times and customize Turnstile CAPTCHA wait timeouts.
* **File Management:** Safely delete tasks and optionally remove their associated physical files from your disk, or use "Force Redownload" to wipe and restart a corrupted file.
* **Error Diagnostics:** Hover over failed tasks for detailed tooltips, and easily copy error logs for quick troubleshooting.
* **Direct Link Extraction:** Automatically simulates the internal HTMX POST requests required to fetch the real `.rar` direct links.
* **Multi-threading:** Downloads multiple parts concurrently (default 3 workers, customizable in Settings) to maximize bandwidth.
* **Pause, Resume & Retry:** Safely pause your downloads, recover from network drops, or quickly retry errored links using HTTP `Range` headers.
* **Graphical Interface:** Includes a clean, modern GUI built with PyQt6.
* **Command Line Interface:** Also includes a lightweight CLI script for server environments or automation.

## Requirements

* Python 3.10+
* Dependencies listed in `requirements.txt`

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/billysams21/SilverSpoon.git
   cd SilverSpoon
   ```
2. Install the required Python packages (or do it inside virtual environment):
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Using the GUI (Recommended)
Launch the graphical interface (or double-click `SilverSpoon.exe`):
```bash
python pyqt_downloader.py
```

![App Screenshot 1](assets/screenshot1.png)

1. Click **Browse...** to select your base save directory (or set a persistent default in `File -> Settings`).
2. Open the game link and click the provider you want to use (for now it's FuckingFast).
![FitGirl 1](assets/fitgirl1.png)
3. Copy the links you want to download.
![FitGirl 2](assets/fitgirl2.png)
4. Paste your links into the top text box (one per line) or use `File -> Import Links from File...`. You can also copy links/tables straight from your browser and click **Paste from Clipboard**—SilverSpoon automatically extracts the direct URLs from rich HTML clipboard data.
![App Screenshot 2](assets/screenshot2.png)
5. Click **Add Links to Queue**. A prompt will appear allowing you to confirm the Batch Folder name so all main and optional files go to the exact same place.
6. Click **Select All** (or check individual boxes) for the files you want to download.
7. (Optional) Check the **Extract after download** checkbox if you want files extracted automatically using the built-in 7-Zip engine.
8. Click the green **Start / Resume** button to begin downloading.
![App Screenshot 3](assets/screenshot3.png)
9. Use the **Pause** and **Start / Resume** buttons to manage your selected downloads at any time.

### Download Scheduler
Queue your links, then let SilverSpoon download them automatically during a chosen window (e.g. off-peak hours):
1. Add and select your links as usual, but leave them **paused/queued** (don't press Start).
2. Open `File -> Download Scheduler` (or right-click one or more downloads and choose **Schedule download at specific interval** to schedule only those instead of the whole queue).
3. Set the **Start** and **End** times using the hour / minute / AM–PM dropdowns. If the end is earlier than the start, the window is treated as crossing midnight (e.g. `11:00 PM`–`5:00 AM`).
4. Choose **Repeat weekly** (and pick the active days) or **Run once** on a specific date.
5. *(Optional, Windows)* Tick **Wake the computer to run downloads** to register a Windows wake timer that powers the PC on and launches SilverSpoon when the window starts. Leave **Keep the computer awake** on so it doesn't sleep mid-download.
6. Click **Add Schedule**. When the window opens, SilverSpoon verifies your connection and starts the scheduled downloads; when it closes, it pauses them and shows a summary (also saved to `~/.silverspoon_offpeak_report.jsonl`).

> **Note:** The wake timer is Windows-only. On Linux/macOS the app still auto-starts and keeps the display awake while it is running, but it cannot power the machine on from a fully off state.
>
> **When using the wake timer, close SilverSpoon (or let the PC sleep) beforehand** so the timer launches a single fresh instance. SilverSpoon does not yet guard against multiple instances, and running two copies against the same queue can corrupt partially-downloaded files.

### Using the CLI
If you prefer the command line:
1. Put your links into `link.txt` (one per line).
2. Run the script:
   ```bash
   python downloader.py link.txt
   ```
*(Files will be downloaded to the current working directory).*

## Fork: Changes from Upstream

This fork (`LordRifqi15/SilverSpoon`) adds the following on top of the original:

### Linux support fixes
* **Chromium discovery on Linux:** The original `find_browsers()` only knew Windows layouts (`playwright-chromium\chrome.exe`, `%LOCALAPPDATA%\ms-playwright`, Program Files Chrome/Edge), so on Linux every download failed with *"Bundled Playwright Chromium was not found"*. It now also scans:
  * `~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome` (current Playwright layout) and `chrome-linux`
  * System browsers on `PATH`: `chromium`, `chromium-browser`, `google-chrome`, `google-chrome-stable`
* **Fragment-free `/go` POST:** The original sent the full task link (including the `#filename` fragment) in the `HX-Current-URL` / `Referer` headers of the direct-link POST, which the host rejected with `403 captcha verification failed` — even though the CAPTCHA itself had solved successfully. The fragment is now stripped before posting.
* **Python 3.14 note:** If you hit `SyntaxError: Non-UTF-8 code starting with '\xb1'` inside `nodriver/cdp/network.py` (nodriver 0.50.3), patch the vendored file: replace the raw `\xb1` byte in the `#: JSON (…)` comment with UTF-8 `±`. This is a venv-level fix, not committed here.

### Direct link sharing
* **Direct Links panel** below the download table: shows every resolved direct link live, one per line — ready to paste into JDownloader2 or any other downloader (links work without cookies).
* **Copy Direct Link** (right-click on a task): shows the resolved link with a copy button; resolves on demand in the background if the task hasn't been downloaded yet.
* **Copy All Direct Links** (panel button + context menu): resolves any missing links in the queue and copies the full list to the clipboard.
* **Parallel CAPTCHA solving:** Direct links are resolved by a pool of 3 independent browser instances (`TurnstileSolverPool`), so resolving a 20-part archive takes seconds instead of a serial ~5 s/link. Each solver is serial internally — nodriver's target bookkeeping is not safe for concurrent tabs inside one browser (crossed tabs → token evaluated on the wrong page → 403), so parallelism comes from separate browsers, one profile per slot (`/tmp/silverspoon_browser_profile_{0..2}`). A wedged slot (rare nodriver listener race) is timed out and retired; the task auto-retries on a live slot.
* **Cleaner shutdown:** `stop()` now awaits the browser shutdown (the original called it without `await`, leaving zombie Chromium processes) and cancels lingering websocket tasks first, avoiding a hang at interpreter exit on Python 3.14.

## Contributing

We welcome contributions! If you'd like to help improve SilverSpoon, please see our [Contributing Guide](CONTRIBUTING.md) for instructions on how to set up your environment, follow our branching strategy (`dev` branch), and submit Pull Requests.

## Changelog

Detailed release notes and history of changes can be found in the [CHANGELOG.md](CHANGELOG.md) file.

## Disclaimer

This tool is provided for educational and automation purposes only. The author is not responsible for the content downloaded using this tool. Please respect the terms of service of the file-hosting providers.
