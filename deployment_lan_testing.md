# LAN Testing Guide

Use this when the system runs on one office computer and other computers connect through the same network.

## 1. Run the app on host computer

```bash
python run.py
```

or:

```bash
python serve_waitress.py
```

## 2. Find IP address

```bash
ipconfig
```

Example:

```text
10.10.10.62
```

## 3. Open from another computer

```text
http://10.10.10.62:5000
```

## Notes

- Host computer must stay ON
- App must keep running
- Windows Firewall must allow port 5000
- Use static IP or DHCP reservation for stable access
