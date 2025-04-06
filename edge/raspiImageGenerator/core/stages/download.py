#!/usr/bin/env python3
"""
Download stage for Raspberry Pi image generator.
"""

import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from core.stages.base import BuildStage
from core.cache_manager import CacheManager

class DownloadStage(BuildStage):
    """
    Build stage for downloading and caching the Raspberry Pi OS image.
    """
    
    async def execute(self) -> bool:
        try:
            self.logger.info("Starting stage: DownloadStage")
            
            # Initialize cache manager with a persistent location
            cache_dir = Path(self.state["config"].get("cache_dir", "/tmp/w4b_image_cache"))
            self.cache_manager = CacheManager(cache_dir)
            
            # Clean cache before starting
            self.cache_manager.clean_cache()
            
            # Get image information
            image_info = self._get_image_info()
            
            # Check if image is already cached
            download_cached, unpacked_cached = self.cache_manager.is_cached(image_info)
            
            download_path = self.cache_manager.get_download_path(image_info)
            extracted_path = download_path.with_suffix("")
            
            # If the extracted image already exists and is valid, use it directly
            if unpacked_cached:
                self.logger.info(f"Using cached extracted image: {extracted_path}")
                self.state["image_path"] = extracted_path
                return True
                
            if download_cached:
                self.logger.info("Using cached downloaded image")
                
                # Verify the cached file is valid
                if download_path.exists() and download_path.stat().st_size > 0:
                    self.logger.info(f"File size: {download_path.stat().st_size / (1024*1024):.1f} MB")
                    
                    # If it's a compressed file, extract it
                    if download_path.suffix.lower() == '.xz':
                        # Check if already extracted
                        if extracted_path.exists() and extracted_path.stat().st_size > 0:
                            self.logger.info(f"Using previously extracted image: {extracted_path}")
                            self.state["image_path"] = extracted_path
                        else:
                            # Not yet extracted, do the extraction
                            self.logger.info("Extracting compressed image")
                            extracted_path = await self._extract_image(download_path)
                            if extracted_path:
                                self.state["image_path"] = extracted_path
                            else:
                                self.logger.error("Failed to extract cached image")
                                return False
                    else:
                        # Already uncompressed
                        self.state["image_path"] = download_path
                else:
                    # Invalid cached file, download again
                    self.logger.warning("Cached file is invalid, downloading again")
                    download_cached = False
            
            if not download_cached:
                # Download the image if not cached
                self.logger.info("Downloading image")
                image_url = self._get_image_url()
                download_path.parent.mkdir(parents=True, exist_ok=True)
                
                if not await self._download_image(image_url, download_path):
                    self.logger.error("Failed to download image")
                    return False
                    
                # Set image path in state
                if download_path.suffix.lower() == '.xz':
                    self.logger.info("Extracting compressed image")
                    extracted_path = await self._extract_image(download_path)
                    if extracted_path:
                        self.state["image_path"] = extracted_path
                    else:
                        self.logger.error("Failed to extract downloaded image")
                        return False
                else:
                    self.state["image_path"] = download_path
                
                # Save metadata
                self.cache_manager.save_metadata(image_info)
            
            self.logger.info(f"Using image: {self.state['image_path']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in download stage: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    def _get_image_info(self) -> Dict[str, Any]:
        """
        Get information about the image for caching purposes.
        
        Returns:
            Dict[str, Any]: Image information
        """
        config = self.state["config"]["base_image"]
        
        return {
            "version": config.get("version", "unknown"),
            "model": config.get("model", "generic"),
            "checksum": config.get("checksum", ""),
            "checksum_type": config.get("checksum_type", "sha256"),
            "url": self._get_image_url(),
            "compressed": config.get("compressed", True)
        }
    
    async def _download_image(self, url: str, target_path: Path, resume: bool = False) -> bool:
        """
        Download an image file from URL to target path with progress tracking and resumption.
        
        Args:
            url: URL to download from
            target_path: Path to save to
            resume: Whether to attempt to resume a partial download
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check available disk space
            free_space = shutil.disk_usage(target_path.parent).free
            min_required = 8 * 1024 * 1024 * 1024  # 8 GB minimum
            
            if free_space < min_required:
                self.logger.error(f"Insufficient disk space: {free_space / (1024**3):.1f} GB available, {min_required / (1024**3):.1f} GB required")
                return False
            
            self.logger.info(f"Downloading image from {url} to {target_path}")
            
            headers = {}
            file_size_exists = 0
            
            # If resuming and file exists with content, set range header
            if resume and target_path.exists() and target_path.stat().st_size > 0:
                file_size_exists = target_path.stat().st_size
                headers['Range'] = f'bytes={file_size_exists}-'
                self.logger.info(f"Resuming download from byte {file_size_exists}")
            
            # Use aiohttp for better async handling
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200 or response.status == 206:  # OK or Partial Content
                        total_size = int(response.headers.get('content-length', 0))
                        
                        if total_size == 0:
                            self.logger.warning("Content length header missing, can't track progress accurately")
                        else:
                            self.logger.info(f"File size: {total_size / (1024*1024):.1f} MB")
                        
                        mode = 'ab' if resume and file_size_exists > 0 else 'wb'
                        with open(target_path, mode) as f:
                            downloaded = file_size_exists
                            chunk_size = 1024 * 1024  # 1MB chunks
                            
                            self.logger.info("Download started, this may take a while...")
                            
                            async for chunk in response.content.iter_chunked(chunk_size):
                                if not chunk:
                                    break
                                    
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                if total_size > 0:
                                    percent = min(100, downloaded * 100 / (file_size_exists + total_size))
                                    self.logger.debug(f"Download progress: {percent:.1f}% ({downloaded / (1024*1024):.1f} MB)")
                        
                        # Verify file size after download
                        if total_size > 0 and target_path.stat().st_size != file_size_exists + total_size:
                            self.logger.warning(f"Downloaded file size mismatch: expected {total_size + file_size_exists} bytes, got {target_path.stat().st_size} bytes")
                        
                        self.logger.info(f"Download completed: {target_path.stat().st_size / (1024*1024):.1f} MB")
                        return True
                    else:
                        self.logger.error(f"Download failed with status code: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Download failed: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return False
    
    async def _verify_file(self, file_path: Path) -> bool:
        """
        Verify if a file exists, has content, and looks valid.
        
        Args:
            file_path: Path to the file to verify
            
        Returns:
            bool: True if file is valid, False otherwise
        """
        try:
            if not file_path.exists():
                self.logger.error(f"File does not exist: {file_path}")
                return False
                
            file_size = file_path.stat().st_size
            if file_size == 0:
                self.logger.error(f"File is empty: {file_path}")
                return False
                
            self.logger.info(f"File size: {file_size / (1024*1024):.1f} MB")
            
            # Check if the file has a valid signature for its type
            if file_path.suffix == '.xz':
                # Check XZ signature (first 6 bytes should be 0xFD, '7', 'z', 'X', 'Z', 0x00)
                with open(file_path, 'rb') as f:
                    header = f.read(6)
                    
                if len(header) < 6 or header[0] != 0xFD or header[1:6] != b'7zXZ\x00':
                    self.logger.error(f"File has invalid XZ header: {file_path}")
                    return False
                    
            # Add additional file type checks as needed
            
            return True
            
        except Exception as e:
            self.logger.error(f"File verification failed: {str(e)}")
            return False
    
    async def _extract_image(self, image_path: Path) -> Optional[Path]:
        """
        Extract a compressed image file.
        
        Args:
            image_path: Path to the compressed image file
            
        Returns:
            Optional[Path]: Path to the extracted image, or None if extraction failed
        """
        try:
            self.logger.info(f"Extracting image at {image_path}")
            
            # Check if the input file exists and has a valid size
            if not image_path.exists():
                self.logger.error(f"Image file not found: {image_path}")
                return None
                
            file_size = image_path.stat().st_size
            if file_size == 0:
                self.logger.error(f"Image file is empty: {image_path}")
                return None
                
            self.logger.info(f"Image file size: {file_size / (1024*1024):.2f} MB")
            
            # Determine output path (removing .xz extension)
            output_path = image_path.with_suffix("")
            
            # If already extracted and valid, return it
            if output_path.exists() and output_path.stat().st_size > 0:
                self.logger.info(f"Using previously extracted image: {output_path}")
                return output_path
                
            # Verify the file is actually an XZ file before attempting extraction
            # XZ files start with the magic bytes 0xFD, '7', 'z', 'X', 'Z', 0x00
            with open(image_path, 'rb') as f:
                magic_bytes = f.read(6)
                
            if len(magic_bytes) < 6 or magic_bytes[0] != 0xFD or magic_bytes[1:6] != b'7zXZ\x00':
                self.logger.error(f"File is not a valid XZ archive: {image_path}")
                return None
            
            # Check available disk space before extraction
            free_space = shutil.disk_usage(output_path.parent).free
            estimated_space = file_size * 5  # Compressed file typically expands significantly
            
            if free_space < estimated_space:
                self.logger.error(f"Insufficient disk space for extraction: {free_space / (1024**3):.1f} GB available, estimated need: {estimated_space / (1024**3):.1f} GB")
                return None
                
            # Extract the file using xz command
            self.logger.info(f"Extracting to {output_path}")
            process = await asyncio.create_subprocess_exec(
                "xz", "-d", "-k", "-f", str(image_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"Failed to extract image: {stderr.decode() if stderr else 'Unknown error'}")
                
                # Fallback method using Python's lzma module
                self.logger.info("Trying alternate extraction method with Python lzma")
                try:
                    import lzma
                    with lzma.open(image_path, "rb") as f_in:
                        with open(output_path, "wb") as f_out:
                            # Copy in chunks to avoid memory issues with large files
                            chunk_size = 1024 * 1024  # 1MB chunks
                            while True:
                                chunk = f_in.read(chunk_size)
                                if not chunk:
                                    break
                                f_out.write(chunk)
                    self.logger.info("Extraction completed with Python lzma")
                except Exception as e:
                    self.logger.error(f"Python lzma extraction also failed: {str(e)}")
                    return None
            
            # Verify extracted file exists and has valid size
            if not output_path.exists():
                self.logger.error(f"Extraction failed: output file not found at {output_path}")
                return None
                
            extracted_size = output_path.stat().st_size
            if extracted_size == 0:
                self.logger.error(f"Extraction failed: output file is empty: {output_path}")
                return None
                
            self.logger.info(f"Extracted image size: {extracted_size / (1024*1024):.2f} MB")
            
            # Basic validation - should contain a boot sector for disk images
            try:
                with open(output_path, 'rb') as f:
                    # Read first 512 bytes (typical boot sector size)
                    boot_sector = f.read(512)
                    # Check for boot sector signature (0x55, 0xAA at offset 510-511)
                    if len(boot_sector) >= 512 and boot_sector[510:512] != b'\x55\xAA':
                        self.logger.warning(f"Extracted file doesn't have a valid boot sector signature")
            except Exception as e:
                self.logger.warning(f"Failed to validate image boot sector: {str(e)}")
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Failed to extract image: {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())
            return None
    
    def _get_image_url(self) -> str:
        """
        Construct the image URL based on the configuration.
        
        Returns:
            str: Image URL.
        """
        base_image_config = self.state["config"]["base_image"]
        version = base_image_config["version"]
        url_template = base_image_config["url_template"]
        
        if "{version}" in url_template:
            return url_template.format(version=version)
        else:
            return f"{url_template}/{version}"
