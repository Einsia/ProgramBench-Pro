# Task catalogue

An episode is one complete, realistic usage scenario consisting of a sequence of continuous operations and one or more checkpoints.

Episodes are either program episodes, which only contain program checks, or GUI episodes, which an evaluator model operates from user goals. Points are backend (program checks of product state, files and interfaces) or frontend (the evaluator's judgement of the visible result against the recorded reference screens).

### Full-stack web apps (`fullstack-web-app`, 7 tasks)

Self-hosted applications with a server, persistent data, a browser interface and HTTP APIs.

| Task | Reference software | Interfaces | Episodes (program / GUI) | Points (backend / frontend) |
| --- | --- | --- | ---: | ---: |
| [gitea](../tasks/fullstack-web-app/gitea/) | Gitea 1.22.6 | browser GUI; HTTP API; Git smart HTTP and LFS; package and container registries; uploads and downloads | 61 (14 / 47) | 3,377 (3,275 / 102) |
| [grocy](../tasks/fullstack-web-app/grocy/) | Grocy 4.7.1 | browser GUI; HTTP API; iCalendar and data-file uploads and downloads | 52 (10 / 42) | 1,947 (1,817 / 130) |
| [kanboard](../tasks/fullstack-web-app/kanboard/) | Kanboard 1.2.56 | browser GUI; JSON-RPC API; Atom and iCalendar feeds; HTTP cron; documentation; file uploads and downloads | 77 (16 / 61) | 1,685 (1,561 / 124) |
| [komga](../tasks/fullstack-web-app/komga/) | Komga 1.29.2 | browser GUI; REST API; OPDS, Kobo and KOReader protocols; exchange files; media uploads and downloads | 67 (28 / 39) | 1,989 (1,866 / 123) |
| [mealie](../tasks/fullstack-web-app/mealie/) | Mealie 3.29.0 | browser GUI; HTTP API; product uploads and downloads | 61 (18 / 43) | 1,467 (1,352 / 115) |
| [miniflux](../tasks/fullstack-web-app/miniflux/) | Miniflux 2.3.4 | browser GUI; HTTP APIs (REST, Fever, Google Reader); local web resources and request log; product uploads and downloads | 65 (21 / 44) | 1,111 (1,014 / 97) |
| [navidrome](../tasks/fullstack-web-app/navidrome/) | Navidrome 0.64.2 | browser GUI; OpenSubsonic and native HTTP APIs; music-library file operations; product uploads and downloads | 60 (19 / 41) | 1,124 (1,039 / 85) |

### Browser front-end apps (`browser-frontend-app`, 7 tasks)

Applications that run entirely in the browser, operated through their pages and documents.

| Task | Reference software | Interfaces | Episodes (program / GUI) | Points (backend / frontend) |
| --- | --- | --- | ---: | ---: |
| [bentopdf](../tasks/browser-frontend-app/bentopdf/) | BentoPDF 2.8.10 | browser GUI with PDF viewer frames; file upload, drop, download and reuse; clipboard; lifecycle controls | 94 (0 / 94) | 1,700 (1,354 / 346) |
| [drawdb](../tasks/browser-frontend-app/drawdb/) | drawDB 1.8.2 | browser GUI; file upload, drop and download; clipboard read and write; lifecycle controls | 79 (36 / 43) | 1,399 (1,174 / 225) |
| [ittools](../tasks/browser-frontend-app/ittools/) | IT-Tools 2024.10.22-7ca5933 | browser GUI; file upload, drop and download; clipboard; page clock; lifecycle controls | 122 (89 / 33) | 1,868 (1,729 / 139) |
| [jsoneditor](../tasks/browser-frontend-app/jsoneditor/) | JSON Editor 10.4.3 | browser GUI; documented JavaScript API; file upload/drop and JSON downloads | 128 (77 / 51) | 2,526 (2,251 / 275) |
| [piskel](../tasks/browser-frontend-app/piskel/) | Piskel 0.15.0 | browser GUI; sprite-coordinate input; JavaScript document API; file upload/drop and downloads | 91 (41 / 50) | 1,494 (1,278 / 216) |
| [stackedit](../tasks/browser-frontend-app/stackedit/) | StackEdit 5.15.4 | browser GUI; embedding messages; clipboard text and rich HTML paste; file upload/drop and downloads | 102 (55 / 47) | 1,533 (1,260 / 273) |
| [svgedit](../tasks/browser-frontend-app/svgedit/) | SVG-edit 7.4.2 | browser GUI; SVG editor JavaScript API; file upload, drop and download; lifecycle controls | 51 (14 / 37) | 838 (602 / 236) |

### Desktop document apps (`desktop-document-app`, 8 tasks)

Native desktop applications for documents, notes, spreadsheets and records, operated through X11 and AT-SPI.

| Task | Reference software | Interfaces | Episodes (program / GUI) | Points (backend / frontend) |
| --- | --- | --- | ---: | ---: |
| [cherrytree](../tasks/desktop-document-app/cherrytree/) | CherryTree 1.7.2 | GTK desktop GUI; document exchange; clipboard; command-line document opening/export | 109 (22 / 87) | 1,279 (1,095 / 184) |
| [gnumeric](../tasks/desktop-document-app/gnumeric/) | Gnumeric 1.12.62 | GTK desktop GUI; document exchange; clipboard; ssconvert/ssindex/ssgrep/ssdiff command-line tools | 99 (17 / 82) | 2,589 (2,396 / 193) |
| [joplin](../tasks/desktop-document-app/joplin/) | Joplin 3.7.21 | Electron/React desktop GUI; local Data API; document exchange; clipboard | 70 (11 / 59) | 1,779 (1,583 / 196) |
| [marktext](../tasks/desktop-document-app/marktext/) | MarkText 0.23.0 | Electron desktop GUI; document-opening command-line arguments; document exchange; clipboard | 59 (30 / 29) | 384 (354 / 30) |
| [moneymanagerex](../tasks/desktop-document-app/moneymanagerex/) | Money Manager Ex 1.9.4 | desktop GUI (wxWidgets on GTK); document exchange and clipboard text | 93 (3 / 90) | 2,057 (1,882 / 175) |
| [xournal](../tasks/desktop-document-app/xournal/) | Xournal++ 1.3.8 | desktop GUI (GTK); command line; document exchange and clipboard text/images | 104 (16 / 88) | 1,938 (1,740 / 198) |
| [zim](../tasks/desktop-document-app/zim/) | Zim 0.77.2 | desktop GUI (GTK); command line; notebook/document exchange and clipboard text | 57 (14 / 43) | 790 (667 / 123) |
| [zotero](../tasks/desktop-document-app/zotero/) | Zotero 10.0.6 | desktop GUI (Gecko/XUL); local Web API; document exchange and clipboard text/HTML/images | 115 (44 / 71) | 1,798 (1,660 / 138) |

### Desktop media apps (`desktop-media-app`, 7 tasks)

Native desktop applications for audio, music, and image workflows, operated through X11 and AT-SPI.

| Task | Reference software | Interfaces | Episodes (program / GUI) | Points (backend / frontend) |
| --- | --- | --- | ---: | ---: |
| [audacity](../tasks/desktop-media-app/audacity/) | Audacity 2.4.2 | desktop GUI (wxWidgets); scripting pipe; audio/label/project document exchange | 72 (42 / 30) | 3,576 (3,506 / 70) |
| [darktable](../tasks/desktop-media-app/darktable/) | darktable 5.6.2 | desktop GUI (GTK 3); darktable-cli; document exchange and XMP sidecars | 80 (39 / 41) | 1,446 (1,343 / 103) |
| [hydrogen](../tasks/desktop-media-app/hydrogen/) | Hydrogen 1.2.7 | desktop GUI (Qt); OSC over UDP; command line (h2cli); document exchange and settings | 52 (13 / 39) | 1,118 (1,021 / 97) |
| [lmms](../tasks/desktop-media-app/lmms/) | LMMS 1.2.2 | desktop GUI (Qt); command-line render/rendertracks/dump/upgrade; document exchange and settings | 56 (25 / 31) | 1,303 (1,219 / 84) |
| [musescorestudio](../tasks/desktop-media-app/musescorestudio/) | MuseScore Studio 4.7.6 | Qt Quick desktop GUI; score-conversion command line; score/document exchange | 51 (10 / 41) | 852 (807 / 45) |
| [musicbrainzpicard](../tasks/desktop-media-app/musicbrainzpicard/) | MusicBrainz Picard 3.0.3 | Qt Widgets desktop GUI; remote commands; picard-cli; media/profile/session exchange | 48 (5 / 43) | 1,107 (1,015 / 92) |
| [strawberry](../tasks/desktop-media-app/strawberry/) | Strawberry 1.2.31 | Qt 6 desktop GUI; MPRIS2; command line; media/playlist exchange | 75 (37 / 38) | 1,963 (1,865 / 98) |

### Terminal apps (`terminal-tui-app`, 8 tasks)

Terminal programs driven in a pseudo-terminal, often with a command-line or file interface beside the TUI.

| Task | Reference software | Interfaces | Episodes (program / GUI) | Points (backend / frontend) |
| --- | --- | --- | ---: | ---: |
| [calcurse](../tasks/terminal-tui-app/calcurse/) | calcurse 4.8.2 | terminal UI (PTY); command line; home-directory file exchange; user documentation | 123 (72 / 51) | 1,326 (1,206 / 120) |
| [cmus](../tasks/terminal-tui-app/cmus/) | cmus 2.13.0 | terminal UI (PTY); native Unix control socket; command-line options; media and state file exchange; user manuals | 192 (126 / 66) | 1,543 (1,410 / 133) |
| [lazygit](../tasks/terminal-tui-app/lazygit/) | lazygit 0.66.2 | terminal UI (PTY); Git inspection and repository setup; workspace and state file access; command-line options; OSC 52 clipboard | 221 (130 / 91) | 820 (709 / 111) |
| [micro](../tasks/terminal-tui-app/micro/) | micro 2.0.15 | terminal UI (PTY); command line; workspace and configuration files | 225 (106 / 119) | 1,421 (1,295 / 126) |
| [newsboat](../tasks/terminal-tui-app/newsboat/) | Newsboat 2.45 | terminal UI (PTY); command line; home files; SQLite cache; local feed HTTP input | 161 (134 / 27) | 1,344 (1,227 / 117) |
| [taskwarriortui](../tasks/terminal-tui-app/taskwarriortui/) | taskwarrior-tui 0.27.0 | terminal UI (PTY); Taskwarrior command line | 141 (71 / 70) | 1,284 (1,184 / 100) |
| [tig](../tasks/terminal-tui-app/tig/) | Tig 2.6.1 | terminal UI (PTY); native console and grep; command line and pager; Git repository and file inspection | 272 (179 / 93) | 1,188 (1,064 / 124) |
| [visidata](../tasks/terminal-tui-app/visidata/) | VisiData 3.4 | terminal UI (PTY); batch command line; workspace files and input history | 171 (51 / 120) | 1,432 (1,308 / 124) |


[Back to the README](../README.md)
