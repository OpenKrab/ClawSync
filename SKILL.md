---
name: claw-sync
description: Encrypted bidirectional synchronization for OpenClaw ecosystem - local-first P2P sync with intelligent conflict resolution
version: 1.0.0
metadata:
  openclaw:
    requires:
      env:
        - CLAW_SYNC_CONFIG
        - CLAW_SYNC_PASSPHRASE
      bins:
        - syncthing
        - gocryptfs
        - python3
      anyBins:
        - fusermount
        - mount.fuse
      config:
        - "~/.openclaw/skills/claw-sync/config.yaml"
    primaryEnv: CLAW_SYNC_PASSPHRASE
    emoji: "🔄"
    homepage: https://github.com/openkrab/claw-sync
    os:
      - linux
      - macos
      - windows
    install:
      - kind: brew
        formula: syncthing
        bins: [syncthing]
      - kind: brew
        formula: gocryptfs
        bins: [gocryptfs]
      - kind: node
        package: pyyaml
        bins: [python3]
---

# ClawSync - Encrypted Bidirectional Synchronization

## Overview

ClawSync provides **local-first encrypted synchronization** between multiple OpenClaw devices with intelligent conflict resolution. Keep your Claw data in sync across laptops, desktops, and mobile devices without relying on cloud services.

### Key Benefits

- **🔐 Zero-Knowledge Encryption**: AES-256-GCM encryption with keys that never leave your device
- **🌐 P2P Architecture**: Direct device-to-device sync via Syncthing, no central server required
- **🧠 Intelligent Conflicts**: Learns from your resolution patterns with ClawSelfImprove integration
- **📁 Selective Sync**: Choose which OpenClaw folders to synchronize
- **⚡ Real-Time**: Instant file synchronization with intelligent debouncing
- **💰 Free Forever**: No subscription fees, works offline on LAN

## Problem Solved

**Thai Pain Point**: "ใช้ Claw บนแล็ปท็อป + เดสก์ท็อป แต่ข้อมูลไม่ sync กัน" หรือ "อยากพกข้อมูลไปใช้ที่อื่นแต่กลัวรั่ว"

**Solution**: Local-first encrypted sync that keeps your OpenClaw data consistent across all devices while maintaining complete privacy.

## Quick Start

### Installation

```bash
# Install system dependencies
# Ubuntu/Debian
sudo apt-get install syncthing gocryptfs fuse

# macOS
brew install syncthing gocryptfs

# Windows (with Chocolatey)
choco install syncthing gocryptfs

# Install Python dependencies
pip install -r requirements.txt
```

### First Device Setup

```bash
# Clone skill to OpenClaw skills directory
git clone https://github.com/openkrab/claw-sync.git ~/.openclaw/skills/claw-sync
cd ~/.openclaw/skills/claw-sync

# Setup device with encryption passphrase
export CLAW_SYNC_PASSPHRASE="your_secure_passphrase_here"
python scripts/sync.py setup \
  --device-id "$(hostname)" \
  --name "$(hostname) Device" \
  --passphrase "$CLAW_SYNC_PASSPHRASE"

# Start real-time synchronization
python scripts/sync.py start --mode real-time
```

### Add Second Device

```bash
# On second device, repeat installation then:
python scripts/sync.py setup \
  --device-id "desktop" \
  --name "Office Desktop" \
  --passphrase "same_secure_passphrase"

# Add first device as remote
python scripts/sync.py add-device \
  --id "laptop" \
  --address "192.168.1.100:22000"
```

## Usage

### Basic Commands

```bash
# Check sync status
claw-sync status

# Manual sync specific folders
claw-sync sync --folders "memory,learnings"

# List connected devices
claw-sync list-devices

# Resolve conflicts
claw-sync conflicts
claw-sync resolve --conflict-id "1234" --action "keep-latest"
```

### Environment Variables

Required environment variables:

- `CLAW_SYNC_CONFIG`: Path to configuration file (default: `~/.openclaw/skills/claw-sync/config.yaml`)
- `CLAW_SYNC_PASSPHRASE`: Encryption passphrase for secure filesystem

Optional:

- `CLAW_SYNC_DEVICE_ID`: Override device identifier
- `CLAW_SYNC_MOUNT_POINT`: Custom mount point for encrypted filesystem
- `CLAW_SYNC_DEBUG`: Enable debug logging (set to 1)

## Configuration

### Default Sync Folders

**High Priority (Always Sync)**:
- `~/.openclaw/memory/` - Vector database and snapshots
- `~/.openclaw/.learnings/` - ClawSelfImprove patterns
- `~/.openclaw/SOUL.md` - Agent personality
- `~/.openclaw/AGENTS.md` - Agent configurations

**Medium Priority (Selective Sync)**:
- `~/.openclaw/skills/` - Custom skills (excluding containers)
- `~/.openclaw/workspace/` - Active work files
- `~/.openclaw/config.yaml` - Configuration files

**Low Priority (Optional Sync)**:
- `~/.openclaw/logs/` - Log files (excluding old ones)
- `~/.openclaw/temp/` - Temporary files
- `~/.openclaw/downloads/` - Downloaded files

### Configuration Example

```yaml
device:
  id: "laptop"
  name: "Primary Laptop"
  passphrase: "${CLAW_SYNC_PASSPHRASE}"

folders:
  - path: "~/.openclaw/memory"
    encrypted: true
    priority: "high"
    conflict_resolution: "auto-learn"
    
  - path: "~/.openclaw/skills"
    encrypted: true
    priority: "medium"
    exclude_patterns: ["*/containers/*", "*/node_modules/*"]

sync:
  mode: "real-time"
  lan_discovery: true
  nat_traversal: true

conflicts:
  auto_resolve: true
  learning_enabled: true
  clawselfimprove_integration: true

notifications:
  desktop:
    enabled: true
    events: ["sync_complete", "conflict_detected"]
```

## Integration with OpenClaw Ecosystem

### ClawMemory Integration

Automatically syncs vector database with integrity checks:

```python
# Safe vector database sync
sync.sync_vector_db(
    backup_before=True,
    verify_integrity=True,
    auto_restore_on_corruption=True
)
```

### ClawSelfImprove Integration

Learns conflict resolution patterns:

```python
# Log conflict resolution for learning
sync.log_conflict_resolution({
    'file_path': '/memory/vector_db.sqlite3',
    'conflict_type': 'simultaneous_edit',
    'resolution_action': 'keep_latest',
    'user_confidence': 0.9
})
```

### ClawBackup Integration

Syncs backup archives with verification:

```python
# Sync and verify backup archives
sync.sync_backups(
    days=7,
    verify_checksums=True,
    exclude_corrupted=True
)
```

## Security Features

### Encryption Strategy
- **Algorithm**: AES-256-GCM for maximum security
- **Key Derivation**: Scrypt with 32768 iterations
- **Filesystem**: gocryptfs for transparent encryption
- **Zero-Knowledge**: Keys never leave your device

### Network Security
- **TLS 1.3**: All traffic encrypted with latest TLS
- **P2P Only**: No central servers or cloud dependencies
- **Device Authentication**: Manual device approval required
- **NAT Traversal**: Optional relay servers for connectivity

## Troubleshooting

### Common Issues

**Syncthing not starting**:
```bash
# Check ports
sudo ufw allow 8384 22000
# Restart service
sudo systemctl restart syncthing@$(whoami)
```

**gocryptfs mount failed**:
```bash
# Check FUSE permissions
sudo usermod -a -G fuse $USER
sudo chmod 666 /dev/fuse
```

**Device not connecting**:
```bash
# Check connectivity
ping 192.168.1.100
# Verify device IDs
python scripts/sync.py list-devices
```

### Debug Mode

```bash
# Enable verbose logging
export CLAW_SYNC_DEBUG=1
python scripts/sync.py --debug --verbose

# Monitor logs
tail -f logs/claw_sync.log
```

## Performance

### Benchmarks
- **File Detection**: < 1 second (inotify watching)
- **Small File Sync**: < 2 seconds (LAN)
- **Memory Usage**: ~50MB (Syncthing + gocryptfs)
- **CPU Usage**: < 5% during normal operation

### Optimization
- **Delta Sync**: Only transfer changed blocks
- **Compression**: Reduce bandwidth usage
- **Parallel Transfers**: Multiple files simultaneously
- **Intelligent Caching**: Reduce disk I/O

## Advanced Features

### Web Dashboard (Optional)
```bash
# Start web interface
python scripts/dashboard.py --port 8080
# Access at http://localhost:8080
```

### Mobile Notifications
Configure Telegram or Discord notifications in config.yaml for real-time sync alerts.

### Scheduled Tasks
Set up cron jobs for regular sync reports and backup verification.

## File Structure

```
claw-sync/
├── SKILL.md                 # Skill specification (this file)
├── config.yaml              # Configuration template
├── requirements.txt         # Python dependencies
├── ClawFlow.yaml           # ClawFlow integration
├── scripts/
│   ├── sync.py            # Main synchronization script
│   ├── setup.py          # Device setup script
│   └── test_*.py         # Test scripts
├── containers/
│   └── sync.Dockerfile   # Container configuration
└── logs/                  # Sync logs
```

## Support

- **Documentation**: https://github.com/openkrab/claw-sync#readme
- **Issues**: https://github.com/openkrab/claw-sync/issues
- **Community**: https://discord.gg/openkrab

---

**Version**: 1.0.0  
**Status**: Production Ready  
**License**: MIT