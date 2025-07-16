# 🌐 NexusTor | Advanced P2P Network Suite

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Build](https://img.shields.io/badge/build-passing-success.svg)

```ascii
 ███▄    █ ▓█████ ▒██   ██▒ █    ██   ██████ ▄▄▄█████▓ ▒█████   ██▀███  
 ██ ▀█   █ ▓█   ▀ ▒▒ █ █ ▒░ ██  ▓██▒▒██    ▒ ▓  ██▒ ▓▒▒██▒  ██▒▓██ ▒ ██▒
▓██  ▀█ ██▒▒███   ░░  █   ░▓██  ▒██░░ ▓██▄   ▒ ▓██░ ▒░▒██░  ██▒▓██ ░▄█ ▒
▓██▒  ▐▌██▒▒▓█  ▄  ░ █ █ ▒ ▓▓█  ░██░  ▒   ██▒░ ▓██▓ ░ ▒██   ██░▒██▀▀█▄  
▒██░   ▓██░░▒████▒▒██▒ ▒██▒▒▒█████▓ ▒██████▒▒  ▒██▒ ░ ░ ████▓▒░░██▓ ▒██▒
░ ▒░   ▒ ▒ ░░ ▒░ ░▒▒ ░ ░▓ ░░▒▓▒ ▒ ▒ ▒ ▒▓▒ ▒ ░  ▒ ░░   ░ ▒░▒░▒░ ░ ▒▓ ░▒▓░
░ ░░   ░ ▒░ ░ ░  ░░░   ░▒ ░░░▒░ ░ ░ ░ ░▒  ░ ░    ░      ░ ▒ ▒░   ░▒ ░ ▒░
   ░   ░ ░    ░    ░    ░   ░░░ ░ ░ ░  ░  ░    ░      ░ ░ ░ ▒    ░░   ░ 
         ░    ░  ░ ░    ░     ░           ░               ░ ░     ░     
```

*A Powerful P2P Network Suite by Kcyb3r*

## 📋 Table of Contents
- [Features](#-features)
- [Installation](#-installation)
- [Usage](#-usage)
- [GUI Interface](#-gui-interface)
- [CLI Interface](#-cli-interface)
- [Advanced Features](#-advanced-features)
- [Performance Optimizations](#-performance-optimizations)
- [Requirements](#-requirements)
- [Contributing](#-contributing)
- [Disclaimer](#-disclaimer)

## 🚀 Features

### Core Functionality
- Dual interface modes (GUI and CLI)
- Advanced torrent search capabilities
- Intelligent metadata fetching system
- Parallel download processing
- Smart resume support
- Adaptive bandwidth management
- Real-time progress tracking

### Search Capabilities
- Multi-source search integration
- Advanced filtering options
- Sort by seeders, size, or date
- Detailed torrent information
- Preview available files

### Download Features
- Selective file downloading
- Bandwidth throttling
- Sequential download mode
- Auto-resume interrupted transfers
- DHT and PEX support
- UDP tracker support

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/torrent-tool.git
cd torrent-tool
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the launcher:
```bash
python3 torrent_launcher.py
```

## 💻 Usage

### Quick Start
1. Launch the application:
```bash
python3 torrent_launcher.py
```

2. Choose your preferred interface:
- Option 1: GUI Interface
- Option 2: CLI Interface
- Option 3: Exit

### GUI Interface
The GUI provides an intuitive interface with:
- Search bar for torrent queries
- Results table with sorting capabilities
- Download progress tracking
- File selection interface
- Bandwidth monitoring
- System tray integration

### CLI Interface
Command-line interface offers:
- Fast search functionality
- Interactive file selection
- Real-time progress bars
- Detailed statistics
- Resource monitoring

## ⚡ Advanced Features

### Metadata Fetching System
- Multi-source parallel fetching
- Web cache integration
- DHT network utilization
- Tracker optimization
- Fallback mechanisms

### Performance Optimizations
- Intelligent caching system
- Connection pooling
- Adaptive buffer sizes
- Smart peer selection
- Resource management

### Network Features
- UDP tracker support
- DHT network integration
- PEX peer exchange
- IPv6 support
- NAT traversal

## 📊 Performance Optimizations

The tool implements several optimizations:
- Parallel metadata fetching
- Connection pooling
- Memory management
- Disk I/O optimization
- Network protocol optimization

## 📋 Requirements

### System Requirements
- Python 3.8 or higher
- 2GB RAM minimum
- 1GB free disk space
- Internet connection

### Python Dependencies
- libtorrent-rasterbar ≥ 2.0.0
- requests ≥ 2.31.0
- aiohttp ≥ 3.9.0
- asyncio ≥ 3.4.3
- PyQt6 (for GUI version)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Users are responsible for complying with local laws and regulations regarding downloading and sharing content. The developers assume no liability for misuse of this software.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔧 Troubleshooting

### Common Issues
1. **Metadata Fetching Timeout**
   - Check internet connection
   - Verify tracker availability
   - Try increasing timeout values

2. **Download Speed Issues**
   - Check bandwidth limits
   - Verify port forwarding
   - Check peer availability

3. **GUI Not Launching**
   - Verify PyQt6 installation
   - Check system resources
   - Verify Python version

### Support
For issues and support:
1. Check the [Issues](https://github.com/yourusername/torrent-tool/issues) page
2. Create a new issue with detailed information
3. Join our community discussions

## 🔄 Updates

Stay updated with the latest features and improvements:
```bash
git pull origin main
pip install -r requirements.txt
```

## 🌟 Acknowledgments

- Thanks to all contributors
- Built with Python and libtorrent
- Special thanks to the open-source community

---
<div align="center">
Made by Kcyb3r...
</div>