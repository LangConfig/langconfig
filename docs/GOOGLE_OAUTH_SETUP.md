# Google OAuth Setup Guide

This guide walks you through setting up Google OAuth 2.0 credentials for the Presentation Generator feature, which allows exporting presentations directly to Google Slides.

## Prerequisites

- A Google account
- Access to [Google Cloud Console](https://console.cloud.google.com/)

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top of the page
3. Click "New Project"
4. Enter a project name (e.g., "LangConfig")
5. Click "Create"
6. Wait for the project to be created, then select it

## Step 2: Enable Required APIs

1. In the Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for and enable these APIs:
   - **Google Slides API** - Required for creating presentations
   - **Google Drive API** - Required for file access and sharing

For each API:
1. Click on the API name
2. Click "Enable"

## Step 3: Configure OAuth Consent Screen

Before creating credentials, you must configure the OAuth consent screen:

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** user type (unless you have a Google Workspace organization)
3. Click "Create"

### Fill in the consent screen details:

**App Information:**
- App name: `LangConfig` (or your preferred name)
- User support email: Your email address
- App logo: (optional)

**App Domain:** (optional for development)
- Leave blank for local development

**Developer contact information:**
- Add your email address

4. Click "Save and Continue"

### Scopes:
1. Click "Add or Remove Scopes"
2. Add these scopes:
   - `https://www.googleapis.com/auth/presentations` - Create and edit Google Slides
   - `https://www.googleapis.com/auth/drive.file` - Access files created by the app
3. Click "Update"
4. Click "Save and Continue"

### Test Users:
1. Click "Add Users"
2. Add your Google email address (and any other test users)
3. Click "Save and Continue"

**Note:** While in "Testing" mode, only test users you add can use the OAuth flow. For production, you'll need to submit for verification.

## Step 4: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click "Create Credentials" > "OAuth client ID"
3. Select **Web application** as the application type
4. Configure the following:

**Name:** `LangConfig Web Client` (or your preferred name)

**Authorized JavaScript origins:**
```
http://localhost:1420
http://localhost:8765
```

**Authorized redirect URIs:**
```
http://localhost:8765/api/auth/google/callback
```

5. Click "Create"

## Step 5: Save Your Credentials

After creating the OAuth client, you'll see:
- **Client ID** - looks like: `123456789-abcdefg.apps.googleusercontent.com`
- **Client Secret** - looks like: `GOCSPX-xxxxxxxxxxxxx`

Copy these values to your environment files:

### Root `.env` file:
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
```

### Backend `.env` file (`backend/.env`):
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
```

**Important:** Never commit these credentials to version control!

## Step 6: Test the Integration

1. Start the backend server:
   ```bash
   cd backend && python main.py
   ```

2. Start the frontend:
   ```bash
   npm run dev
   ```

3. Navigate to a workflow with results
4. Select artifacts and click "Create Presentation"
5. Choose "Google Slides" as the format
6. Click "Connect Google Account"
7. Complete the OAuth flow in the popup

## Troubleshooting

### "Google hasn't verified this app"

This is normal for development. Click "Advanced" > "Go to [App Name] (unsafe)" to continue. For production apps, you'll need to submit for Google verification.

### "redirect_uri_mismatch" Error

Ensure the redirect URI in your OAuth credentials exactly matches:
```
http://localhost:8765/api/auth/google/callback
```

Check for:
- Trailing slashes
- HTTP vs HTTPS
- Correct port number

### "access_denied" Error

- Make sure your email is added as a test user in the OAuth consent screen
- The app must be in "Testing" status with your email in the test users list

### Token Refresh Issues

OAuth tokens expire after 1 hour. The app automatically refreshes tokens using the refresh token. If you encounter issues:

1. Disconnect Google account in the app
2. Re-authenticate through the OAuth flow

## Production Deployment

For production use:

1. **Update redirect URIs** in Google Cloud Console to your production domain:
   ```
   https://your-domain.com/api/auth/google/callback
   ```

2. **Submit for verification** if you want users outside your test list to use the app

3. **Use HTTPS** - Google requires HTTPS for production OAuth

4. **Secure your credentials** - Use environment variables or a secrets manager

## Security Notes

- OAuth tokens are encrypted at rest using Fernet encryption
- The encryption key is auto-generated and stored in `backend/encryption.key`
- Never share or commit the encryption key
- Tokens can be revoked via the "Disconnect" button in the app
