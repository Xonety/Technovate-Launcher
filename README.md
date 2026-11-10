# Technovate Launcher

Windows launcher source. Target game: Minecraft 1.21.1 / NeoForge 21.1.228.
Distribution archives are downloaded from the configured GitHub Releases.

## Build
GitHub Actions → Build Technovate Launcher → Run workflow. Download artifact `Technovate-Launcher-Windows`.

## Important validation
This first connected build downloads and SHA-256-verifies both release archives before extracting them. It detects a NeoForge version directory and launches it through minecraft-launcher-lib. Test on a clean Windows account before distributing publicly.

Runtime SHA-256: `dbe48f7d41c39705ef5939d8ff44fba9c7e52f22450f5c1d6515b6c733e7238f`
Modpack SHA-256: `21f6f969a75eebc2465754973cd30e2c7f2d6cdf8ae0d3b5d4abe613c04b0355`
