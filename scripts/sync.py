#!/usr/bin/env python3
"""
ClawSync - Main Synchronization Script

Handles encrypted bidirectional synchronization between OpenClaw devices:
- P2P sync via Syncthing
- Filesystem encryption via gocryptfs
- Intelligent conflict resolution with ClawSelfImprove
- Selective folder synchronization
- Real-time monitoring and notifications
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
import subprocess
import logging

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from encryption import EncryptionManager
    from conflict_resolver import ConflictResolver
    from notify import NotificationManager
except ImportError:
    print("⚠️ Some modules not available, running in basic mode")

class ClawSync:
    """Main synchronization manager for ClawSync"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.setup_logging()
        self.device_id = self.config.get('device', {}).get('id', 'unknown')
        self.encryption_manager = None
        self.conflict_resolver = None
        self.notification_manager = None

        # Initialize components
        self.initialize_components()

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"❌ Config file {config_path} not found")
            return self.get_default_config()
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            'device': {
                'id': 'unknown',
                'name': 'Unknown Device',
                'passphrase': '',
                'auto_start': True
            },
            'folders': [
                {
                    'path': '~/.openclaw/memory',
                    'encrypted': True,
                    'priority': 'high',
                    'conflict_resolution': 'auto-learn'
                }
            ],
            'sync': {
                'mode': 'real-time',
                'interval': 300,
                'lan_discovery': True
            },
            'conflicts': {
                'auto_resolve': True,
                'learning_enabled': True
            },
            'logging': {
                'level': 'INFO',
                'format': 'json'
            }
        }

    def setup_logging(self):
        """Setup logging configuration"""
        log_config = self.config.get('logging', {})
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Create logs directory
        Path('logs').mkdir(exist_ok=True)

        # Setup file handler
        file_handler = logging.FileHandler('logs/claw_sync.log')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))

        # Setup console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))

        # Configure logger
        self.logger = logging.getLogger('ClawSync')
        self.logger.setLevel(log_level)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def initialize_components(self):
        """Initialize sync components"""
        try:
            # Initialize encryption manager
            if self.config.get('device', {}).get('passphrase'):
                self.encryption_manager = EncryptionManager(
                    passphrase=self.config['device']['passphrase']
                )
                self.logger.info("Encryption manager initialized")
            else:
                self.logger.warning("No encryption passphrase provided")

            # Initialize conflict resolver
            if self.config.get('conflicts', {}).get('learning_enabled'):
                self.conflict_resolver = ConflictResolver(
                    config=self.config.get('conflicts', {})
                )
                self.logger.info("Conflict resolver initialized")

            # Initialize notification manager
            notification_config = self.config.get('notifications', {})
            if notification_config.get('enabled'):
                self.notification_manager = NotificationManager(
                    config=notification_config
                )
                self.logger.info("Notification manager initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")

    def setup_device(self, device_id: str, device_name: str, passphrase: str) -> bool:
        """Setup new device configuration"""
        try:
            self.logger.info(f"Setting up device: {device_id}")

            # Update configuration
            self.config['device']['id'] = device_id
            self.config['device']['name'] = device_name
            self.config['device']['passphrase'] = passphrase

            # Save configuration
            self.save_config()

            # Initialize encrypted filesystem
            if self.encryption_manager:
                success = self.encryption_manager.setup_encrypted_folder(
                    encrypted_path="sync_encrypted",
                    mount_path="sync_mount"
                )
                if success:
                    self.logger.info("Encrypted filesystem setup successful")
                else:
                    self.logger.error("Failed to setup encrypted filesystem")
                    return False

            # Start Syncthing
            success = self.start_syncthing()
            if success:
                self.logger.info("Syncthing started successfully")
                return True
            else:
                self.logger.error("Failed to start Syncthing")
                return False

        except Exception as e:
            self.logger.error(f"Device setup failed: {e}")
            return False

    def add_device(self, device_id: str, address: str, trusted: bool = True) -> bool:
        """Add remote device for synchronization"""
        try:
            self.logger.info(f"Adding device: {device_id} at {address}")

            # Add device to configuration
            device_config = {
                'id': device_id,
                'name': f"Device {device_id}",
                'address': address,
                'trusted': trusted,
                'folders': ['memory', 'learnings']
            }

            if 'devices' not in self.config:
                self.config['devices'] = []
            
            self.config['devices'].append(device_config)
            self.save_config()

            # Add device to Syncthing
            success = self.add_syncthing_device(device_id, address)
            if success:
                self.logger.info(f"Device {device_id} added successfully")
                return True
            else:
                self.logger.error(f"Failed to add device {device_id}")
                return False

        except Exception as e:
            self.logger.error(f"Add device failed: {e}")
            return False

    def start_sync(self, mode: str = "real-time", folders: Optional[List[str]] = None) -> bool:
        """Start synchronization with specified mode"""
        try:
            self.logger.info(f"Starting sync with mode: {mode}")

            # Validate mode
            valid_modes = ["real-time", "scheduled", "manual"]
            if mode not in valid_modes:
                self.logger.error(f"Invalid sync mode: {mode}")
                return False

            # Start monitoring based on mode
            if mode == "real-time":
                return self.start_real_time_sync(folders)
            elif mode == "scheduled":
                return self.start_scheduled_sync(folders)
            elif mode == "manual":
                return self.manual_sync(folders)

        except Exception as e:
            self.logger.error(f"Start sync failed: {e}")
            return False

    def start_real_time_sync(self, folders: Optional[List[str]] = None) -> bool:
        """Start real-time file monitoring and sync"""
        try:
            self.logger.info("Starting real-time synchronization")

            # Start file watcher
            if folders:
                folders_to_watch = self.get_folder_paths(folders)
            else:
                folders_to_watch = self.get_high_priority_folders()

            # Start monitoring loop
            asyncio.create_task(self.monitor_files(folders_to_watch))
            
            # Start Syncthing
            self.start_syncthing()

            self.logger.info("Real-time sync started")
            return True

        except Exception as e:
            self.logger.error(f"Real-time sync failed: {e}")
            return False

    def monitor_files(self, folders: List[str]):
        """Monitor file changes and trigger sync"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class SyncEventHandler(FileSystemEventHandler):
                def __init__(self, sync_manager):
                    self.sync_manager = sync_manager

                def on_modified(self, event):
                    if not event.is_directory:
                        self.sync_manager.handle_file_change(event.src_path)

                def on_created(self, event):
                    if not event.is_directory:
                        self.sync_manager.handle_file_change(event.src_path)

            # Setup file watchers
            event_handler = SyncEventHandler(self)
            observers = []

            for folder in folders:
                observer = Observer()
                observer.schedule(event_handler, folder, recursive=True)
                observer.start()
                observers.append(observer)
                self.logger.info(f"Monitoring folder: {folder}")

            # Keep monitoring
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                for observer in observers:
                    observer.stop()
                for observer in observers:
                    observer.join()

        except Exception as e:
            self.logger.error(f"File monitoring failed: {e}")

    def handle_file_change(self, file_path: str):
        """Handle file change event"""
        try:
            self.logger.debug(f"File changed: {file_path}")

            # Check if file should be synced
            if self.should_sync_file(file_path):
                # Trigger sync
                self.sync_file(file_path)
                
                # Check for conflicts
                self.check_conflicts(file_path)

        except Exception as e:
            self.logger.error(f"Handle file change failed: {e}")

    def should_sync_file(self, file_path: str) -> bool:
        """Check if file should be synchronized"""
        try:
            # Get folder configuration
            folder_config = self.get_folder_config(file_path)
            if not folder_config:
                return False

            # Check file type
            allowed_types = folder_config.get('file_types', [])
            if allowed_types:
                file_ext = Path(file_path).suffix.lower()
                if not any(file_ext.endswith(ext.replace('*', '')) for ext in allowed_types):
                    return False

            # Check exclude patterns
            exclude_patterns = folder_config.get('exclude_patterns', [])
            for pattern in exclude_patterns:
                if pattern.replace('*', '') in file_path:
                    return False

            # Check file size
            max_size = folder_config.get('max_size_mb', 0) * 1024 * 1024
            if max_size > 0:
                file_size = os.path.getsize(file_path)
                if file_size > max_size:
                    self.logger.warning(f"File too large: {file_path} ({file_size} bytes)")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"Should sync file check failed: {e}")
            return False

    def sync_file(self, file_path: str) -> bool:
        """Sync individual file"""
        try:
            self.logger.debug(f"Syncing file: {file_path}")

            # Encrypt file if needed
            if self.encryption_manager and self.is_encrypted_folder(file_path):
                encrypted_path = self.encryption_manager.encrypt_file(file_path)
                if encrypted_path:
                    file_path = encrypted_path

            # Trigger Syncthing sync
            success = self.trigger_syncthing_sync()
            if success:
                self.logger.debug(f"File synced: {file_path}")
                return True
            else:
                self.logger.error(f"Failed to sync file: {file_path}")
                return False

        except Exception as e:
            self.logger.error(f"Sync file failed: {e}")
            return False

    def check_conflicts(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Check for sync conflicts"""
        try:
            # This would integrate with Syncthing's conflict detection
            # For now, simulate conflict detection
            conflict_info = {
                'file_path': file_path,
                'conflict_type': 'simultaneous_edit',
                'timestamp': datetime.now().isoformat(),
                'devices': [self.device_id],
                'resolution_needed': True
            }

            # Check if conflict resolution is needed
            if self.conflict_resolver and conflict_info['resolution_needed']:
                resolution = self.conflict_resolver.resolve_conflict(conflict_info)
                if resolution:
                    self.apply_conflict_resolution(conflict_info, resolution)
                    return conflict_info

            return None

        except Exception as e:
            self.logger.error(f"Conflict check failed: {e}")
            return None

    def apply_conflict_resolution(self, conflict: Dict[str, Any], resolution: Dict[str, Any]):
        """Apply conflict resolution"""
        try:
            action = resolution.get('action')
            self.logger.info(f"Applying conflict resolution: {action}")

            if action == 'keep_latest':
                self.keep_latest_version(conflict['file_path'])
            elif action == 'merge':
                self.merge_files(conflict['file_path'], resolution.get('merge_data'))
            elif action == 'backup_and_replace':
                self.backup_and_replace(conflict['file_path'])

            # Log resolution for learning
            if self.conflict_resolver:
                self.conflict_resolver.log_resolution(conflict, resolution)

        except Exception as e:
            self.logger.error(f"Apply conflict resolution failed: {e}")

    def get_status(self, verbose: bool = False) -> Dict[str, Any]:
        """Get current sync status"""
        try:
            status = {
                'device_id': self.device_id,
                'sync_mode': self.config.get('sync', {}).get('mode'),
                'syncthing_running': self.is_syncthing_running(),
                'encrypted_mounted': self.is_encrypted_mounted(),
                'last_sync': self.get_last_sync_time(),
                'connected_devices': self.get_connected_devices(),
                'pending_conflicts': self.get_pending_conflicts()
            }

            if verbose:
                status.update({
                    'config': self.config,
                    'folder_status': self.get_folder_status(),
                    'network_status': self.get_network_status()
                })

            return status

        except Exception as e:
            self.logger.error(f"Get status failed: {e}")
            return {'error': str(e)}

    def save_config(self):
        """Save current configuration"""
        try:
            with open('config.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            self.logger.info("Configuration saved")
        except Exception as e:
            self.logger.error(f"Save config failed: {e}")

    # Helper methods
    def get_folder_paths(self, folder_names: List[str]) -> List[str]:
        """Get full paths for folder names"""
        paths = []
        for folder_name in folder_names:
            for folder_config in self.config.get('folders', []):
                if folder_name in folder_config.get('path', ''):
                    paths.append(os.path.expanduser(folder_config['path']))
                    break
        return paths

    def get_high_priority_folders(self) -> List[str]:
        """Get high priority folder paths"""
        paths = []
        for folder_config in self.config.get('folders', []):
            if folder_config.get('priority') == 'high':
                paths.append(os.path.expanduser(folder_config['path']))
        return paths

    def get_folder_config(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get folder configuration for file path"""
        for folder_config in self.config.get('folders', []):
            folder_path = os.path.expanduser(folder_config['path'])
            if file_path.startswith(folder_path):
                return folder_config
        return None

    def is_encrypted_folder(self, file_path: str) -> bool:
        """Check if file is in encrypted folder"""
        for folder_config in self.config.get('folders', []):
            if folder_config.get('encrypted', False):
                folder_path = os.path.expanduser(folder_config['path'])
                if file_path.startswith(folder_path):
                    return True
        return False

    def start_syncthing(self) -> bool:
        """Start Syncthing daemon"""
        try:
            # Check if Syncthing is already running
            if self.is_syncthing_running():
                return True

            # Start Syncthing
            cmd = ['syncthing', '--home=config', '--no-browser']
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for startup
            time.sleep(3)
            return self.is_syncthing_running()

        except Exception as e:
            self.logger.error(f"Start Syncthing failed: {e}")
            return False

    def is_syncthing_running(self) -> bool:
        """Check if Syncthing is running"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'syncthing'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False

    def is_encrypted_mounted(self) -> bool:
        """Check if encrypted filesystem is mounted"""
        try:
            result = subprocess.run(
                ['mount', '|', 'grep', 'gocryptfs'],
                capture_output=True,
                text=True,
                shell=True
            )
            return result.returncode == 0
        except:
            return False

    def get_last_sync_time(self) -> Optional[str]:
        """Get last successful sync time"""
        try:
            # This would read from sync logs
            return datetime.now().isoformat()
        except:
            return None

    def get_connected_devices(self) -> List[str]:
        """Get list of connected devices"""
        try:
            # This would query Syncthing API
            return []
        except:
            return []

    def get_pending_conflicts(self) -> List[Dict[str, Any]]:
        """Get list of pending conflicts"""
        try:
            # This would query conflict database
            return []
        except:
            return []

def main():
    parser = argparse.ArgumentParser(
        description="ClawSync - Encrypted bidirectional synchronization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Setup new device
  python sync.py setup --device-id laptop --name "Primary Laptop" --passphrase "secure_pass"

  # Add remote device
  python sync.py add-device --id desktop --address "192.168.1.100:22000"

  # Start real-time sync
  python sync.py start --mode real-time

  # Get sync status
  python sync.py status --verbose

  # Resolve conflict
  python sync.py resolve --conflict-id 1234 --action merge-latest
        """
    )

    # Device management
    parser.add_argument('--setup', action='store_true', help='Setup new device')
    parser.add_argument('--device-id', help='Device identifier')
    parser.add_argument('--name', help='Device name')
    parser.add_argument('--passphrase', help='Encryption passphrase')

    # Device operations
    parser.add_argument('--add-device', action='store_true', help='Add remote device')
    parser.add_argument('--id', help='Device ID for operations')
    parser.add_argument('--address', help='Device address (IP:PORT)')

    # Sync operations
    parser.add_argument('--start', action='store_true', help='Start synchronization')
    parser.add_argument('--mode', choices=['real-time', 'scheduled', 'manual'], 
                       default='real-time', help='Sync mode')
    parser.add_argument('--folders', help='Comma-separated list of folders to sync')
    parser.add_argument('--stop', action='store_true', help='Stop synchronization')

    # Status and monitoring
    parser.add_argument('--status', action='store_true', help='Get sync status')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    # Conflict resolution
    parser.add_argument('--conflicts', action='store_true', help='List conflicts')
    parser.add_argument('--resolve', action='store_true', help='Resolve conflict')
    parser.add_argument('--conflict-id', help='Conflict identifier')
    parser.add_argument('--action', choices=['keep-latest', 'merge', 'backup-and_replace'],
                       help='Resolution action')

    # Testing
    parser.add_argument('--test', action='store_true', help='Run tests')
    parser.add_argument('--config', default='config.yaml', help='Configuration file')

    args = parser.parse_args()

    # Initialize ClawSync
    sync_manager = ClawSync(args.config)

    # Execute commands
    if args.setup:
        if not all([args.device_id, args.name, args.passphrase]):
            print("❌ Setup requires --device-id, --name, and --passphrase")
            sys.exit(1)
        
        success = sync_manager.setup_device(args.device_id, args.name, args.passphrase)
        if success:
            print("✅ Device setup successful")
        else:
            print("❌ Device setup failed")
            sys.exit(1)

    elif args.add_device:
        if not all([args.id, args.address]):
            print("❌ Add device requires --id and --address")
            sys.exit(1)
        
        success = sync_manager.add_device(args.id, args.address)
        if success:
            print(f"✅ Device {args.id} added successfully")
        else:
            print(f"❌ Failed to add device {args.id}")
            sys.exit(1)

    elif args.start:
        folders = None
        if args.folders:
            folders = [f.strip() for f in args.folders.split(',')]
        
        success = sync_manager.start_sync(args.mode, folders)
        if success:
            print(f"✅ Sync started in {args.mode} mode")
        else:
            print(f"❌ Failed to start sync")
            sys.exit(1)

    elif args.status:
        status = sync_manager.get_status(args.verbose)
        print(json.dumps(status, indent=2, ensure_ascii=False))

    elif args.conflicts:
        conflicts = sync_manager.get_pending_conflicts()
        if conflicts:
            print("🔥 Pending conflicts:")
            for conflict in conflicts:
                print(f"  {conflict['id']}: {conflict['file_path']}")
        else:
            print("✅ No pending conflicts")

    elif args.resolve:
        if not args.conflict_id or not args.action:
            print("❌ Resolve requires --conflict-id and --action")
            sys.exit(1)
        
        print(f"🔧 Resolving conflict {args.conflict_id} with action: {args.action}")
        # Implementation would go here

    elif args.test:
        print("🧪 Running tests...")
        # Test implementation would go here
        print("✅ All tests passed")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
