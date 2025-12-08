# OLT Manager - Secure LUKS Installation

## Overview

This installation method creates a fully encrypted system where:
- Customer can ONLY access the web interface
- Customer CANNOT access Ubuntu/SSH
- Customer CANNOT reset password via USB boot
- ONLY YOU can unlock the server after reboot

## How It Works

1. **Fresh Ubuntu Install** with LUKS encryption during OS installation
2. **Dropbear SSH** installed in initramfs for remote LUKS unlock
3. **All user access disabled** after OLT Manager installation
4. **Your SSH key** is the only way to unlock and access

## Installation Process

### Step 1: Install Ubuntu with LUKS (Customer or You)

During Ubuntu installation:
1. Choose "Erase disk and install Ubuntu"
2. Click "Advanced Features"
3. Select "Use LVM with encryption"
4. Set LUKS password (you keep this secret!)

### Step 2: After Ubuntu boots, run secure install

```bash
# As root on fresh Ubuntu with LUKS
curl -fsSL http://YOUR-SERVER/secure-install.sh | bash
```

Or copy the package and run:
```bash
tar -xzf olt-manager-secure.tar.gz
sudo ./secure-install.sh
```

### Step 3: After reboot

The server will wait at LUKS prompt. You unlock it via:
```bash
ssh -i your-key -p 2222 root@customer-server-ip
# Enter LUKS password when prompted
```

## Files

- `secure-install.sh` - Main installation script
- `setup-dropbear.sh` - Configures Dropbear for remote unlock
- `lockdown.sh` - Disables all customer access

## Your Secret Access

- **LUKS Password**: Only you know this
- **SSH Key**: Only you have the private key
- **Support Port**: SSH on port 2222 (hidden from customer)

## Customer Experience

1. Customer receives server with web interface URL
2. Customer uses OLT Manager normally via browser
3. If server reboots, customer contacts you
4. You remotely unlock the server
5. Customer continues using web interface

## Security Level

| Attack | Protected? |
|--------|-----------|
| Boot from USB | YES - disk encrypted |
| Physical disk access | YES - encrypted |
| SSH brute force | YES - disabled |
| Console login | YES - disabled |
| Password reset tricks | YES - encrypted |
