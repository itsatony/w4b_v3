#!/usr/bin/env python3
"""
Unit tests for the W4B Raspberry Pi Image Builder.

These tests validate the core functionality of the image builder,
including downloading, extraction, and modification of disk images.
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.image import ImageBuilder


class TestImageBuilder:
    """Test cases for the ImageBuilder class."""
    
    @pytest.fixture
    async def image_builder(self):
        """Create a test image builder with dummy configuration."""
        # Create a temporary directory for testing
        work_dir = Path(tempfile.mkdtemp())
        
        # Create a dummy config
        config = {
            "hive_id": "test_hive",
            "base_image": {
                "version": "2023-12-05-raspios-bullseye-arm64-lite",
                "url_template": "https://downloads.raspberrypi.org/raspios_lite_arm64/images/raspios_lite_arm64-{version}/2023-12-05-raspios-bullseye-arm64-lite.img.xz",
                "checksum_type": "sha256"
            },
            "output": {
                "directory": str(work_dir),
                "naming_template": "{timestamp}_{hive_id}"
            }
        }
        
        # Create image builder
        builder = ImageBuilder(config, work_dir)
        
        try:
            yield builder
        finally:
            # Clean up
            if work_dir.exists():
                shutil.rmtree(work_dir)

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession.get")
    async def test_verify_checksum(self, mock_get, image_builder):
        """Test checksum verification functionality."""
        # Create a temporary file with known content
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test data")
            tmp_path = Path(tmp.name)
        
        try:
            # Expected SHA256 hash of "test data"
            expected_hash = "916f0027a575074ce72a331777c3478d6513f786a591bd892da1a577bf2335f9"
            
            # Test checksum verification
            result = await image_builder._verify_checksum(tmp_path, expected_hash)
            assert result is True
            
            # Test with invalid checksum
            result = await image_builder._verify_checksum(tmp_path, "invalid_hash")
            assert result is False
            
        finally:
            # Clean up
            if tmp_path.exists():
                tmp_path.unlink()

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_extract_image(self, mock_exec, image_builder):
        """Test image extraction functionality."""
        # Set up mock process
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = asyncio.Future()
        mock_process.communicate.return_value.set_result((b"", b""))
        mock_exec.return_value = asyncio.Future()
        mock_exec.return_value.set_result(mock_process)
        
        # Create a dummy xz file
        with tempfile.NamedTemporaryFile(suffix=".img.xz", delete=False) as tmp:
            tmp.write(b"fake xz data")
            tmp_path = Path(tmp.name)
        
        try:
            # Test extraction
            result = await image_builder.extract_image(tmp_path)
            
            # Verify extraction was attempted
            mock_exec.assert_called_once()
            assert result.suffix == ".img"
            
        finally:
            # Clean up
            if tmp_path.exists():
                tmp_path.unlink()
            if result.exists():
                result.unlink()

    @pytest.mark.asyncio
    @patch("core.image.ImageBuilder.generate_checksum")
    async def test_compress_image(self, mock_checksum, image_builder):
        """Test image compression functionality."""
        # Mock checksum generation
        mock_checksum.return_value = {"sha256": "fake_hash"}
        
        # Create a dummy image file
        with tempfile.NamedTemporaryFile(suffix=".img", delete=False) as tmp:
            tmp.write(b"fake image data" * 1000)  # Make it somewhat large
            tmp_path = Path(tmp.name)
        
        # Patch subprocess execution
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Set up mock process
            mock_process = MagicMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = asyncio.Future()
            mock_process.communicate.return_value.set_result((b"", b""))
            mock_exec.return_value = asyncio.Future()
            mock_exec.return_value.set_result(mock_process)
            
            try:
                # Test compression
                result = await image_builder.compress_image(tmp_path)
                
                # Verify compression was attempted
                mock_exec.assert_called_once()
                assert result.suffix == ".xz"
                
            finally:
                # Clean up
                if tmp_path.exists():
                    tmp_path.unlink()
                if result and result.exists():
                    result.unlink()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
