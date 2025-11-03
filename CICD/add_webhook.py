import requests

def create_github_webhook(owner, repo, token, webhook_url):
  api_url = f"https://api.github.com/repos/{owner}/{repo}/hooks"
  headers = {
    "Authorization" : f"token {token}",
    "Accept" : "application/vnd.github+json"
  }
  payload = {
    "name" : "web",
    "active" : True,
    "events" : ["push"],
    "config": {
      "url" : webhook_url,
      "content_type" : "json",
      "insecure_ssl" : "0"
    }
  }

  response = requests.post(api_url, json=payload, headers=headers)
  
  if response.status_code in [200,201]:
    print("Webhook created successfully!")
    return True, f"Webhook created successfully for {owner}/{repo}."
  else:
    print(f"Failed to create webhook: {response.status_code} - {response.text}")
    return False, f"Failed to create webhook: {response.status_code} - {response.text}"