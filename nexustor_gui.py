import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLineEdit, QPushButton, QTableWidget, 
                            QTableWidgetItem, QProgressBar, QLabel, QHeaderView,
                            QMessageBox, QFileDialog, QComboBox, QStyle)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from datetime import datetime
from nexustor_core import TorrentSearchDownloader
import subprocess
import time
import mimetypes
import signal

class DownloadWorker(QThread):
    progress = pyqtSignal(float, float, str, int)  # progress, speed, state, peers
    finished = pyqtSignal(list)  # list of downloaded files
    error = pyqtSignal(str)

    def __init__(self, magnet_link, save_path):
        super().__init__()
        self.magnet_link = magnet_link
        self.save_path = save_path
        self.downloader = TorrentSearchDownloader()
        self.downloader.download_path = save_path
        self.is_running = True

    def run(self):
        try:
            downloaded_files = self.downloader.download_torrent(
                self.magnet_link, 
                progress_callback=self.progress.emit,
                is_gui=True
            )
            if downloaded_files:
                self.finished.emit(downloaded_files)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

class StreamWorker(QThread):
    progress = pyqtSignal(float, float, str, int)  # progress, speed, state, peers
    ready_to_play = pyqtSignal(str)  # emits file path when ready to play
    error = pyqtSignal(str)
    finished = pyqtSignal(list)

    def __init__(self, magnet_link, save_path, file_index=0, reuse_handle=None):
        super().__init__()
        self.magnet_link = magnet_link
        self.save_path = save_path
        self.file_index = file_index
        self.reuse_handle = reuse_handle  # Existing download handle to reuse
        self.downloader = TorrentSearchDownloader()
        self.downloader.download_path = save_path
        self.is_running = True

    def run(self):
        try:
            downloaded_files = self.downloader.stream_torrent(
                self.magnet_link,
                self.file_index,
                progress_callback=self.progress.emit,
                ready_callback=self.ready_to_play.emit,
                is_gui=True,
                reuse_handle=self.reuse_handle
            )
            if downloaded_files:
                self.finished.emit(downloaded_files)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self.is_running = False

class MediaPlayer:
    def __init__(self):
        self.process = None
        self.devnull = open(os.devnull, 'w')
        # Handle SIGTERM gracefully
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

    def handle_signal(self, signum, frame):
        """Handle termination signals gracefully"""
        self.stop()
        self.devnull.close()

    def play(self, file_path):
        """Play media file using VLC"""
        try:
            if self.process:
                self.stop()
            
            vlc_args = [
                'vlc',
                '--quiet',
                '--no-osd',
                '--no-video-title-show',
                '--no-overlay',
                '--no-qt-privacy-ask',
                '--no-qt-notification',
                '--no-qt-error-dialogs',
                '--no-qt-fs-controller',
                '--no-dbus',
                '--file-caching=5000',
                '--network-caching=5000',
                '--no-qt-system-tray',
                '--play-and-exit',  # Exit VLC when playback ends
                file_path
            ]
            
            self.process = subprocess.Popen(
                vlc_args,
                stdout=self.devnull,
                stderr=self.devnull
            )
            
        except FileNotFoundError:
            QMessageBox.warning(None, 'VLC Not Found', 
                              'Please install VLC media player to stream media files.')
        except Exception as e:
            QMessageBox.critical(None, 'Playback Error', str(e))

    def stop(self):
        """Stop media playback"""
        if self.process:
            try:
                self.process.terminate()
                # Give it 2 seconds to terminate gracefully
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()  # Force kill if it doesn't terminate
                self.process = None
            except Exception:
                pass  # Ignore errors during cleanup

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop()
        try:
            self.devnull.close()
        except Exception:
            pass

class TorrentGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.downloader = TorrentSearchDownloader()
        self.current_results = []
        self.download_thread = None
        self.stream_thread = None
        self.media_player = MediaPlayer()
        self.active_downloads = {}  # Keep track of active downloads by info_hash
        self.initUI()
        
        # Setup auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(1000)  # Update every second

    def initUI(self):
        self.setWindowTitle('Torrent Search & Download')
        self.setMinimumSize(800, 600)
        
        # Set window icon (using system icon)
        self.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Search bar and button
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Enter search term...')
        self.search_input.returnPressed.connect(self.search_torrents)
        
        search_button = QPushButton('Search')
        search_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        search_button.clicked.connect(self.search_torrents)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        layout.addLayout(search_layout)

        # Results table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['Name', 'Size', 'Seeds', 'Leeches', 'Date', 'Uploader'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        # Enable sorting
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)

        # Buttons layout
        button_layout = QHBoxLayout()
        
        # Download button
        download_button = QPushButton('Download')
        download_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        download_button.clicked.connect(self.start_download)
        button_layout.addWidget(download_button)
        
        # Stream button
        stream_button = QPushButton('Stream')
        stream_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        stream_button.clicked.connect(self.start_streaming)
        button_layout.addWidget(stream_button)
        
        layout.addLayout(button_layout)

        # File selection for streaming
        self.file_combo = QComboBox()
        self.file_combo.setVisible(False)
        layout.addWidget(self.file_combo)

        # Progress section
        progress_group = QWidget()
        progress_layout = QVBoxLayout(progress_group)
        
        # Current action label
        self.current_action_label = QLabel('No active download/stream')
        progress_layout.addWidget(self.current_action_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel('')
        progress_layout.addWidget(self.status_label)
        
        layout.addWidget(progress_group)

        self.show()

    def refresh_status(self):
        """Refresh the status of downloads/streams"""
        if self.download_thread and not self.download_thread.isRunning():
            self.download_thread = None
        if self.stream_thread and not self.stream_thread.isRunning():
            self.stream_thread = None

    def search_torrents(self):
        search_term = self.search_input.text().strip()
        if not search_term:
            return

        try:
            self.current_results = self.downloader.search_torrents(search_term)
            self.update_table()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Search failed: {str(e)}')

    def update_table(self):
        self.table.setRowCount(0)
        self.table.setSortingEnabled(False)  # Disable sorting while updating
        
        for torrent in self.current_results:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Name
            name_item = QTableWidgetItem(torrent['name'])
            name_item.setData(Qt.ItemDataRole.UserRole, torrent)  # Store full torrent data
            self.table.setItem(row, 0, name_item)
            
            # Size
            size = self.downloader.convert_size(int(torrent['size']))
            size_item = QTableWidgetItem(size)
            size_item.setData(Qt.ItemDataRole.UserRole, int(torrent['size']))  # For proper sorting
            self.table.setItem(row, 1, size_item)
            
            # Seeds
            seeds_item = QTableWidgetItem(str(torrent['seeders']))
            seeds_item.setData(Qt.ItemDataRole.UserRole, int(torrent['seeders']))
            self.table.setItem(row, 2, seeds_item)
            
            # Leeches
            leeches_item = QTableWidgetItem(str(torrent['leechers']))
            leeches_item.setData(Qt.ItemDataRole.UserRole, int(torrent['leechers']))
            self.table.setItem(row, 3, leeches_item)
            
            # Date
            date = datetime.fromtimestamp(int(torrent['added'])).strftime('%Y-%m-%d')
            date_item = QTableWidgetItem(date)
            date_item.setData(Qt.ItemDataRole.UserRole, int(torrent['added']))
            self.table.setItem(row, 4, date_item)
            
            # Uploader
            self.table.setItem(row, 5, QTableWidgetItem(torrent['username']))
        
        self.table.setSortingEnabled(True)  # Re-enable sorting

    def is_media_file(self, filename):
        """Check if the file is a media file based on its extension"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type and mime_type.startswith(('video/', 'audio/'))

    def get_media_files(self, torrent_info):
        """Get list of media files from torrent"""
        media_files = []
        for idx, file_info in enumerate(torrent_info.files()):
            if self.is_media_file(file_info.path):
                media_files.append((idx, file_info.path, file_info.size))
        return media_files

    def start_streaming(self):
        if self.stream_thread and self.stream_thread.isRunning():
            QMessageBox.warning(self, 'Warning', 'A stream is already in progress')
            return

        selected_row = self.table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, 'Warning', 'Please select a torrent first')
            return

        selected_torrent = self.current_results[selected_row]
        info_hash = selected_torrent['info_hash']

        # Check if this torrent is already being downloaded
        existing_download = self.active_downloads.get(info_hash)
        save_path = None
        reuse_handle = None
        
        if existing_download:
            reply = QMessageBox.question(
                self, 'File Already Downloading',
                'This file is already being downloaded. Would you like to stream from the existing download?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                save_path = existing_download['save_path']
                # Get the handle from the existing download thread
                if hasattr(existing_download['thread'].downloader, 'session'):
                    for handle in existing_download['thread'].downloader.session.get_torrents():
                        if str(handle.info_hash()) == info_hash:
                            reuse_handle = handle
                            break
            else:
                # User wants to download to a different location
                save_path = QFileDialog.getExistingDirectory(self, 'Select Download Location')
                if not save_path:
                    return
        else:
            # Ask for save location
            save_path = QFileDialog.getExistingDirectory(self, 'Select Download Location')
            if not save_path:
                return

        magnet_link = self.downloader.get_magnet_link(
            info_hash,
            selected_torrent['name']
        )

        # Get media files info
        try:
            media_files = self.downloader.get_media_files_info(magnet_link)
            if not media_files:
                QMessageBox.warning(self, 'Warning', 'No media files found in this torrent')
                return

            # Update file selection combo box
            self.file_combo.clear()
            for idx, path, size in media_files:
                size_str = self.downloader.convert_size(size)
                self.file_combo.addItem(f"{path} ({size_str})", idx)
            
            self.file_combo.setVisible(True)
            
            # Ask user to select file if multiple media files
            if len(media_files) > 1:
                reply = QMessageBox.question(
                    self, 'Select File',
                    'Multiple media files found. Please select a file from the dropdown and click OK.',
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    self.file_combo.setVisible(False)
                    return
            
            file_index = self.file_combo.currentData()
            
            # Start streaming thread
            self.stream_thread = StreamWorker(magnet_link, save_path, file_index, reuse_handle)
            self.stream_thread.progress.connect(self.update_progress)
            self.stream_thread.ready_to_play.connect(self.play_media)
            self.stream_thread.error.connect(self.streaming_error)
            self.stream_thread.finished.connect(self.streaming_finished)
            self.stream_thread.start()

            # Update UI
            self.current_action_label.setText(f'Streaming: {selected_torrent["name"]}')
            self.progress_bar.setValue(0)

        except Exception as e:
            self.file_combo.setVisible(False)
            QMessageBox.critical(self, 'Error', f'Failed to start streaming: {str(e)}')

    def play_media(self, file_path):
        """Start playing the media file"""
        self.media_player.play(file_path)

    def streaming_error(self, error_msg):
        self.current_action_label.setText('Streaming Failed!')
        self.status_label.setText('')
        self.progress_bar.setValue(0)
        self.file_combo.setVisible(False)
        QMessageBox.critical(self, 'Error', f'Streaming failed: {error_msg}')

    def streaming_finished(self, files):
        self.current_action_label.setText('Streaming Complete!')
        self.status_label.setText('')
        self.progress_bar.setValue(100)
        self.file_combo.setVisible(False)

    def start_download(self):
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, 'Warning', 'A download is already in progress')
            return

        selected_row = self.table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, 'Warning', 'Please select a torrent first')
            return

        # Ask for save location
        save_path = QFileDialog.getExistingDirectory(self, 'Select Download Location')
        if not save_path:
            return

        selected_torrent = self.current_results[selected_row]
        info_hash = selected_torrent['info_hash']
        magnet_link = self.downloader.get_magnet_link(
            info_hash,
            selected_torrent['name']
        )

        # Start download thread
        self.download_thread = DownloadWorker(magnet_link, save_path)
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.start()

        # Track this download
        self.active_downloads[info_hash] = {
            'thread': self.download_thread,
            'save_path': save_path,
            'name': selected_torrent['name']
        }

        # Update UI
        self.current_action_label.setText(f'Downloading: {selected_torrent["name"]}')
        self.progress_bar.setValue(0)

    def update_progress(self, progress, speed, state, peers):
        self.progress_bar.setValue(int(progress))
        self.status_label.setText(
            f'Speed: {speed:.1f} KB/s | State: {state} | Peers: {peers}'
        )

    def download_finished(self, files):
        # Remove from active downloads
        finished_hash = None
        for info_hash, download in self.active_downloads.items():
            if download['thread'] == self.download_thread:
                finished_hash = info_hash
                break
        
        if finished_hash:
            del self.active_downloads[finished_hash]

        self.current_action_label.setText('Download Complete!')
        self.status_label.setText('')
        self.progress_bar.setValue(100)
        
        msg = 'Downloaded files:\n' + '\n'.join(f'- {f}' for f in files)
        QMessageBox.information(self, 'Download Complete', msg)

    def download_error(self, error_msg):
        # Remove from active downloads on error
        error_hash = None
        for info_hash, download in self.active_downloads.items():
            if download['thread'] == self.download_thread:
                error_hash = info_hash
                break
        
        if error_hash:
            del self.active_downloads[error_hash]

        self.current_action_label.setText('Download Failed!')
        self.status_label.setText('')
        self.progress_bar.setValue(0)
        QMessageBox.critical(self, 'Error', f'Download failed: {error_msg}')

    def closeEvent(self, event):
        if (self.download_thread and self.download_thread.isRunning()) or \
           (self.stream_thread and self.stream_thread.isRunning()):
            reply = QMessageBox.question(
                self, 'Confirm Exit',
                'A download/stream is in progress. Are you sure you want to quit?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.download_thread:
                    self.download_thread.stop()
                    self.download_thread.wait()
                if self.stream_thread:
                    self.stream_thread.stop()
                    self.stream_thread.wait()
                self.media_player.stop()
            else:
                event.ignore()
                return
        event.accept()

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    ex = TorrentGUI()
    sys.exit(app.exec()) 