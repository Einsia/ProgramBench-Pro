# Strawberry coverage

Task version 1.0.0, unmodified Strawberry 1.2.31. The executable
manifest and frozen bundle are authoritative: **75 episodes** (38 GUI and
37 program), **98 frontend** and **1,865 backend** assertions, **1,963 total**.

| Feature family | Coverage |
| --- | --- |
| Media reading | FLAC, Ogg Vorbis, Opus, MP3, AAC, ALAC, WAV/ID3, AIFF/ID3, WavPack, ASF, Speex, Ogg FLAC and TrueAudio. Eight distinct tag/rate/channel/duration profiles per container; additional FLAC/MP3/Vorbis/AAC/WAV profiles omit title/artist/other tags, contain multiple artists, track/disc totals and full dates, and use subsecond audio. Each field is checked independently. |
| Playlist formats | M3U/M3U8, PLS, XSPF, ASX INI, XML ASX, WPL and CUE parsing; reordered/duplicate entries, overrides, relative references, XML escaping, Unicode, BOM/newlines, unequal media lengths and three CUE segment boundaries. GUI M3U/PLS/XSPF saving, clearing and loading; relative/absolute paths; saving all open named playlists. |
| Playback | GUI play/pause/stop/track selection, volume/mute/repeat/shuffle; program transport transitions, capabilities, bounded volume, collection ratings, paused seeks, unsupported rates and stale IDs. Short tracks cover natural end, next-track transitions, stop-after-current, repeat-track/playlist boundaries, and deleting current/last tracks. |
| Playlist management | GUI insert/remove/undo/redo/clear/duplicates, title and track sorting with deliberately different orders, filtering, named tabs and persistence. MPRIS insertion positions, RemoveTrack, GoTo, metadata request order/duplicates/invalid IDs, append/OpenUri, playlist ordering/pagination/reversal/activation. |
| Command line | Playback and track selection, absolute/relative seeking, fixed/custom volume increments and boundaries, playlist creation and selection by name, stop-after-current. All commands forward to the running instance. |
| Collection and organization | Scanning, artist/album hierarchy, filtering, Unicode, adding collection songs, move with formatted path, copy keeping originals, overwrite conflict, content preservation and restart. |
| Smart and dynamic lists | Create/edit/delete, restart persistence, artist predicates, AND/OR, numeric year comparison, no matches, title sorting, limit, and dynamic mode adding unique songs from the allowed collection after advancement. Dynamic order/count bookkeeping is not frozen. |
| Tag editing | Title/artist/album/genre/year/track/disc/composer/comment/lyrics writes, exact Unicode and discarded edits; downloaded media parsed independently. |
| Transcoding | WAV, MP3, Opus, FLAC, ALAC, AAC, Vorbis, Speex, WavPack, ASF and Ogg FLAC. Short source changes frequency and amplitude throughout, with distinct left/right signals. Speex uses a mono voice-codec fixture; all other formats preserve both channels. Codec, duration, channel count and every half-second signal window are checked. |
| Local artwork | Cover manager listing/filtering; two distinguishable local images, embedded cover writing, export, replacement, restart and removal. Downloaded pixels and embedded image attachments are independently checked. |
| Queue | Enqueue order and dequeue. |
| Settings and analysis | Save/cancel/restart, volume increment, playlist relative/absolute path behavior, ReplayGain selection, local EBU R128 collection analysis on two different loudness levels, compared with independent FFmpeg analysis. |
| Malformed media | Invalid FLAC/MP3/Vorbis/WAV files reach the product decoder; it reports a visible error and stops while retaining the original valid track. Positive companion points prevent an inert implementation from receiving rejection credit. |

All setup and checks cross the shared runtime: upload, MPRIS, CLI, desktop,
list_files/download and restart/reset. SQLite/INI state is never read.
GUI backend checks concern the stated goal's result. When MPRIS exposes the
active playback list rather than the displayed tab, the public activation
method selects the displayed list after frontend evidence has been captured.

Each program scenario establishes a baseline. Candidate crashes trigger recovery
before the next scenario. Setup and dependencies are explicit; scored operations
are not replayed as setup. Metadata collection waits for stable raw observations,
then every assertion validates its own field: a missing/wrong duration does not
fail unrelated tags. Ogg FLAC's unavailable duration and unsupported TrueAudio
fields are omitted. IDs, timestamps, artwork-cache URLs and bookkeeping are not
compared. Rejection/empty/cleared-rating cases have positive companions.

Playlist exports resolve references against the public playlist directory,
decode file URIs, and compare actual input document identities and order. Every
target must exist in list_files. PLS order follows numeric FileN keys. Optional
titles, EXTINF strings and artist/title display composition are not frozen.
Organization downloads must preserve the original document bytes, including
encoded audio and tags; empty/corrupt output cannot satisfy a correct pathname.

Metadata/container durations allow 150 ms; paused seeking allows 1.5 seconds
because the native API uses integer seconds. Percent volume and float ratings
allow 0.011. Audio comparisons align at most 120 ms of codec delay, allow 160 ms
of codec padding, and compare RMS and frequency in every half-second window of
every channel, including the tail. RMS tolerance is max(0.008, 18% of source RMS)
and spectral peaks within two bins of the inset 300 ms window. This admits
lossy encoding while rejecting missing tails, silent/mixed/swapped channels and
wrong content. Artwork compares decoded RGB at 64×64 with mean error below 10,
allowing image recompression. Loudness agrees with independent EBU R128 analysis
within 1 LUFS; its frozen visible result allows 0.3 LUFS.

Desktop evidence uses 1440×900 and shared AT-SPI/input. Functional goals permit
equivalent controls and routes. Reference recipes use accessible controls or
screenshot coordinates; they do not constrain candidate widget types. Selected
repeat modes are visible in the open mode menu; filenames/content are program
checks, while the organization frontend checks the visible collection result.
GUI budgets are at least 150 calls, 1,500 seconds and 3,000,000 tokens and scale
with checkpoint count. Local artwork uses 400 calls, 6,000 seconds and 8,000,000
tokens for its import, export, replacement and persistence operations.
Program episodes use deterministic checks. Episode wall limits are derived
from the recorded duration of each episode.
