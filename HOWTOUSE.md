# DISCORD-R-T
1. Edit the config file and add your bot token, user id, server id, and your own custom channel name
2. Install the requirements (CMD: pip install -r requirements.txt/ POWERSHELL: python -m pip install -r requirements.txt)
3. Create your custom bot and invite it to your RAT server.
4. Open the python file called "DISCORD RAT SOURCE" and it will start the rat.
Note: The rat will connect itself to your pc to test if the rat works or not.

### C2 Commands
| Command | Description |
|---------|-------------|
| `!help` | Show command reference |
| `!ip` | Get target system info & geolocation |
| `!shell` | Open interactive PowerShell session |
| `!cmd` | Open interactive CMD session |
| `!kill` | Terminate active shell session |
| `!ls` | List directory contents |
| `!cat` | Read file contents |
| `!download` | Upload file from target to Discord |
| `!upload` | Download file from Discord to target |
| `!screenshot` | Capture desktop screenshot |
| `!webcam` | Capture webcam image |
| `!tokens` | Extract Discord authentication tokens |
| `!wifi` | Dump saved WiFi passwords |
| `!wallets` | Search for cryptocurrency wallet files |
| `!persist` | Install registry persistence (HKCU Run) |
| `!bsod` | Trigger Blue Screen of Death (admin) |
| `!encrypt` | AES encrypt files (ransomware simulation) |
| `!build` | Compile payload `.exe` via PyInstaller |

NOTE: When using the "!build" command in the RAT server, you will be encountered with this specific error: "413 Payload Too Large (error code: 40005): Request entity too large". This is because the max default file size for discord is 25MB. If you see this error, do not worry, the payload will appear in your downloads and you will still be able to control the target.


### Payload Features (compiled `.exe`)
- Reverse shell C2 via Discord bot
- File exfiltration & upload
- Screen/webcam capture
- Discord token extraction
- WiFi credential dumping
- Crypto wallet discovery
- Keylogging
- AES file encryption simulation
- Registry persistence
- Self-destruct

### Prerequisites
- Python 3.10+
- Windows (for payload compilation & target functionality)
- Discord Bot Token with Privileged Gateway Intents enabled
