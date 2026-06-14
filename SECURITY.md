# Security Recommendations

## Repository Security

The current git repository may contain sensitive information in its history.

> **Before doing anything else: rotate and revoke every exposed credential.**
> Rewriting or replacing the repository does not protect secrets that were
> already cloned, forked, or seen by CI systems. Treat any secret that ever
> appeared in a commit as compromised and replace it immediately (new API keys,
> new Django SECRET_KEY, new tokens, etc.).

Once credentials are rotated, clean the history using one of the approaches below.

### Option 1 — Create a new repository without history

```bash
mkdir new_repo
cd new_repo

# Copy all files, including hidden ones (dotfiles such as .gitignore, .env.sample)
cp -r /path/to/original/repo/. .

# Remove the old git history
rm -rf .git

# Initialize a fresh repository
git init
git branch -m main          # ensure the branch is named 'main'
git add .
git commit -m "Initial commit"

# Add remote and push
git remote add origin <new-repository-url>
git push -u origin main
```

### Option 2 — Use git-filter-repo to clean history in place

```bash
# Install git-filter-repo
pip install git-filter-repo

# Create patterns.txt — prefix literal strings with "literal:" and
# regex patterns with "regex:" so they are matched correctly.
# Example patterns.txt:
# literal:actualSecretKeyValueHere==>REDACTED
# regex:SECRET_KEY\s*=\s*\S+==>SECRET_KEY=REDACTED
# regex:password\s*=\s*\S+==>password=REDACTED

git-filter-repo --replace-text patterns.txt

# git-filter-repo removes the origin remote as a safety measure.
# Re-add it before pushing.
git remote add origin <repository-url>

# Force-push all branches and tags after rewriting
git push --force --all
git push --force --tags
```

> **Note:** `git-filter-repo` treats each line as a literal replacement
> unless it is prefixed with `regex:`. Generic glob-style patterns such as
> `SECRET_KEY=.*` will not match — use `regex:` for variable-value patterns.

## Going forward — prevent new secrets from entering history

After cleaning the repository, ensure no new secrets are committed:

- Never commit `.env` files — add `.env` to `.gitignore`
- Use a secrets manager or CI secret store to share credentials with team members
- Consider running a pre-commit hook (e.g. `detect-secrets`) to catch credentials before they are committed

## Security Issues Fixed

The following security issues have been addressed in this repository:

1. **XSS Vulnerability in Fake Triage Screen**:
   - Fixed by validating URLs and ensuring only http/https URLs are allowed
   - Added URL validation in both frontend templates and backend views

2. **HMAC Generation for Media URLs**:
   - Fixed by removing all percent-decoding from HMAC generation
   - Token is now bound to the exact URL byte sequence: `path%2Fmore` and `path/more` produce different tokens
   - Prevents reuse of a signed token via a percent-encoded URL variant that could resolve to a different host (e.g. `cdn.example%2F@evil.com` authority mutation)

3. **Rate Limiting for Resource-Intensive Endpoints**:
   - Added rate limiting to the `/proxy/map` endpoint
   - Added caching to reduce server load

## Additional Security Recommendations

1. **Implement Content Security Policy (CSP)** to prevent XSS attacks
2. **Use HTTPS** for all connections
3. **Regularly update dependencies** to patch security vulnerabilities
4. **Implement proper input validation** for all user inputs
5. **Use a secrets management solution** for production environments
