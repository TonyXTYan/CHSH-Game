
Tried once and worked: 
```bash
gh release list --limit 1000 --json tagName,isPrerelease \
| jq -r '.[] | select(.isPrerelease) | .tagName' \
| while read -r tag; do
  echo "Deleting pre-release and tag: $tag"
  gh release delete -y "$tag"
  git push origin --delete "$tag"
done
```


Probably a better method, try this next time: 
```bash
gh release list --limit 1000 --json tagName,isPrerelease | \
jq -r '.[] | select(.isPrerelease) | .tagName' | while read -r tag; do
  echo "Deleting pre-release and its tag: $tag"
  gh release delete -y --cleanup-tag "$tag"
done
```


or also try delete local tags?
```bash
# Get a list of pre-release tag names
gh release list --limit 1000 --json tagName,isPrerelease | \
jq -r '.[] | select(.isPrerelease) | .tagName' | while read -r tag; do
  echo "Deleting pre-release and its tag (GitHub & local): $tag"
  # Delete release and remote tag
  gh release delete -y --cleanup-tag "$tag"
  # Delete local tag if it exists
  if git rev-parse "$tag" >/dev/null 2>&1; then
    git tag -d "$tag"
  fi
done
``` 