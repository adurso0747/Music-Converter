# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-25

### Added
- Output to MP3, Opus, AAC (M4A) and Ogg Vorbis, with VBR/CBR modes and custom bitrates.
- Convert any mix of single files and folders; folder structure is recreated in the output.
- Album artwork is copied next to converted tracks, and cover art is embedded in every
  format (including Opus/Ogg), falling back to the folder's cover image.
- Tags are preserved.
- Parallel conversion on a configurable number of threads, with progress, a per-file log
  and cancel support.
- "Skip files already converted" for quick incremental syncs to a phone.
- Optional copying of existing MP3/AAC/Ogg files as-is.
- Settings are remembered between runs.
- Command-line interface (`music-converter-cli`).
- Standalone Windows build with ffmpeg bundled, published on GitHub Releases.
- App icon, test suite, linting and CI.

### Changed
- Restructured the project into the `music_converter` package with a `pyproject.toml`.
- Replaced `tkfilebrowser` with the native folder picker.

### Fixed
- Bitrate mode buttons now switch the quality options.
- The thread count setting is now used.
- Selecting a single file now converts it.
- Error dialogs are no longer shown from worker threads.

[1.0.0]: https://github.com/adurso0747/Music-Converter/releases/tag/v1.0.0
