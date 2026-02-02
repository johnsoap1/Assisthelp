# YouTube Cookies Setup

## Why You Need Cookies
YouTube age-restricted videos require browser cookies to bypass age verification. Without cookies, yt-dlp cannot download:
- Age-restricted content (18+)
- Region-blocked videos
- Login-required content
- VEVO videos requiring account

## How to Get Cookies

### Method 1: Browser Extension (Recommended)
1. Install the "Get cookies.txt" browser extension:
   - Chrome: https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhpfphnancnnhhbh
   - Firefox: https://addons.mozilla.org/en-US/firefox/addon/get-cookiestxt-locally/

2. Go to YouTube and log in to your account
3. Visit any YouTube video page
4. Click the extension icon and export cookies as "cookies.txt"
5. Upload this file to: `/root/cookies/cookies.txt` on your server

### Method 2: Manual Export
1. Log into YouTube in your browser
2. Open Developer Tools (F12)
3. Go to Network tab, refresh page
4. Find any request to youtube.com
5. Copy Cookie header value
6. Create cookies.txt in Netscape format

## File Location
Upload your cookies.txt file to:
```
/root/cookies/cookies.txt
```

## Permissions
Make sure the file has correct permissions:
```bash
chmod 600 /root/cookies/cookies.txt
```

## Security Notes
- Cookies contain your login credentials
- Keep the file private and secure
- Update cookies periodically (they expire)
- Don't share your cookies.txt file

## Testing
After setting up cookies, test with an age-restricted video:
```
/song https://www.youtube.com/watch?v=VIDEO_ID
```

## Troubleshooting
If age-restricted videos still don't work:
1. Check if cookies.txt exists in the correct location
2. Ensure cookies are not expired
3. Try logging out and back into YouTube, then re-export
4. Check file permissions

## Alternative: Use YouTube Music API
For public videos only, you can disable cookie requirement by setting cookiefile to None in the code.
