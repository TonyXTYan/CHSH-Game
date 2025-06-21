#!/usr/bin/env python3
"""
Simple test script to verify the new /download endpoint works correctly.
This can be run independently to test the CSV download functionality.
"""

import requests
import sys
import os

def test_download_endpoint():
    """Test the /download endpoint"""
    try:
        # Assume the server is running on localhost:8080
        url = "http://localhost:8080/download"
        
        print(f"Testing download endpoint: {url}")
        response = requests.get(url)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'Not set')}")
        print(f"Content-Disposition: {response.headers.get('Content-Disposition', 'Not set')}")
        
        if response.status_code == 200:
            print("✅ Download endpoint is working!")
            
            # Check if we got CSV content
            if 'text/csv' in response.headers.get('Content-Type', ''):
                print("✅ Content-Type is correct (text/csv)")
            else:
                print("⚠️  Content-Type might not be set correctly")
            
            # Check if download headers are set
            if 'attachment' in response.headers.get('Content-Disposition', ''):
                print("✅ Download headers are set correctly")
            else:
                print("⚠️  Download headers might not be set correctly")
            
            # Show first few lines of content
            content_lines = response.text.split('\n')[:5]
            print(f"\nFirst few lines of CSV content:")
            for i, line in enumerate(content_lines):
                print(f"  {i+1}: {line}")
            
            # Save to file for inspection
            with open('downloaded_test.csv', 'w') as f:
                f.write(response.text)
            print(f"\n📁 Content saved to 'downloaded_test.csv' for inspection")
            
        else:
            print(f"❌ Download endpoint returned error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to server. Make sure the server is running on localhost:8080")
        return False
    except Exception as e:
        print(f"❌ Error testing download endpoint: {str(e)}")
        return False
    
    return response.status_code == 200

if __name__ == "__main__":
    print("CHSH Game Download Endpoint Test")
    print("=" * 40)
    
    success = test_download_endpoint()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)
