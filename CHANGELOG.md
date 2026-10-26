# Changelog

Every release of OddsBreaker is listed here, newest first. The version numbers follow [semantic versioning](https://semver.org).

## [1.1.0] - 2026-10-25

### New

- A start-up show: the closed Pokédex swings open on its hinge, the lights and lens power up, and the screen boots with a loading bar. Click or press any key to skip it. It follows the EFFECTS setting (LITE skips the lid, OFF skips it all).
- OddsBreaker looks for a new version every time it opens and offers the download right away. Pick LATER and it won't ask again for that version.
- A download page at https://tahsan228.github.io/OddsBreaker/

### Changed

- Sound effects play the moment you click. The sounds stay loaded and the sound card stays open, where before every beep opened the sound card first. Buttons click when pressed, like real ones.
- More room everywhere: a slightly bigger device, wider margins on every page, and roomier keys, rows and buttons.
- Every Pokémon now shows at about the same size, so small ones aren't blown up and big ones aren't shrunk.
- The project moved to github.com/Tahsan228/OddsBreaker.

### Fixed

- On the very first start, the moving shiny sprite could fail to download (two downloads tried to create the same folder at once) and stay a still picture until the next start. Failed sprite downloads now try again after two minutes.
- The line at the bottom of the Pokédex screen switches to a shorter wording instead of ending in "...".

## [1.0.0] - 2026-10-18

The first release under the new name. OddsBreaker used to be called ShinyDex, and it offers to bring your old hunts over the first time it starts.

### New

- A redrawn pixel-art Pokédex with rounder buttons, more breathing room, eight shell colours and a 1x to 4x size picker.
- Proper pixel animations: a CRT power-on, block dissolves between screens, a scanner line while it checks, LED chases, a rolling counter with +1 pops, and a full shiny celebration with light rays, a bouncing SHINY! banner, sparkles and a screen shake. Effects can be FULL, LITE or OFF.
- Moving sprites of the Pokémon you're hunting, normal and shiny.
- STATS page with resets per day, the time left to 50% and 90% at your pace, your best pace and your luck so far.
- Alerts on Discord (with the screenshot) and on your phone through ntfy, a heads-up when a hunt stops on its own and an optional progress ping.
- OBS text files and the Pokémon's sprite for streamers.
- Mini mode, global hotkeys you can change (start/stop, +1, -1, mini mode) and an auto-stop timer.
- TEST plays your steps once without counting, and SUGGEST picks a shiny threshold from your real scores.
- Hunt codes to share a setup, CSV export, a daily backup of your save and an update check.
- Help for every page behind the ? button.
- A Windows installer, a single-file .exe and a portable zip.

### Fixed

- Drawing the watch area no longer leaves the setup stuck saying the area is missing.
