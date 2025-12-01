# Release Guide

This document describes the release process for dictacode components.

## Component Architecture

dictacode uses a monorepo with independently versioned components:

- **dictacode-stt** - Speech-to-Text engine (PyPI + Debian arm64)
- **dictacode-hid** - HID gadget controller (PyPI + Debian armhf)
- **dictacode-core** - Shared configuration (Debian all)

Each component is released independently with its own version number.

## Release Artifacts

### PyPI Packages
- `dictacode-stt` - Python package for STT
- `dictacode-hid` - Python package for HID

### Debian Packages
- `dictacode-stt_X.Y.Z_arm64.deb` - For Raspberry Pi 5
- `dictacode-hid_X.Y.Z_armhf.deb` - For Pi Zero 2W
- `dictacode-core_X.Y.Z_all.deb` - For all devices

### Git Tags
Format: `{component}/v{version}`

Examples:
- `stt/v0.2.12`
- `hid/v0.2.12`
- `core/v0.2.12`

## Release Workflow

### Prerequisites

1. **Clean working directory**
   ```bash
   git status  # Should be clean
   ```

2. **All tests passing**
   ```bash
   cd apps/stt && uv run pytest
   cd apps/hid && uv run pytest
   ```

3. **Updated CHANGELOG.md**
   - Document all changes since last release
   - Follow [Keep a Changelog](https://keepachangelog.com) format

4. **Secrets configured** (for CI/CD)
   - `PYPI_TOKEN` - PyPI API token
   - `TEST_PYPI_TOKEN` - TestPyPI API token

### Manual Release (Local)

Use the `tools/release.sh` orchestration script:

#### Quick Release (Full)
```bash
# Release STT with all artifacts
./tools/release.sh stt --full

# Release all components
./tools/release.sh --all --full
```

#### Controlled Release
```bash
# PyPI only
./tools/release.sh stt --pypi

# Debian package only (local build)
./tools/release.sh stt --deb

# Debian package (remote build on target device)
./tools/release.sh stt --deb --remote

# Git tag only
./tools/release.sh stt --tag
```

#### Version Bumping
```bash
# Bump patch version and release
./tools/release.sh stt --bump patch --full

# Bump minor version
./tools/release.sh stt --bump minor --full

# Bump major version
./tools/release.sh stt --bump major --full
```

#### Testing with TestPyPI
```bash
# Test release to TestPyPI
./tools/release.sh stt --test --dry-run
./tools/release.sh stt --test
```

### Individual Scripts

For fine-grained control, use individual scripts:

#### PyPI Release
```bash
# Release to PyPI
./tools/release-pypi.sh stt

# With version bump
./tools/release-pypi.sh stt --bump patch

# To TestPyPI
./tools/release-pypi.sh stt --test

# Dry run
./tools/release-pypi.sh stt --dry-run
```

#### Debian Package
```bash
# Build locally
./tools/release-deb.sh stt

# Build on target device
./tools/release-deb.sh stt --remote

# Build and deploy
./tools/release-deb.sh stt --deploy

# Dry run
./tools/release-deb.sh stt --dry-run
```

#### Git Tags
```bash
# Create tag
./tools/release-tag.sh stt

# Create and push
./tools/release-tag.sh stt --push

# Tag all components
./tools/release-tag.sh --all --push

# Dry run
./tools/release-tag.sh stt --dry-run
```

### Automated Release (CI/CD)

#### Tag-Triggered Release
Push a tag to trigger automatic release:

```bash
# Bump version in pyproject.toml or DEBIAN/control
# Commit the change
git add apps/stt/pyproject.toml
git commit -m "Bump STT to v0.2.13"

# Create and push tag
./tools/release-tag.sh stt --push
```

GitHub Actions will:
1. Run tests
2. Build and publish to PyPI
3. Build Debian package
4. Create GitHub Release with artifacts

#### Manual Workflow Dispatch
Trigger release via GitHub UI:

1. Go to Actions → Release workflow
2. Click "Run workflow"
3. Select component and options
4. Click "Run workflow"

## Release Checklist

### Pre-Release
- [ ] All tests passing
- [ ] CHANGELOG.md updated
- [ ] Version bumped in pyproject.toml or DEBIAN/control
- [ ] Git working directory clean
- [ ] On correct branch (exploration or main)

### Release
- [ ] Run `./tools/release.sh {component} --full --dry-run` to verify
- [ ] Run `./tools/release.sh {component} --full` for real release
- [ ] Verify PyPI package uploaded
- [ ] Verify Debian package built
- [ ] Verify git tag created and pushed
- [ ] Verify GitHub Release created

### Post-Release
- [ ] Test installation from PyPI: `pip install dictacode-{component}==X.Y.Z`
- [ ] Test Debian package on target device
- [ ] Update roadmap if needed
- [ ] Announce release (if applicable)

## Version Strategy

We use [Semantic Versioning](https://semver.org/):

- **MAJOR** - Breaking changes to API or protocol
- **MINOR** - New features, backwards compatible
- **PATCH** - Bug fixes, backwards compatible

### Current Version Ranges (v0.2.x)
Components within v0.2.x are designed to be compatible:
- `v0.2.8` - Transport Adapter & Multi-HID
- `v0.2.9` - State Machine & Buffering
- `v0.2.10` - Protocol Handshake & Versioning
- `v0.2.11` - Supervisor & Link Health
- `v0.2.12` - Deployment Hygiene & Packaging
- `v0.2.13` - Diagnostics Integration

## Troubleshooting

### "Working directory has uncommitted changes"
Commit or stash changes before releasing.

### "Tests failed"
Fix failing tests before releasing, or use `--skip-tests` (not recommended).

### "Tag already exists"
Tag was already created. Either:
- Delete the tag: `git tag -d stt/v0.2.12 && git push origin :refs/tags/stt/v0.2.12`
- Bump version and create new tag

### PyPI upload fails
- Check PYPI_TOKEN is set correctly
- Verify version doesn't already exist on PyPI
- Check package name is correct in pyproject.toml

### Remote Debian build fails
- Verify SSH access to target device
- Check device has enough disk space
- Verify `ops/packaging/build-deb.sh` exists on device

## Component Configuration

See `components.yaml` for component definitions and artifact mappings.

## More Information

- Architecture plans: `docs/architecture-plan-v*.md`
- Roadmap: `docs/roadmap.md`
- Changelog: `CHANGELOG.md`
