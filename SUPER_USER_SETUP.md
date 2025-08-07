# Super User Setup Guide

## Overview

The Speed Dating Application includes a secure one-time super user registration system that allows you to create the first administrator account when the application is first deployed.

## How It Works

### 1. First Startup
When you start the application for the first time, it will automatically generate a unique secret key and display it in the console output:

```
============================================================
🔑 SUPER USER SECRET GENERATED
============================================================
Secret Key: N2TbRBjtyXoDQP0JjVQabc123...

⚠️  IMPORTANT SECURITY NOTICE:
• This key will only be shown ONCE
• Save it securely - you'll need it to create the first admin account
• The secret file is stored with restricted permissions
• This registration will be disabled after the first super user is created
• Access the super user registration at: /setup/super-user
============================================================
```

### 2. Super User Registration
1. **Save the Secret Key**: Copy and save the secret key immediately - it will not be shown again
2. **Access Setup Page**: Navigate to `/setup/super-user` in your browser
3. **Fill the Form**: 
   - Enter the secret key
   - Provide admin email and strong password
   - Enter your name and display name
4. **Create Account**: Click "Create Super User Account"

### 3. After Registration
- The super user setup page becomes permanently unavailable
- The secret key file is automatically deleted
- You can log in with your new admin account at `/auth/login`
- Access the admin dashboard at `/admin/dashboard`

## Security Features

### 🔐 Secure Secret Generation
- Uses cryptographically secure random number generation
- Secret key is 32 bytes (256 bits) of entropy
- Stored as SHA-256 hash (not plain text)

### 🛡️ File Security
- Secret key file has 600 permissions (owner read/write only)
- File is automatically deleted after successful registration
- Uses constant-time comparison to prevent timing attacks

### 🚫 One-Time Use
- Only works when no super user exists in the database
- Form becomes completely unavailable after first registration
- Secret key cannot be reused or regenerated

### ⚡ Automatic Cleanup
- Secret key file is deleted immediately after successful registration
- No trace of the secret remains on the system
- Setup endpoint returns 404 after registration

## API Endpoints

### GET `/setup/super-user/status`
Check if super user setup is available:
```json
{
  "setup_available": true,
  "super_user_exists": false,
  "secret_key_exists": true,
  "message": "Super user setup is available."
}
```

### GET `/setup/super-user`
Display the registration form (HTML page) - only available when setup is possible.

### POST `/setup/super-user`
Create the super user account:
```json
{
  "secret_key": "your-secret-key-here",
  "email": "admin@example.com",
  "password": "secure-password",
  "first_name": "John",
  "last_name": "Doe",
  "display_name": "Administrator"
}
```

## Troubleshooting

### Secret Key Lost
If you lose the secret key:
1. Stop the application
2. Delete the `.super_user_secret` file
3. Restart the application
4. A new secret key will be generated and displayed

### Setup Not Available
If the setup page shows 404:
- A super user already exists in the database
- The secret key file doesn't exist
- Check application logs for details

### Permission Errors
If you get permission errors:
- Ensure the application has write access to its directory
- Check file permissions on `.super_user_secret`
- Run with appropriate user privileges

## Development/Testing

For development or testing, you can manually create super user accounts using the included test scripts:

```bash
python3 test_simple_super_user.py
```

This validates the secret key generation and verification functionality.

## Security Best Practices

1. **Save the Secret Key Immediately**: It's only shown once
2. **Use Strong Passwords**: Admin accounts have full system access
3. **Secure the Server**: Ensure your deployment environment is secure
4. **Monitor Access**: Keep logs of admin access and actions
5. **Regular Updates**: Keep the application and dependencies updated

## File Locations

- **Secret Key File**: `.super_user_secret` (in application root)
- **Setup Template**: `app/templates/setup/super_user.html`
- **API Endpoints**: `app/api/super_user.py`
- **Security Logic**: `app/security/super_user.py`