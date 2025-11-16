# SSH Key Pair Management for EC2 Instances

## Overview

The system **automatically creates unique SSH key pairs** for each EC2 instance during deployment. Private keys are returned to the frontend for secure download.

## ⚠️ CRITICAL SECURITY NOTES

1. **Private keys are only returned ONCE** - During the initial deployment response
2. **AWS does not store private keys** - They cannot be retrieved later
3. **Frontend MUST save the private key immediately** - Download as `.pem` file
4. **User responsibility** - Users must store their private keys securely

## How It Works

### 1. Deployment Flow with Key Pairs

```
Frontend (Canvas) → Backend → AWS
     ↓                ↓         ↓
  Deploy         Create Keys  Deploy Stack
     ↓                ↓         ↓
  Response ← Key Pairs ← EC2 Instances
```

### 2. Key Pair Creation (Automatic)

**When**: Before CloudFormation template generation
**For**: Every EC2 instance in the canvas
**Naming**: `{build_id}-{unique_id}-{instance_name}-key`

Example: `build-12345678-abc123-webserver-key`

### 3. API Response Structure

```json
{
  "success": true,
  "stackName": "foundry-stack-12345678",
  "keyPairs": {
    "webserver": {
      "keyName": "build-12345678-abc123-webserver-key",
      "keyMaterial": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----",
      "keyFingerprint": "1f:51:ae:28:bf:89:e9:d8:1f:25:5d:37:2d:7d:b8:ca",
      "keyPairId": "key-0abcdef1234567890",
      "instanceName": "webserver",
      "instanceNodeId": "node-abc-123"
    },
    "database-server": {
      "keyName": "build-12345678-def456-database-server-key",
      "keyMaterial": "-----BEGIN RSA PRIVATE KEY-----\n...",
      ...
    }
  }
}
```

## Frontend Implementation

### 1. Handle Deployment Response

```javascript
// After successful deployment
const response = await fetch("/canvas/deploy", {
  method: "POST",
  body: JSON.stringify({ buildId, canvas, owner_id, region }),
});

const result = await response.json();

if (result.success && result.keyPairs) {
  // CRITICAL: Save private keys immediately
  Object.entries(result.keyPairs).forEach(([instanceName, keyInfo]) => {
    if (keyInfo.keyMaterial) {
      downloadPrivateKey(instanceName, keyInfo.keyMaterial, keyInfo.keyName);
    }
  });
}
```

### 2. Download Private Key as File

```javascript
function downloadPrivateKey(instanceName, privateKey, keyName) {
  // Create blob from private key
  const blob = new Blob([privateKey], { type: "text/plain" });

  // Create download link
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${keyName}.pem`; // Save as .pem file

  // Trigger download
  document.body.appendChild(a);
  a.click();

  // Cleanup
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
```

### 3. Display Modal with Key Information

```javascript
// Show modal with key pair info
showKeyPairModal({
  title: "SSH Keys Created",
  message: "Private keys have been generated. Download and save them securely!",
  keyPairs: result.keyPairs,
  warning: "These keys cannot be retrieved later. Store them safely!",
});
```

### 4. Example Modal UI

```jsx
<Modal open={showKeyModal}>
  <h2>🔑 SSH Key Pairs Created</h2>

  <Alert severity="warning">
    <strong>Important:</strong> Private keys are only shown once. Download and
    save them securely now!
  </Alert>

  <List>
    {Object.entries(keyPairs).map(([instance, keyInfo]) => (
      <ListItem key={instance}>
        <ListItemText
          primary={`${instance} (${keyInfo.keyName})`}
          secondary={`Fingerprint: ${keyInfo.keyFingerprint}`}
        />
        <Button
          variant="contained"
          onClick={() => downloadKey(instance, keyInfo)}
        >
          Download {instance}.pem
        </Button>
      </ListItem>
    ))}
  </List>

  <Alert severity="info">
    <strong>How to use:</strong>
    <code>chmod 400 {keyName}.pem</code>
    <br />
    <code>
      ssh -i {keyName}.pem ubuntu@{ec2_public_ip}
    </code>
  </Alert>
</Modal>
```

## Using SSH Keys to Connect

### 1. Set Correct Permissions (Linux/Mac)

```bash
chmod 400 build-12345678-abc123-webserver-key.pem
```

### 2. Connect to EC2 Instance

```bash
# Get public IP from CloudFormation outputs
ssh -i build-12345678-abc123-webserver-key.pem ubuntu@<EC2_PUBLIC_IP>

# For Amazon Linux
ssh -i build-12345678-abc123-webserver-key.pem ec2-user@<EC2_PUBLIC_IP>
```

### 3. Default Users by AMI

- **Amazon Linux**: `ec2-user`
- **Ubuntu**: `ubuntu`
- **Windows**: Use RDP with `.pem` for password retrieval

## Security Best Practices

### ✅ DO:

- Download private keys immediately after deployment
- Store keys in a secure password manager or encrypted storage
- Set proper file permissions (`chmod 400`) on Linux/Mac
- Use different keys for different environments (dev/staging/prod)
- Rotate keys periodically

### ❌ DON'T:

- Commit private keys to git repositories
- Share private keys via email or messaging
- Store keys in plain text on shared drives
- Reuse the same key across multiple AWS accounts
- Leave keys world-readable

## Key Pair Cleanup

Keys are automatically cleaned up when:

1. CloudFormation stack is deleted
2. Manual cleanup via key pair manager

```python
from CFCreators.key_pair_manager import cleanup_key_pairs_for_stack

# Clean up all keys for a stack
deleted_count = cleanup_key_pairs_for_stack("foundry-stack-12345678", region="us-east-1")
print(f"Deleted {deleted_count} key pairs")
```

## Troubleshooting

### Problem: "Permission denied (publickey)"

**Solution**: Check file permissions and username

```bash
chmod 400 key.pem
ssh -i key.pem ubuntu@<IP>  # Try 'ec2-user' if Ubuntu doesn't work
```

### Problem: Key pair already exists

**Solution**: The system will skip creation and return existing key info (without private key)

### Problem: Lost private key

**Solution**: Cannot be recovered. Options:

1. Create new EC2 instance with new key pair
2. Use AWS Systems Manager Session Manager (no keys needed)
3. Create AMI, launch new instance with new key

## Database Storage

**Private keys are NOT stored in the database** for security reasons.

What IS stored:

- Build ID
- Canvas data
- CloudFormation template
- Deployment metadata

What is NOT stored:

- Private keys (`keyMaterial`)
- Key fingerprints
- Sensitive credentials

## API Endpoints

### Deploy with Key Pair Creation

```
POST /canvas/deploy
{
  "buildId": 12345678,
  "canvas": {...},
  "owner_id": 1,
  "region": "us-east-1"
}

Response includes: keyPairs object with private keys
```

### WebSocket Deployment Tracking

```
WS /canvas/deploy/track/{stack_name}

Does NOT include private keys (security)
```

## Testing

```python
# Test key pair creation
from CFCreators.key_pair_manager import KeyPairManager

manager = KeyPairManager(region='us-east-1')

# Create key pair
key_info = manager.create_key_pair('test-key-pair')
print(f"Key Name: {key_info['keyName']}")
print(f"Private Key: {key_info['keyMaterial'][:50]}...")

# Save to file
with open('test-key.pem', 'w') as f:
    f.write(key_info['keyMaterial'])
```

## Future Enhancements

- [ ] Optional: Let users upload their own public keys
- [ ] Key rotation scheduler
- [ ] Integration with AWS Secrets Manager
- [ ] Support for EC2 Instance Connect
- [ ] Key expiration warnings
