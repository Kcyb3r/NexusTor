import requests
import time
import libtorrent as lt
import os
from datetime import datetime
import sys
import urllib.parse
import mimetypes
import tempfile
import hashlib
import json
import concurrent.futures
import asyncio
import aiohttp
import functools
import threading
from pathlib import Path
import logging
from typing import List, Tuple, Optional, Dict, Any
import socket

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TorrentSearchDownloader:
    def __init__(self):
        self.base_url = "https://apibay.org"
        self.download_path = "downloads"
        self.session = None
        self.resume_data_dir = os.path.join(os.path.expanduser("~"), ".torrent_resume")
        self.metadata_cache_dir = os.path.join(os.path.expanduser("~"), ".torrent_metadata")
        self.metadata_cache_ttl = 24 * 60 * 60  # 24 hours in seconds
        
        # Create necessary directories
        for directory in [self.download_path, self.resume_data_dir, self.metadata_cache_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        
        # Initialize libtorrent session with optimal settings
        self.init_session()
        
        # Initialize async session
        self.aiohttp_session = None
        self.loop = None

    async def init_aiohttp_session(self):
        """Initialize aiohttp session for async requests"""
        if self.aiohttp_session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.aiohttp_session = aiohttp.ClientSession(timeout=timeout)
            self.loop = asyncio.get_event_loop()

    async def close_aiohttp_session(self):
        """Close aiohttp session"""
        if self.aiohttp_session:
            await self.aiohttp_session.close()
            self.aiohttp_session = None

    def get_metadata_cache_path(self, info_hash: str) -> str:
        """Get path for cached metadata file"""
        return os.path.join(self.metadata_cache_dir, f"{info_hash}.json")

    def load_cached_metadata(self, info_hash: str) -> Optional[List[Tuple[int, str, int]]]:
        """Load metadata from cache if available and not expired"""
        cache_path = self.get_metadata_cache_path(info_hash)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                
                # Check if cache is expired
                if time.time() - cached_data['timestamp'] <= self.metadata_cache_ttl:
                    return cached_data['media_files']
                else:
                    # Remove expired cache
                    os.remove(cache_path)
            except Exception as e:
                logger.warning(f"Failed to load cached metadata: {e}")
        return None

    def save_metadata_cache(self, info_hash: str, media_files: List[Tuple[int, str, int]]):
        """Save metadata to cache"""
        cache_path = self.get_metadata_cache_path(info_hash)
        try:
            cache_data = {
                'timestamp': time.time(),
                'media_files': media_files
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f)
        except Exception as e:
            logger.warning(f"Failed to save metadata cache: {e}")

    async def fetch_metadata_from_web(self, info_hash: str, session: aiohttp.ClientSession) -> Optional[List[Tuple[int, str, int]]]:
        """Fetch metadata from web sources asynchronously"""
        apis = [
            f"https://itorrents.org/torrent/{info_hash.upper()}.torrent",
            f"https://torrage.info/torrent.php?h={info_hash.lower()}",
            f"https://btcache.me/torrent/{info_hash.lower()}",
            f"https://thetorrent.org/torrent/{info_hash.lower()}.torrent",
            f"https://torrentgalaxy.org/torrent/{info_hash.lower()}",
            f"https://academictorrents.com/download/{info_hash.lower()}.torrent"
        ]
        
        async def try_api(url: str) -> Optional[bytes]:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.read()
            except Exception as e:
                logger.debug(f"Failed to fetch from {url}: {e}")
            return None

        tasks = [try_api(url) for url in apis]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for response in responses:
            if isinstance(response, bytes):
                try:
                    # Save torrent file temporarily
                    temp_file = os.path.join(tempfile.gettempdir(), f"{info_hash}.torrent")
                    with open(temp_file, 'wb') as f:
                        f.write(response)
                    
                    # Parse torrent file
                    info = lt.torrent_info(temp_file)
                    
                    # Find media files
                    media_files = []
                    for idx, file_info in enumerate(info.files()):
                        if self.is_media_file(file_info.path):
                            media_files.append((idx, file_info.path, file_info.size))
                    
                    # Clean up
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    
                    if media_files:
                        return media_files
                except Exception as e:
                    logger.debug(f"Failed to parse torrent file: {e}")
                    continue
        
        return None

    def get_media_files_info(self, magnet_link: str) -> List[Tuple[int, str, int]]:
        """Get information about media files in the torrent using parallel approach"""
        info_hash = magnet_link.split('btih:')[1].split('&')[0].lower()
        
        # Try cache first
        cached_metadata = self.load_cached_metadata(info_hash)
        if cached_metadata:
            logger.info("Using cached metadata")
            return cached_metadata

        # Create event loop in a separate thread if needed
        if threading.current_thread() is threading.main_thread():
            loop = asyncio.get_event_loop()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def fetch_all_metadata():
            await self.init_aiohttp_session()
            try:
                # Try web sources first
                web_metadata = await self.fetch_metadata_from_web(info_hash, self.aiohttp_session)
                if web_metadata:
                    logger.info("Successfully fetched metadata from web sources")
                    self.save_metadata_cache(info_hash, web_metadata)
                    return web_metadata
            except Exception as e:
                logger.warning(f"Web metadata fetch failed: {e}")

            # Fall back to DHT/tracker method with improved settings
            return await self.fetch_metadata_from_dht(magnet_link, info_hash)

        try:
            media_files = loop.run_until_complete(fetch_all_metadata())
            if media_files:
                self.save_metadata_cache(info_hash, media_files)
                return media_files
            raise Exception("Failed to fetch metadata from all sources")
        finally:
            if self.aiohttp_session:
                loop.run_until_complete(self.close_aiohttp_session())

    async def fetch_metadata_from_dht(self, magnet_link: str, info_hash: str) -> List[Tuple[int, str, int]]:
        """Fetch metadata using DHT/tracker method with improved settings"""
        # Create a temporary session with optimized settings
        temp_session = lt.session()
        
        # Optimize session settings for metadata fetching
        settings = {
            'user_agent': 'libtorrent/2.0.0',
            'announce_to_all_tiers': True,
            'announce_to_all_trackers': True,
            'connection_speed': 3000,
            'peer_connect_timeout': 10,
            'request_timeout': 15,
            'active_downloads': 100,
            'active_limit': 2000,
            'num_want': 5000,
            'download_rate_limit': 0,
            'upload_rate_limit': 0,
            'active_seeds': -1,
            'auto_manage_startup': 5,
            'max_failcount': 1,
            'min_reconnect_time': 1,
            'max_out_request_queue': 10000,
            'request_queue_time': 5,
            'strict_end_game_mode': False,
            'suggest_mode': 1,
            'smooth_connects': False,
            'predictive_piece_announce': True,
            'cache_size': 262144,  # 256MB cache
            'allow_multiple_connections_per_ip': True,
            'enable_incoming_utp': True,
            'enable_outgoing_utp': True,
            'mixed_mode_algorithm': 1,
            'max_queued_disk_bytes': 256 * 1024 * 1024,  # 256MB
            'send_buffer_watermark': 5 * 1024 * 1024,  # 5MB
            'send_buffer_low_watermark': 1 * 1024 * 1024,  # 1MB
            'alert_queue_size': 10000,
            'dht_announce_interval': 30,
            'min_announce_interval': 30,
            'max_concurrent_http_announces': 100,
            'enable_dht': True,
            'enable_lsd': True,
            'enable_upnp': True,
            'enable_natpmp': True
        }
        temp_session.apply_settings(settings)

        # Enable all session extensions
        temp_session.start_dht()
        temp_session.start_lsd()
        temp_session.start_upnp()
        temp_session.start_natpmp()

        # Add all DHT routers
        for router in self.get_dht_routers():
            temp_session.add_dht_router(*router)

        max_retries = 5
        retry_count = 0
        base_timeout = 120  # 2 minutes base timeout
        
        while retry_count < max_retries:
            try:
                # Add magnet link
                params = lt.parse_magnet_uri(magnet_link)
                params.save_path = tempfile.gettempdir()
                handle = temp_session.add_torrent(params)
                handle.set_sequential_download(True)

                logger.info(f"Attempt {retry_count + 1}/{max_retries} - Fetching torrent metadata...")
                
                # Add all trackers immediately
                for tracker in self.get_backup_trackers():
                    try:
                        handle.add_tracker({'url': tracker})
                    except Exception as e:
                        logger.debug(f"Failed to add tracker: {e}")

                # Dynamic timeout based on retry count
                timeout = base_timeout * (1 + retry_count * 0.5)
                start_time = time.time()
                last_status_time = time.time()
                last_downloaded = 0
                last_announce = 0
                last_dht_announce = time.time()
                dht_announce_interval = 5
                
                while not handle.has_metadata():
                    current_time = time.time()
                    status = handle.status()
                    
                    # Check timeout
                    if current_time - start_time > timeout:
                        raise Exception(f"Attempt timeout after {int(timeout)} seconds")
                    
                    # Update status every 0.5 seconds
                    if current_time - last_status_time >= 0.5:
                        peers = status.num_peers
                        seeds = status.num_seeds
                        dht_nodes = status.dht_nodes
                        time_remaining = max(0, timeout - (current_time - start_time))
                        
                        logger.info(f"Peers: {peers} | Seeds: {seeds} | "
                                  f"DHT Nodes: {dht_nodes} | "
                                  f"Time remaining: {int(time_remaining)}s")
                        
                        last_status_time = current_time
                    
                    # More aggressive peer discovery
                    if current_time - last_announce >= 1:
                        handle.force_reannounce()
                        last_announce = current_time
                    
                    # More frequent DHT announces
                    if current_time - last_dht_announce >= dht_announce_interval:
                        logger.info("Performing DHT announce...")
                        handle.force_dht_announce()
                        # Add fresh trackers
                        for tracker in self.get_backup_trackers():
                            try:
                                handle.add_tracker({'url': tracker})
                            except:
                                continue
                        last_dht_announce = current_time
                    
                    # Check if we're making progress
                    if status.total_wanted_done > last_downloaded:
                        # Reset timeout if making progress
                        start_time = current_time
                        last_downloaded = status.total_wanted_done
                    
                    await asyncio.sleep(0.1)

                logger.info("Metadata fetched successfully!")

                # Get torrent info
                torrent_info = handle.get_torrent_info()
                
                # Find media files
                media_files = []
                for idx, file_info in enumerate(torrent_info.files()):
                    if self.is_media_file(file_info.path):
                        media_files.append((idx, file_info.path, file_info.size))

                # Clean up
                temp_session.remove_torrent(handle)
                return media_files

            except Exception as e:
                logger.warning(f"Attempt {retry_count + 1} failed: {str(e)}")
                retry_count += 1
                
                if retry_count < max_retries:
                    wait_time = min(5 * retry_count, 15)
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    await asyncio.sleep(wait_time)
                    try:
                        temp_session.remove_torrent(handle)
                    except:
                        pass
                else:
                    try:
                        temp_session.remove_torrent(handle)
                    except:
                        pass
                    raise Exception("Failed to fetch metadata after multiple attempts")

    def init_session(self):
        """Initialize libtorrent session with optimized settings"""
        self.session = lt.session()
        settings = {
            'user_agent': 'libtorrent/2.0.0',
            'announce_to_all_tiers': True,
            'announce_to_all_trackers': True,
            'connection_speed': 5000,  # Increased for faster connections
            'peer_connect_timeout': 5,  # Reduced for faster failure detection
            'rate_limit_ip_overhead': True,
            'download_rate_limit': 0,
            'upload_rate_limit': 0,
            'active_downloads': -1,
            'active_seeds': -1,
            'active_limit': -1,
            'num_want': 1000,  # Increased peer requests
            'piece_timeout': 20,  # Reduced for faster piece requests
            'request_timeout': 10,  # Reduced for faster request timeouts
            'auto_manage_startup': 10,
            'auto_manage_interval': 5,
            'seed_time_limit': 0,
            'cache_size': 524288,  # Increased to 512MB
            'max_failcount': 1,  # Reduced for faster tracker switching
            'min_reconnect_time': 1,
            'max_out_request_queue': 10000,
            'request_queue_time': 3,
            'strict_end_game_mode': False,
            'smooth_connects': False,
            'alert_queue_size': 10000,
            'checking_mem_usage': 4096,  # Increased to 4GB
            'allow_multiple_connections_per_ip': True,
            'enable_incoming_utp': True,
            'enable_outgoing_utp': True,
            'max_queued_disk_bytes': 256 * 1024 * 1024,  # 256MB
            'send_buffer_watermark': 10 * 1024 * 1024,  # 10MB
            'send_buffer_low_watermark': 2 * 1024 * 1024,  # 2MB
            'alert_mask': lt.alert.category_t.all_categories,
            'enable_dht': True,
            'enable_lsd': True,
            'enable_upnp': True,
            'enable_natpmp': True,
            'max_peerlist_size': 4000,  # Increased peer list size
            'max_paused_peerlist_size': 2000,
            'listen_queue_size': 5000,  # Increased listen queue
            'torrent_connect_boost': 200,  # Boost initial connections
            'seeding_piece_quota': 2000,
            'max_rejects': 10,  # Reduced for faster peer dropping
            'recv_socket_buffer_size': 16 * 1024 * 1024,  # 16MB
            'send_socket_buffer_size': 16 * 1024 * 1024,  # 16MB
            'max_suggest_pieces': 50,
            'dht_announce_interval': 30,  # More frequent DHT announces
            'min_announce_interval': 30,  # More frequent announces
            'max_concurrent_http_announces': 100,
            'urlseed_pipeline_size': 50,  # Increased web seed pipeline
            'urlseed_max_request_bytes': 10 * 1024 * 1024,  # 10MB
            'file_pool_size': 1000  # Increased file pool size
        }
        
        # Filter out any settings that might not be supported
        supported_settings = {}
        try:
            # Create a test session to verify settings
            test_session = lt.session()
            test_settings = test_session.get_settings()
            
            # Only keep settings that exist in the current version
            for key, value in settings.items():
                if key in test_settings:
                    supported_settings[key] = value
                else:
                    logger.warning(f"Skipping unsupported setting: {key}")
            
            # Clean up test session
            del test_session
            
        except Exception as e:
            logger.error(f"Error during settings validation: {e}")
            # Use minimal settings if validation fails
            supported_settings = {
                'user_agent': 'libtorrent/2.0.0',
                'enable_dht': True,
                'enable_lsd': True,
                'enable_upnp': True,
                'enable_natpmp': True,
                'alert_mask': lt.alert.category_t.all_categories
            }
        
        try:
            # Apply the validated settings
            self.session.apply_settings(supported_settings)
        except Exception as e:
            logger.error(f"Failed to apply settings: {e}")
            # Apply bare minimum settings if everything else fails
            self.session.apply_settings({
                'enable_dht': True,
                'alert_mask': lt.alert.category_t.all_categories
            })
        
        # Add common DHT routers and bootstrap nodes
        for router in self.get_dht_routers():
            try:
                self.session.add_dht_router(*router)
            except Exception as e:
                logger.warning(f"Failed to add DHT router {router}: {e}")
        
        try:
            # Enable all session extensions
            self.session.start_dht()
            self.session.start_lsd()
            self.session.start_upnp()
            self.session.start_natpmp()
        except Exception as e:
            logger.error(f"Failed to start session extensions: {e}")
        
        # Set up connection pool
        self.setup_connection_pool()

    def setup_connection_pool(self):
        """Set up a connection pool for better network performance"""
        try:
            # Set default socket timeout
            socket.setdefaulttimeout(10)  # 10 second timeout
            
            # Increase system limits if possible
            try:
                import resource
                # Increase number of file descriptors
                resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))
            except Exception as e:
                logger.warning(f"Failed to increase system limits: {e}")
                
        except Exception as e:
            logger.warning(f"Failed to setup connection pool: {e}")

    def cleanup_session(self):
        """Clean up the session properly"""
        if hasattr(self, 'session') and self.session:
            try:
                # Remove all torrents
                for handle in self.session.get_torrents():
                    self.session.remove_torrent(handle)
                
                # Stop session features
                self.session.stop_dht()
                self.session.stop_lsd()
                self.session.stop_upnp()
                self.session.stop_natpmp()
                
                # Clear the session
                del self.session
                self.session = None
            except Exception as e:
                logger.error(f"Error during session cleanup: {e}")

    def __del__(self):
        """Destructor to ensure proper cleanup"""
        self.cleanup_session()

    def get_dht_routers(self) -> List[Tuple[str, int]]:
        """Get list of DHT routers"""
        return [
            ("router.bittorrent.com", 6881),
            ("router.utorrent.com", 6881),
            ("dht.transmissionbt.com", 6881),
            ("dht.libtorrent.org", 25401),
            ("dht.aelitis.com", 6881),
            ("dht.bootstack.net", 6881),
            ("dht.mininova.org", 6881),
            ("router.bitcomet.com", 6881),
            ("dht.academictorrents.com", 6881),
            ("router.silotis.us", 6881),
            ("dht.dendrite.me", 6881),
            ("dht.libtorrent.org", 25401),
            ("dht.transmissionbt.com", 6881),
            ("router.utorrent.com", 6881),
            ("router.bitcomet.com", 6881),
            ("dht.aelitis.com", 6881)
        ]

    def get_resume_path(self, info_hash):
        """Get path for resume data file"""
        return os.path.join(self.resume_data_dir, f"{info_hash}.fastresume")

    def save_resume_data(self, handle, info_hash):
        """Save resume data for future resume"""
        if handle.is_valid() and handle.has_metadata():
            data = lt.bencode(handle.write_resume_data())
            resume_path = self.get_resume_path(info_hash)
            with open(resume_path, 'wb') as f:
                f.write(data)

    def load_resume_data(self, info_hash):
        """Load resume data if available"""
        resume_path = self.get_resume_path(info_hash)
        if os.path.exists(resume_path):
            with open(resume_path, 'rb') as f:
                return lt.bdecode(f.read())
        return None

    def remove_resume_data(self, info_hash):
        """Remove resume data file"""
        resume_path = self.get_resume_path(info_hash)
        if os.path.exists(resume_path):
            os.remove(resume_path)

    def convert_size(self, size_bytes):
        """Convert size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0

    def get_magnet_link(self, info_hash, name):
        """Generate magnet link from info hash"""
        encoded_name = urllib.parse.quote(name)
        trackers = [
            "udp://tracker.coppersurfer.tk:6969/announce",
            "udp://9.rarbg.to:2920/announce",
            "udp://tracker.opentrackr.org:1337",
            "udp://tracker.internetwarriors.net:1337/announce",
            "udp://tracker.leechers-paradise.org:6969/announce",
            "udp://tracker.pirateparty.gr:6969/announce",
            "udp://tracker.cyberia.is:6969/announce",
            "udp://exodus.desync.com:6969/announce",
            "udp://open.stealth.si:80/announce",
            "udp://tracker.tiny-vps.com:6969/announce",
            "udp://tracker.torrent.eu.org:451/announce",
            "udp://tracker.moeking.me:6969/announce",
            "udp://tracker.dler.org:6969/announce",
            "udp://open.demonii.si:1337/announce",
            "udp://tracker.openbittorrent.com:6969/announce",
            "udp://tracker.altrosky.nl:6969/announce",
            "udp://tracker.bitsearch.to:1337/announce",
            "udp://movies.zsw.ca:6969/announce",
            "udp://tracker.theoks.net:6969/announce",
            "udp://tracker.4.babico.name.tr:3131/announce"
        ]
        
        # Add web seeds and DHT/PEX support
        params = [
            f"xt=urn:btih:{info_hash}",
            f"dn={encoded_name}",
            "xs=http://www.bittorrent.com/downloads/complete/",
            "kt=web",
            "x.pe=1",  # Enable PEX
        ]
        
        # Add trackers
        params.extend(f"tr={urllib.parse.quote(t)}" for t in trackers)
        
        return "magnet:?" + "&".join(params)

    def is_media_file(self, filename):
        """Check if the file is a media file based on its extension"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type and mime_type.startswith(('video/', 'audio/'))

    def format_speed(self, bytes_per_second):
        """Format speed in bytes/second to human readable format"""
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.0f} B/s"
        elif bytes_per_second < 1024*1024:
            return f"{bytes_per_second/1024:.1f} KB/s"
        else:
            return f"{bytes_per_second/(1024*1024):.1f} MB/s"

    def format_time(self, seconds):
        """Format seconds to human readable time"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{minutes:.0f}m {seconds:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"

    def get_backup_trackers(self):
        """Get additional backup trackers for better peer discovery"""
        return [
            "udp://tracker.opentrackr.org:1337/announce",
            "udp://9.rarbg.com:2810/announce",
            "udp://tracker.torrent.eu.org:451/announce",
            "udp://tracker.tiny-vps.com:6969/announce",
            "udp://tracker.pomf.se:80/announce",
            "udp://tracker.moeking.me:6969/announce",
            "udp://tracker.dler.org:6969/announce",
            "udp://retracker.lanta-net.ru:2710/announce",
            "udp://opentor.org:2710/announce",
            "udp://open.stealth.si:80/announce",
            "udp://open.demonii.com:1337/announce",
            "udp://tracker.openbittorrent.com:6969/announce",
            "udp://tracker.coppersurfer.tk:6969/announce",
            "udp://exodus.desync.com:6969/announce",
            "udp://tracker.zer0day.to:1337/announce",
            "udp://tracker.leechers-paradise.org:6969/announce",
            "udp://tracker.internetwarriors.net:1337/announce",
            "udp://eddie4.nl:6969/announce",
            "udp://tracker.mg64.net:6969/announce",
            "udp://open.nyap2p.com:6969/announce",
            "udp://tracker.uw0.xyz:6969/announce",
            "udp://tracker.birkenwald.de:6969/announce",
            "udp://tracker.moeking.me:6969/announce",
            "udp://www.torrent.eu.org:451/announce",
            "udp://tracker.cyberia.is:6969/announce",
            "udp://tracker.army:6969/announce",
            "udp://tracker0.ufibox.com:6969/announce",
            "udp://tracker.zemoj.com:6969/announce",
            "udp://tracker.v6speed.org:6969/announce",
            "udp://tracker.skyts.net:6969/announce"
        ]

    def search_torrents(self, search_term, category="all"):
        """Search for torrents on The Pirate Bay"""
        search_url = f"{self.base_url}/q.php"
        params = {
            "q": search_term
        }
        
        try:
            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()  # Raise exception for bad status codes
            results = response.json()
            
            # Filter out invalid results and sort by seeders
            valid_results = [r for r in results if r['id'] != '0' and r['name'] != '']
            valid_results.sort(key=lambda x: int(x['seeders']), reverse=True)
            return valid_results[:10]  # Return top 10 results
            
        except requests.exceptions.Timeout:
            raise Exception("Search request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Search failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error during search: {str(e)}")

    def create_torrent_handle(self, magnet_link, save_path, file_priorities=None):
        """Create and configure a torrent handle"""
        params = lt.parse_magnet_uri(magnet_link)
        params.save_path = save_path
        
        # Try to load resume data
        resume_data = self.load_resume_data(params.info_hash)
        if resume_data:
            params.resume_data = resume_data
        
        handle = self.session.add_torrent(params)
        
        # Set file priorities if specified
        if file_priorities and handle.has_metadata():
            handle.prioritize_files(file_priorities)
        
        return handle

    def wait_for_metadata(self, handle, timeout=30):
        """Wait for torrent metadata with timeout"""
        start_time = time.time()
        while not handle.has_metadata():
            if time.time() - start_time > timeout:
                raise Exception("Timeout while fetching metadata")
            time.sleep(0.1)

    def stream_torrent(self, magnet_link, file_index=0, progress_callback=None, ready_callback=None, is_gui=False, reuse_handle=None):
        """Stream a specific file from the torrent"""
        try:
            # Use existing handle if provided, otherwise create new one
            if reuse_handle and reuse_handle.is_valid():
                handle = reuse_handle
                print("\nReusing existing download handle")
            else:
                # Create and configure handle
                handle = self.create_torrent_handle(magnet_link, self.download_path)
                
                # Wait for metadata
                print("\nFetching metadata...")
                self.wait_for_metadata(handle)

            # Set sequential download and file priorities
            handle.set_sequential_download(True)
            file_priorities = [0] * handle.get_torrent_info().num_files()
            file_priorities[file_index] = 7  # Maximum priority
            handle.prioritize_files(file_priorities)

            print(f"\nStarting streaming: {handle.name()}")
            downloaded_files = []
            stream_started = False
            initial_buffer_percent = 5.0

            while not handle.is_seed():
                if not handle.is_valid():
                    raise Exception("Download was interrupted")

                s = handle.status()
                
                # Calculate progress
                progress = s.progress * 100
                download_rate = s.download_rate / 1000  # KB/s
                
                # States
                state_str = ['queued', 'checking', 'downloading metadata',
                            'downloading', 'finished', 'seeding', 'allocating']

                # Check if ready to start playback
                if not stream_started and progress >= initial_buffer_percent:
                    stream_started = True
                    if ready_callback:
                        file_path = os.path.join(
                            self.download_path,
                            handle.get_torrent_info().files().file_path(file_index)
                        )
                        ready_callback(file_path)

                if progress_callback and is_gui:
                    progress_callback(progress, download_rate, state_str[s.state], s.num_peers)
                else:
                    print(f"\rProgress: {progress:.2f}% "
                          f"Speed: {download_rate:.1f} KB/s "
                          f"State: {state_str[s.state]} "
                          f"Peers: {s.num_peers}", end='')
                
                time.sleep(1)

                # Save resume data periodically
                if handle.need_save_resume_data():
                    self.save_resume_data(handle, str(handle.info_hash()))

            print(f"\n\nDownload complete! Files saved in: {self.download_path}")
            print("Downloaded files:")
            for f in handle.get_torrent_info().files():
                if file_priorities[f.index] > 0:
                    file_path = f.path
                    print(f" - {file_path}")
                    downloaded_files.append(file_path)

            # Clean up resume data after successful download
            self.remove_resume_data(str(handle.info_hash()))
            return downloaded_files

        except Exception as e:
            # Clean up on error only if we created a new handle
            if 'handle' in locals() and handle.is_valid() and not reuse_handle:
                self.session.remove_torrent(handle)
            raise Exception(f"Streaming error: {str(e)}")

    def download_torrent(self, magnet_link, progress_callback=None, is_gui=False):
        """Download the selected torrent"""
        try:
            # Create and configure handle
            handle = self.create_torrent_handle(magnet_link, self.download_path)
            
            # Wait for metadata
            print("\nFetching metadata...")
            self.wait_for_metadata(handle)

            print(f"\nStarting download: {handle.name()}")
            downloaded_files = []

            while not handle.is_seed():
                if not handle.is_valid():
                    raise Exception("Download was interrupted")

                s = handle.status()
                
                # Calculate progress
                progress = s.progress * 100
                download_rate = s.download_rate / 1000  # KB/s
                
                # States
                state_str = ['queued', 'checking', 'downloading metadata',
                            'downloading', 'finished', 'seeding', 'allocating']
                
                if progress_callback and is_gui:
                    progress_callback(progress, download_rate, state_str[s.state], s.num_peers)
                else:
                    print(f"\rProgress: {progress:.2f}% "
                          f"Speed: {download_rate:.1f} KB/s "
                          f"State: {state_str[s.state]} "
                          f"Peers: {s.num_peers}", end='')
                
                time.sleep(1)

                # Save resume data periodically
                if handle.need_save_resume_data():
                    self.save_resume_data(handle, str(handle.info_hash()))

            print(f"\n\nDownload complete! Files saved in: {self.download_path}")
            print("Downloaded files:")
            for f in handle.get_torrent_info().files():
                file_path = f.path
                print(f" - {file_path}")
                downloaded_files.append(file_path)

            # Clean up resume data after successful download
            self.remove_resume_data(str(handle.info_hash()))
            return downloaded_files

        except Exception as e:
            # Clean up on error
            if 'handle' in locals() and handle.is_valid():
                self.session.remove_torrent(handle)
            raise Exception(f"Download error: {str(e)}")

def main():
    downloader = TorrentSearchDownloader()
    
    while True:
        print("\n=== The Pirate Bay Torrent Search and Download ===")
        search_term = input("Enter search term (or 'quit' to exit): ")
        
        if search_term.lower() == 'quit':
            break
            
        print("\nSearching for torrents...")
        try:
            results = downloader.search_torrents(search_term)
            
            if not results:
                print("No results found!")
                continue
                
            print("\nSearch Results:")
            print("-" * 100)
            
            for idx, torrent in enumerate(results, 1):
                size = downloader.convert_size(int(torrent['size']))
                date = datetime.fromtimestamp(int(torrent['added'])).strftime('%Y-%m-%d')
                
                print(f"{idx}. {torrent['name']}")
                print(f"   Size: {size} | Seeds: {torrent['seeders']} | Leeches: {torrent['leechers']}")
                print(f"   Uploaded: {date} | Uploader: {torrent['username']}")
                print("-" * 100)
            
            while True:
                choice = input("\nEnter number to download/stream (d/s number) or 'back': ")
                
                if choice.lower() == 'back':
                    break
                
                try:
                    action, num = choice.lower().split()
                    choice_idx = int(num) - 1
                    
                    if 0 <= choice_idx < len(results):
                        selected_torrent = results[choice_idx]
                        print(f"\nSelected: {selected_torrent['name']}")
                        
                        # Generate magnet link
                        magnet_link = downloader.get_magnet_link(
                            selected_torrent['info_hash'],
                            selected_torrent['name']
                        )
                        
                        if action == 'd':
                            # Start download
                            downloader.download_torrent(magnet_link)
                        elif action == 's':
                            # Get media files
                            media_files = downloader.get_media_files_info(magnet_link)
                            if not media_files:
                                print("No media files found in this torrent!")
                                continue
                                
                            print("\nAvailable media files:")
                            for idx, (_, path, size) in enumerate(media_files, 1):
                                size_str = downloader.convert_size(size)
                                print(f"{idx}. {path} ({size_str})")
                                
                            file_choice = int(input("\nEnter file number to stream: ")) - 1
                            if 0 <= file_choice < len(media_files):
                                file_index = media_files[file_choice][0]
                                downloader.stream_torrent(magnet_link, file_index)
                            else:
                                print("Invalid file selection!")
                        break
                    else:
                        print("Invalid selection. Please try again.")
                except (ValueError, IndexError):
                    print("Invalid input. Use format: 'd 1' to download or 's 1' to stream")
                    
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Please try again.")

if __name__ == "__main__":
    main() 