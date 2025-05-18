# Changelog

All notable changes to this project will be documented in this file.  
This project adheres to [Semantic Versioning](https://semver.org/).

---

## [0.2.0] - 2025-05-18

### Changed
- Entire agent logic rewritten using LangGraph framework
- Removed `!chat` command; replaced with implicit message-based interaction
- Added `!join` / `!leave` commands to control channel participation

### Added
- Speaker identity is now tracked per Discord message (`msg.author.display_name`)
- Characters can define one or more `owners` in `personas.yaml`
- AI response behavior now adapts based on speaker/owner relationship


## [0.1.0] - 2025-05-16

### Initial release

- Discord bot with `!chat` and `!char` commands
- Character system and metadata loading from YAML
- Chat agent using Gemini (Google Generative AI)
- Basic `Message` data model
- Minimal orchestrator structure for input, agent, and output flow

---

## [Unreleased]

### Planned
- Scheduler to enable periodic events (e.g. time-based reminders)
- AI voice integration for Discord VC speech synthesis
