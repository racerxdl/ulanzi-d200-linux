# How To Create Pages

You can manage multiple profiles like pages or folders in the Window Studio.

## Step 1: Update services

After setting up everything you should create a new service to handle the default startup:

1. Copy service file:
```bash
mkdir -p ~/.config/systemd/user
cp systemd/pages/ulanzi-profile.service ~/.config/systemd/user/
```

2. Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable ulanzi-profile
systemctl --user start ulanzi-profile
```

Then you should update the old service to add dependence and load the `_current` profile instead of `config.yaml`:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/pages/ulanzi-daemon.service ~/.config/systemd/user/
systemctl --user restart ulanzi-daemon
```

## Step 2: Create you page profile

Like your current `config.yaml`.

Remember to add a back button (step 3.2).

## Step 3: Buttons

### 3.1 Go to page:

Just copy new page to `_current.yml` and reload service:

```yaml
action: command
params:
  cmd: "cp -T ~/.config/ulanzi/page.yaml ~/.config/ulanzi/_current.yaml && systemctl --user restart ulanzi-daemon.service"
```

### 3.2 Back to page:

Copy back default config to `_current.yml` and reload service:

```yaml
image: ./icons/back.png
action: command
params:
  cmd: "cp -T ~/.config/ulanzi/config.yaml ~/.config/ulanzi/_current.yaml && systemctl --user restart ulanzi-daemon.service"
```
