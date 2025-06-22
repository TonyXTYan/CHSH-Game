#!/usr/bin/env python3
"""
Simple test script to verify the /download endpoint works correctly.
This can be run independently to test the CSV download functionality.
"""

import requests
import logging
import sys
import os
import pytest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.mark.integration
def test_download_endpoint():
    """Test the CSV download endpoint"""
    url = "http://localhost:8080/download"
    
    try:
        logger.info(f"Testing download endpoint: {url}")
        response = requests.get(url, timeout=10)
        
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Content-Type: {response.headers.get('Content-Type', 'Not set')}")
        logger.info(f"Content-Disposition: {response.headers.get('Content-Disposition', 'Not set')}")
        
        if response.status_code == 200:
            logger.info("✅ Download endpoint is working!")
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if 'text/csv' in content_type:
                logger.info("✅ Content-Type is correct (text/csv)")
            else:
                logger.warning("⚠️  Content-Type might not be set correctly")
            
            # Check download headers
            content_disposition = response.headers.get('Content-Disposition', '')
            if 'attachment' in content_disposition:
                logger.info("✅ Download headers are set correctly")
            else:
                logger.warning("⚠️  Download headers might not be set correctly")
            
            # Check if content looks like CSV
            content = response.text
            logger.info(f"\nFirst few lines of CSV content:")
            for i, line in enumerate(content.split('\n')[:5]):
                logger.info(f"  {i+1}: {line}")
            
            # Save content to file for manual inspection
            with open('downloaded_test.csv', 'w') as f:
                f.write(content)
            logger.info(f"\n📁 Content saved to 'downloaded_test.csv' for inspection")
            
        else:
            logger.error(f"❌ Download endpoint returned error: {response.status_code}")
            logger.error(f"Response: {response.text}")
            assert False, f"Download endpoint returned error: {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        logger.error("❌ Could not connect to server. Make sure the server is running on localhost:8080")
        assert False, "Could not connect to server"
    except Exception as e:
        logger.error(f"❌ Error testing download endpoint: {str(e)}")
        assert False, f"Error testing download endpoint: {str(e)}"

def main():
    """Main test runner"""
    logger.info("CHSH Game Download Endpoint Test")
    logger.info("=" * 40)
    
    success = test_download_endpoint()
    
    if success:
        logger.info("\n🎉 All tests passed!")
        return 0
    else:
        logger.error("\n💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
