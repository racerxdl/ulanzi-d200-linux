# OBS WebSocket API Reference - obsws-python-1.8.0

## Quick Reference

### Client Initialization

```python
import obsws_python as obs

client = obs.ReqClient(
    host='localhost',      # OBS WebSocket host
    port=4455,             # OBS WebSocket port (default: 4455)
    password='pass',       # Password if WebSocket has auth
    timeout=3              # Connection timeout in seconds
)
```

### Scene Methods

```python
# Get current scene list
scenes = client.get_scene_list()
current_scene = scenes.current_program_scene_name

# Set specific scene
client.set_current_program_scene('Scene Name')

# Example: Toggle between two scenes
def toggle_scene(client, scene1, scene2):
    current = client.get_scene_list().current_program_scene_name
    target = scene2 if current == scene1 else scene1
    client.set_current_program_scene(target)
```

### Source Methods

```python
# Get scene item ID
item = client.get_scene_item_id('Scene Name', 'Source Name')
item_id = item.scene_item_id

# Get source visibility state
state = client.get_scene_item_enabled('Scene Name', item_id)
is_visible = state.scene_item_enabled

# Set source visibility
client.set_scene_item_enabled('Scene Name', item_id, True)

# Example: Toggle source visibility
def toggle_source(client, scene, source):
    item = client.get_scene_item_id(scene, source)
    state = client.get_scene_item_enabled(scene, item.scene_item_id)
    new_state = not state.scene_item_enabled
    client.set_scene_item_enabled(scene, item.scene_item_id, new_state)
```

### Recording Methods

```python
# Get recording status
status = client.get_record_status()
is_recording = status.output_active

# Start recording
client.start_record()

# Stop recording
client.stop_record()

# Example: Toggle recording
def toggle_recording(client):
    status = client.get_record_status()
    if status.output_active:
        client.stop_record()
    else:
        client.start_record()
```

### Streaming Methods

```python
# Get streaming status
status = client.get_stream_status()
is_streaming = status.output_active

# Start streaming
client.start_stream()

# Stop streaming
client.stop_stream()

# Example: Toggle streaming
def toggle_streaming(client):
    status = client.get_stream_status()
    if status.output_active:
        client.stop_stream()
    else:
        client.start_stream()
```

### Other Useful Methods

```python
# Get version info
version = client.get_version()

# Get all scenes
scenes = client.get_scene_list()

# Get sources in a scene
sources = client.get_scene_item_list('Scene Name')

# Get input properties
props = client.get_input_settings('Input Name')

# Set input settings
client.set_input_settings('Input Name', {'setting': 'value'})
```

## Response Objects

All methods return response objects with attributes. Common ones:

```python
# Scene List Response
response = client.get_scene_list()
response.current_program_scene_name  # str
response.scenes                       # list of scenes

# Scene Item Response
response = client.get_scene_item_id(...)
response.scene_item_id               # int

# Scene Item Enabled Response
response = client.get_scene_item_enabled(...)
response.scene_item_enabled          # bool

# Record/Stream Status Response
response = client.get_record_status()
response.output_active               # bool
response.output_paused               # bool (recording only)
```

## Ulanzi D200 Manager Integration

### Configuration Example

```yaml
buttons:
  # Toggle between two OBS scenes
  - image: ./icons/obs.png
    label: Scene Toggle
    action: obs
    params:
      action: toggle_scene
      scene1: "Gaming"
      scene2: "Desktop"

  # Set specific scene
  - image: ./icons/scene.png
    label: Scene 1
    action: obs
    params:
      action: set_scene
      scene: "Gaming"

  # Toggle camera visibility in scene
  - image: ./icons/camera.png
    label: Camera
    action: obs
    params:
      action: toggle_source
      scene: "Gaming"
      source: "Webcam"

  # Toggle recording
  - image: ./icons/record.png
    label: Record
    action: obs
    params:
      action: toggle_recording

  # Toggle streaming
  - image: ./icons/stream.png
    label: Stream
    action: obs
    params:
      action: toggle_streaming
```

### Daemon Integration

The daemon automatically:
1. Creates `obs.ReqClient` with settings from config
2. Connects to OBS WebSocket server
3. Executes OBS actions on button presses
4. Logs all OBS operations

Example config section:
```yaml
obs:
  host: localhost      # OBS WebSocket host
  port: 4455          # OBS WebSocket port
  password: null      # null if no password
```

## Error Handling

```python
try:
    client.set_current_program_scene('Scene Name')
except Exception as e:
    print(f"Error: {e}")
    # Common errors:
    # - Scene doesn't exist
    # - Connection lost
    # - OBS WebSocket disabled
```

## OBS WebSocket Server Setup

1. **Open OBS Studio**
2. Go to **Tools → WebSocket Server Settings**
3. Check **Enable WebSocket Server**
4. Note the port (default: 4455)
5. Set password if desired

## Performance Tips

- Reuse the client connection (don't create new ones)
- Use appropriate timeouts for network conditions
- Handle exceptions for network issues
- Cache scene/source data if querying frequently

## Migration from Old API

| Old Method | New Method |
|-----------|-----------|
| `call('GetCurrentProgramScene')` | `get_scene_list()` |
| `call('SetCurrentProgramScene', {...})` | `set_current_program_scene(name)` |
| `responseData.get('key')` | `response.attribute_name` |
| `obsws(host, port, password)` | `ReqClient(host, port, password)` |
| `.connect()` | (automatic) |

## Common Issues

**Q: "WebSocket connection failed"**
- Is OBS running?
- Is WebSocket Server enabled in OBS?
- Correct host/port?

**Q: "Authentication failed"**
- Is password correct?
- Check OBS WebSocket settings

**Q: "Scene not found"**
- Scene name is case-sensitive
- Verify scene exists in OBS

**Q: "Connection timeout"**
- Check network connection
- Increase timeout parameter
- Check OBS WebSocket is listening

## References

- [obsws-python GitHub](https://github.com/obsproject/obs-websocket-py)
- [OBS WebSocket Protocol](https://github.com/obsproject/obs-websocket)
- [Ulanzi D200 Manager](https://github.com/...)

---

**SDK Version**: obsws-python-1.8.0
**Last Updated**: 2025-01-27
