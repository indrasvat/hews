# Hews – Hacker News Terminal Browser CLI – Product Requirements Document (PRD)

## 1. **Overview and Vision**

**Product Name:** *Hews* (a working title) – a terminal-based Hacker News browser, search, and reader.

**Summary:** *Hews* is a command-line tool for macOS (and other OSes) that lets users browse Hacker News (HN) in a modern Terminal User Interface (TUI). It provides a rich, colorful text UI (built with the latest **Textual** and **Rich** libraries) to navigate HN posts and comments without leaving the terminal. By default, the tool is read-only (ideal for quick reading), but users can optionally log in to their HN account to upvote and comment. The interface is intuitive, keyboard- and mouse-friendly, and optimized for speed (using asynchronous I/O and caching to minimize latency). Notably, the interface puts a strong emphasis on visual style and user experience, making *Hews* more engaging than a typical CLI tool. 

**Goal:** Deliver a comprehensive, **implementation-ready** specification for *Hews* that a developer can directly use to build the tool using modern Python 3.12 best practices. This PRD outlines all features, technical requirements, and design considerations in detail, ensuring the resulting tool is a standout among HN CLI readers.

## 2. **Objectives and Non-Goals**

### 2.1 Objectives (What we will achieve)

- **Full Hacker News Browsing:** Provide an interface to read HN content (posts and comments) in the terminal. Support all main HN sections: Top, New, Ask HN, Show HN, and Jobs posts.
- **Search Functionality:** Integrate HN’s search (via the Algolia API) to find stories by keywords. Potentially support offline full-text search on cached data for instant results.
- **Modern TUI/UX:** Use **Textual** (with **Rich** for styling) to create an attractive, responsive text-based UI. Aim for GUI-like usability in the terminal (mouse support, dynamic content, theming).
- **Performance:** Ensure fast startup and minimal waiting:  
  - Use **httpx** with async/await for concurrent data fetching .  
  - Implement intelligent caching of content (stories, comments, etc.) to speed up repeat views and enable offline use.
- **Optional HN Account Actions:** Allow users to log in (via `.env` or prompt) to upvote posts and possibly add comments, while keeping default usage read-only for simplicity.
- **Robust CLI Design:** Use **Click** for command-line argument parsing and adhere to CLI best practices (following guidelines from [clig.dev](https://clig.dev/) for consistency and usability). Provide clear `--help` text and a well-structured command interface.
- **Python Best Practices:** Leverage Python 3.12 features and modern libraries:  
  - Use **python-dotenv** for managing configuration/secrets (HN credentials, etc.) via a `.env` file.  
  - Use **Loguru** for logging (for easier debugging and maintenance).  
  - Manage dependencies with **uv**, a fast modern Python package manager, ensuring reproducible environments.  
  - Write clean, type-hinted Python code, making it maintainable and clear for a junior developer to pick up.

### 2.2 Non-Goals (Out of Scope for v1)

- **Posting new stories:** Out of scope. We focus on reading and lightweight interactions (upvotes/comments) rather than submitting new HN posts.
- **Advanced Analytics or AI Summaries:** No sentiment analysis, AI-generated summaries, or other heavy post-processing in this version.
- **Graphical Web Interface:** The target is strictly terminal usage (Textual’s web capabilities are possible for future extension, but not a current goal).
- **Extensive Moderation Tools:** Not building admin/moderation features (no content flagging beyond what HN normally allows for logged-in users).

By clarifying scope, we ensure the implementation focuses on core functionality first. Future enhancements (see later sections) can extend this base.

## 3. **User Stories and Use Cases**

- **Use Case 1 – Passive Browsing:** *Alice*, a software engineer, wants to catch up on HN during breaks without opening a browser. She runs `hews` and immediately sees the top HN stories in her terminal. She uses arrow keys (or *j/k*) to scroll through headlines and hits *Enter* to read a thread’s comments. The interface highlights the original poster’s comments and high-scoring replies, making it easy for her to skim important points. She doesn’t log in; she just reads comfortably in the terminal. **Success:** Alice browses HN content quickly, with minimal distractions, and the TUI is faster than using the HN web UI.

- **Use Case 2 – Search and Research:** *Bob* is researching a topic (say *“Python CLI tools”*) that was discussed on HN. He invokes a search mode in the app (maybe by pressing `/` or via a CLI command) to query the HN Algolia search. The tool returns a list of matching stories with titles, dates, and scores. Bob selects a story to read its discussion. Because Bob might be offline later, the tool caches the story and comments locally. **Success:** Bob finds relevant discussions via search and can refer to them even if he goes offline, thanks to caching.

- **Use Case 3 – Logged-in Interaction:** *Cara* frequently comments on HN. She wants the ability to upvote or add a quick comment without leaving the terminal. She sets her HN username/password in the `.env` file and launches *Hews*. The tool logs her in (securely) in the background. When reading a story, she presses `u` to upvote an insightful comment and the UI reflects the upvote (perhaps by color or a symbol). She can also press a key to enter a comment reply mode, type her comment in a text input widget, and submit it. **Success:** Cara’s upvotes register (with confirmation or error feedback), and her comment posts successfully, all within the CLI tool.

- **Use Case 4 – Offline Reading:** *Devon* has spotty internet on his commute. He uses *Hews* to cache the latest top stories in the morning. While offline, Devon can open the tool and still read the content cached earlier (the stories and comments load from local storage). The interface might indicate offline mode (and disable actions like voting). **Success:** Devon can read previously fetched HN threads without internet, with the app seamlessly falling back to cached data.

These scenarios highlight the need for a fast, read-friendly UI, search, caching, and optional interactivity. The PRD’s requirements below ensure these needs are met.

## 4. **Feature Requirements**

This section details each major feature of *Hews*. Each requirement is described in terms of user-facing behavior and specific constraints or implementation notes.

### 4.1 **General Interface & Navigation**

- **Startup Behavior:** If run without any command-line arguments, `hews` launches the interactive TUI application. The initial view defaults to *Top Stories* (the HN front page). The terminal is cleared or switched to an app view (using Textual’s App run loop). A header or title bar should display the application name and current section (e.g., “Top Stories”), and possibly a brief help hint (e.g., “Press ? for help, q to quit”).

- **Launch Banner:** When the application starts up, display a distinctive ASCII art banner showing the tool’s name ("HEWS") in stylized, colorful text. This can be done using a library like **pyfiglet** or Rich’s text rendering to create a big, colorful title. The banner gives the app a unique visual identity at launch and sets a fun, modern tone. After the banner is displayed (as a brief splash or part of the header), the TUI proceeds to show the normal Hacker News content.

- **Keyboard Navigation:** The UI must support common navigation keys:  
  - *Arrow Up/Down or j/k:* Move the selection cursor through lists (story list or comment list).  
  - *Enter or Right Arrow:* Select/open the highlighted item. On the story list, *Enter* opens the story detail (comments view); on a comment thread, *Enter* or *Right* might expand/collapse a comment thread (see 4.3).  
  - *Left Arrow or b:* Go “back” to the previous view. E.g., from a story detail back to the story list.  
  - *Home/End or g/G:* Jump to top or bottom of a list (optional but common in UIs).  
  - *Page Up/Page Down or space:* Page through long lists or comment threads quickly.  
  - *? (Question Mark):* Toggle a help overlay showing keybindings and tips (like how to search, quit, etc.).  
  - *q:* Quit the application (with a confirmation prompt if needed).

- **Mouse Support:** Using Textual’s mouse support, the user should be able to click on story titles to open them, click on UI tabs or buttons (if any), and expand/collapse comments by clicking on them. The TUI will treat mouse clicks similar to key navigation for an intuitive experience (e.g., clicking a story = pressing Enter on it). This requires enabling mouse tracking in Textual (which is supported out of the box).

- **CLI Arguments:** Even though interactive TUI is the default, support some command-line options for advanced usage:  
  - `hews --section <name>` or simply `hews top/ask/show/etc.`: Directly start in a specific section (e.g., `hews ask` jumps straight to Ask HN posts).  
  - `hews --story <id>`: Directly open a specific story by ID (bypassing the list). Useful for integration with other tools (pass an HN item ID).  
  - `hews --search "query"`: Start in search results for the given query (immediately enter the search view).  
  - `hews --no-curses` or `--print-only`: (Optional) Non-interactive mode to output data to stdout instead of the interactive UI – e.g., `hews --section top --print` prints top stories to the console and exits. This allows scripting or piping into other commands (secondary to the primary interactive mode).  
  - Standard flags: `-h/--help` (auto-generated by Click) shows usage information; `--version` shows the app version.

  **Rationale:** We use **Click** to parse CLI arguments and dispatch accordingly. Click allows defining subcommands or options easily, with built-in help generation. This ensures consistency with CLI UX guidelines and allows power users to use the tool in scripts or quick queries, in addition to interactive mode.

- **Help and Documentation:** The application should have an in-app help screen (triggered by `?`) listing all key commands and a brief description. Additionally, `hews --help` should summarize usage. We will follow [clig.dev](https://clig.dev) recommendations for wording and formatting of help messages, ensuring clarity and brevity. For instance, commands should be named intuitively (`top`, `new`, `search` etc.), and help text should use consistent terminology (refer to posts as “stories”, etc.).

### 4.2 **Browsing Hacker News Sections**

- **Section Selection:** Users can switch between HN sections: **Top**, **New**, **Show HN**, **Ask HN**, **Jobs**. This can be done via keyboard shortcuts (e.g., `1-5` keys for those sections, or letter shortcuts like `t` for Top, `n` for New, etc.), and/or an on-screen menu. Consider a top navigation bar or sidebar listing sections:  
  - *Option 1:* A horizontal menu bar (tabs) at the top highlighting the current section. The user can press `Tab` or a specific key to move between sections.  
  - *Option 2:* A vertical menu or simply direct keys without a visible menu (simpler for v1).

  For v1, a simple approach: use keys to switch sections and display the section name in the header. For example, pressing `t` = Top, `a` = Ask HN, `s` = Show HN, `j` = Jobs, `n` = New. These keybindings will be listed in the help.

- **Fetching Stories:** When a section is selected, the app fetches the list of story IDs for that section from the Hacker News API:  
  - **Official HN API:** Use the official Firebase-based HN API (e.g., `/v0/topstories.json`, `/v0/newstories.json`, etc.) to get story IDs for each section. This returns an array of item IDs (e.g., top 500 IDs for Top stories).  
  - **Fetching story details:** For each story ID in the list (at least the first N stories to display, say 30 by default), fetch the story’s details (title, URL, score, by, time, descendants count, etc.) via `/v0/item/<id>.json`. Doing this sequentially is slow, so fetch details concurrently using **httpx** async (spawn async requests for the top 30 IDs and gather them).  
    - Implement an **HN API client** (see Architecture §5) to handle this, possibly with caching (if story ID 12345 was fetched recently, reuse it from cache).  
  - **Batching optimization:** If needed, consider Algolia’s batch query capabilities (Algolia indexes HN items and can retrieve multiple items by IDs). But using official API with parallel httpx requests should suffice for ~30 items quickly.  
  - **Caching:** The first time a section is loaded in a session, fetch from network. Keep results in memory (and optionally on disk). If the user returns to a section, use cached data if it’s fresh, and provide manual refresh (e.g., pressing `r` to refresh the section). Also cache the list of IDs for offline use.

- **Story List Display:** Once stories are fetched, display them in a scrollable list. Each story entry should include key metadata:  
  - **Title** – displayed prominently (e.g., bright yellow or orange) for visibility. If the story is a link, follow the title with a dimmer domain name in parentheses (like HN web UI).  
  - **Score** – points the story has (e.g., “123 points”), and number of comments (“45 comments”) if applicable. The HN API’s story object has `score` and `descendants` (comment count).  
  - **Author** – the username (`by` field).  
  - **Age** – how long ago it was posted (e.g., “3 hours ago”), computed from the Unix timestamp (`time` field).  
  - Possibly a **rank number** (1, 2, 3, …) preceding each item if the list is ordered (Top, New, etc.).

  Example list entry format:  
  ```
  1. Some Interesting Article Title (example.com)  
     123 points by alice | 45 comments | 3 hours ago
  2. Another Story (github.com)  
     56 points by bob | 10 comments | 1 hour ago
  ...
  ```  
  Use **Rich** styling for readability – e.g., title in one color, metadata in another, ensure alignment and wrapping. Long titles should wrap or truncate gracefully to the next line with indentation (avoid breaking the layout).

- **Paging or Continuous Scroll:** Initially show, say, top 30 stories. If more exist (Top can have up to 500 items), allow loading more:  
  - Perhaps pressing a key (e.g., `]` or at the bottom prompt “press n for next page”) to load the next batch of 30.  
  - Or implement infinite scroll: when the user reaches end of list, automatically fetch next set.  
  - Given 500 items is a lot to scroll, focusing on top ~100 for v1 is fine (with manual load for more if needed).

- **Ask HN / Show HN / Jobs specifics:**  
  - *Ask HN / Show HN:* These are stories often with text content. We’ll list them like any story but note that when opened, they may have a text body before comments (see Story Detail). We might visually mark Ask HN in list (e.g., prefix title with “[Ask]” or a color indicator) just for clarity.  
  - *Jobs:* HN job posts have no comments (descendants = 0) and often include a `text` job description. In the list, show title and author/time (omit comments count since 0). On selection, display the job description text.

- **Section Refresh:** Provide a key (e.g., `r`) to refresh the current section (re-fetch the latest story list from the API). This updates the list in place without restarting the app. Show a loading indicator (spinner or message) during refresh. If offline, either warn the user or use stale data from cache.

### 4.3 **Story Detail and Comments Viewing**

When a user opens a story (presses Enter on a story in the list), the app transitions to a **Story Detail View**. This view shows the story’s content (if any) and its comment discussion in a threaded format.

- **Story Header/Metadata View:** At the top of this view, display the story title and metadata prominently:  
  - **Title** – possibly larger/bold or underlined.  
  - If the story has a URL (not a text post), show the URL/domain. Allow a key press (like `o`) to **open the URL in the default web browser** (via Python `webbrowser.open`).  
  - Show points, author, posted time, and number of comments (“descendants”) on a subheader line.  
  - If the story is a text post (e.g., Ask HN question or job listing with `text` field), display that text content nicely formatted below the title. The `text` is HTML (or HN’s HTML-like format); convert to plain text or simple markdown. **Rich** can help render Markdown or safe HTML. At minimum, strip tags and render paragraphs/newlines, preserve lists or code formatting if present.  
  - Polls (rare on HN): if `parts` or poll options exist in the story data, list them with their points (optional for v1).

- **Comments Thread Rendering:**  
  - **Tree Structure:** HN comments are a tree (each comment has `kids` array of reply IDs). Display comments in an indented thread layout. Use indentation or text tree lines to indicate depth: e.g., indent replies by a few spaces, maybe draw vertical `│` and `└─` characters connecting replies to parents for visual clarity. Ensure these line-drawing characters display properly (most modern terminals handle UTF-8 well).  
  - **Collapsible Threads:** Users should be able to collapse a comment and all its replies:  
    - If a comment has replies, indicate with a symbol (e.g., triangle ▶/▼ or `[+]`/`[-]`).  
    - Pressing *Right* (or Enter) on an expanded comment *collapses* it, hiding all nested replies, and changing the symbol to a collapsed state (e.g., from ▼ to ▶ or `[-]` to `[+]`).  
    - Pressing *Right* on a collapsed comment *expands* it, showing its replies again (symbol switches back). *Left* arrow could also be used to collapse (mirroring open/right, close/left behavior).  
    - **Implementation:** Textual may not have a built-in tree widget in early versions, but we can manage manually. Represent comments as individual widgets or lines; maintain a data structure of which comments are expanded. On collapse, hide or remove the child comment widgets from view; on expand, insert them back. We might pre-build the comment tree structure in memory for easy show/hide. By default, we can start with all top-level comments expanded, and deeper replies collapsed initially (so a thread with many replies doesn’t overwhelm until user expands it).

  - **Comment Content Display:** For each comment, show:  
    - Metadata: username, time posted. (HN API comments don’t include score/upvotes, so skip points for comments.)  
    - The comment text, which is HTML (with links, <i>, <pre>, etc.). Render it to plaintext or simplified markdown. At least preserve paragraphs, line breaks, and basic formatting like italics or code blocks for readability.  
    - **OP Highlight:** If the comment author is the original story poster (story’s `by`), indicate it (e.g., append “[OP]” after their username or color their name differently). This helps identify the author’s responses.  
    - **Deleted/Dead Comments:** The API marks deleted comments (`deleted: true`) or dead (moderated) ones (`dead: true`). For those:  
      - If deleted: show “[deleted]” in place of text, maybe in italic or gray.  
      - If dead/flagged: similar to deleted (possibly “[dead]” placeholder). We might hide them entirely by default or show a faint placeholder to indicate missing content.  
    - **Formatting**: Ensure the comment text wraps properly within the available width. If the comment is very long or has code blocks, use Rich to format it nicely (monospaced font for code, etc., if possible in terminal).  
    - **High-scoring/Popular indicators:** (Optional/future) If we had comment points or external hints, we could highlight notably upvoted comments. Since we don't have scores, one idea is highlighting comments with many replies (implying they generated discussion). This is a stretch idea, not core.

  - **Lazy Loading Comments:** Some stories have hundreds of comments. Fetching them all at once can be slow. A strategy (for performance, see §5.6):  
    - Initially fetch only top-level comments (the IDs in story.kids). Display them (with an indicator if they have replies not yet fetched, like “[+ 10 replies]”).  
    - When the user expands a comment for the first time, then fetch that comment’s children from the API (which will in turn include their kids recursively or require further fetches). This way we load what the user needs on demand.  
    - Cache any fetched comment so subsequent expansions are instant.  
    - Show a small “Loading...” message or spinner when fetching on-demand.  
    - This approach prevents us from making, say, 300 separate HTTP requests upfront for a huge thread. It trades initial speed for a slight delay when the user drills into a deep thread, which is acceptable.

  - **Comment Navigation Controls:**  
    - Up/Down arrows move the focus through visible comments (skip over collapsed children).  
    - *Right* (or Enter) on a comment toggles expand/collapse (for consistency, maybe choose one: e.g., Enter toggles, or Right = expand, Left = collapse).  
    - Provide a key (maybe `c` or `x`) to explicitly collapse/expand the currently focused comment’s thread (as an alternative to using arrows/enter).  
    - Provide a key (maybe `m` for “minimize” or `h` for “hide”) to collapse *all* comment threads at once (show only top-level comments). Conversely, maybe another (like `M` or `E`) to expand all. Expanding all in a huge thread might be too slow, so this is optional. Collapsing all can be helpful to skim just the main threads.

- **Return to List:** The user can press `Left` (or `b`, or a dedicated key like `q` if not used globally) to go back to the story list from the comments view. Preserve the story list scroll position and selection, so users pick up where they left off. (Textual screens will help manage this state, as the previous screen remains in memory unless fully torn down.)

### 4.4 **Search Functionality**

Searching Hacker News is a key differentiator for our tool. We use the Hacker News **Algolia Search API** (which powers the search on the HN website) to implement story search.

- **Entering Search Mode:**  
  1. **In-App:** Press `/` to open a small search input overlay. The user types a query and hits Enter, then the UI switches to a Search Results screen showing matches.  
  2. **CLI Invocation:** As noted, `hews --search "query"` can start the app directly in search results mode for that query.

- **Using Algolia API:** The HN Algolia API provides full-text search over stories (and comments):  
  - For stories, endpoint example: `https://hn.algolia.com/api/v1/search?query=<keywords>&tags=story`. We’ll use the `tags=story` parameter to focus on story titles (and story text).  
  - Use **httpx** to fetch search results (one GET request returning JSON).  
  - Parse the JSON “hits” to extract fields: title, URL, points, author, num_comments, objectID (which is the story’s HN ID).  
  - No auth or API key is needed for this endpoint, but be mindful of rate limiting (avoid spamming queries in a loop). Possibly, if a user searches rapidly multiple times, introduce a short delay or limit.

- **Displaying Search Results:** Show results similar to a story list:  
  - Each item: title, points, author, date (Algolia provides `created_at` which we can convert to “N hours ago”).  
  - Optionally indicate it’s a search result (maybe a label “[Search]” in the header or different color scheme).  
  - If the search query matched in the story text or comments (Algolia can search comments too if we used different parameters), we might show an excerpt or highlight (but to keep it simple, assume we search titles primarily, so no excerpt).  
  - Navigation and selection work same as story list. Pressing Enter on a search result opens the story’s comments view. Internally, we have the story’s HN ID (objectID), so we can fetch that story via the HN API (or possibly Algolia provides the story content in the result, but likely we’ll do a fresh fetch to get comments).  
  - Cache any story opened from search into the same cache as others.

- **Search History:** Nice-to-have: remember recent queries (in memory during the session). If the user re-opens the search input, they could arrow up to see previous queries, etc. (This could be added easily by storing queries in a list; but basic input is fine for v1).

- **Advanced Search Options (Future):** We design the search with future extensions in mind, such as filtering by date, by author, or searching within comments. The Algolia API supports complex queries (e.g., `tags=comment` or adding `author:username`). For v1, keep it simple (keyword search across stories). But the code structure (maybe have a `search(query, tags="story")` method) could allow adding parameters later.

- **Offline Full-Text Search (Optional):** If feasible, allow searching cached content when offline:  
  - This means implementing a local search index of cached stories (and maybe comments).  
  - A simple approach: linearly search through titles and text of cached items for the keyword. That might be fine if cache is small, but if large, it's slow.  
  - A more robust approach: use SQLite **FTS5** full-text search on cached content. For example, maintain an FTS index on story titles and comment text in the cache DB. Then an offline query can use SQL to find matches.  
  - This is an ambitious feature and can be marked experimental. It would truly set us apart (offline search in a CLI). For v1, it's optional if time permits. We mention it for completeness, but it’s not required to implement if it's too much.

- **Result Sorting:** By default, Algolia sorts by relevance. We can stick with that. Optionally, we could allow sorting by date or points (Algolia has parameters for sort by date or a separate “search_by_date” endpoint). To keep UI simple, we won't add sorting toggles in v1.

### 4.5 **Offline Caching and Data Management**

Offline capability and caching are crucial for performance and user experience.

- **What to Cache:**  
  - *Stories:* ID, title, URL, points, author, timestamp, text (if any), descendants count, and maybe the list of top comment IDs.  
  - *Comments:* For each story, cache the comments (ID, author, text, parent, maybe a pointer to children IDs). Possibly cache nested comments as a blob or separate entries.  
  - *User info:* If we implement features like user lookup, caching user profiles (id, karma, etc.) could be considered, but not needed for v1.

- **Cache Storage:** Use a persistent on-disk cache so data persists across runs. Options:  
  - **SQLite database:** (Preferred) e.g., `~/.cache/hews/cache.db`. Tables for stories and comments, with appropriate indices. SQLite allows structured queries (and FTS). We can store JSON or break into columns. It's file-based, no separate server, and Python’s `sqlite3` is easy to use.  
  - **JSON files:** (Alternative) e.g., one file per story (containing story and its comments). This is simpler to implement, but harder to query (no easy search) and could get cluttered.  
  - Given our need for possible full-text search and efficient lookup, SQLite is recommended. We will outline the schema and usage in §5.2. 

- **Cache Freshness/Expiration:**  
  - HN stories don't update much (score increases, new comments appear). We decide how “fresh” the cache should be before refetching: e.g., consider a cached story stale after 15 minutes or an hour.  
  - For simplicity, whenever online, fetch fresh data for sections and story detail every time they are opened (unless the user literally goes back and forth quickly, in which case we might reuse very recent data). If offline, fall back entirely on cache.  
  - We can include a timestamp in cache entries. If a user opens a story and the cache is older than, say, 30 minutes, we could trigger a refresh in the background (showing the cached content immediately, then updating if new info comes). But this is a refinement; initially we can just always fetch on open if online.  
  - Manual refresh (key `r`) always bypasses cache and fetches.

- **Preloading for Offline:** (Optional) We could allow the user to preload data. For instance, a CLI flag `--preload <section>[:N]` to fetch top N stories from a section and all their comments, then exit. This way a user could run `hews --preload top:50` in the morning (with internet) to have content ready for offline reading. Not a core feature, but relatively easy to implement with the HNClient logic. We note it as a potential feature if time permits.

- **Cache Integration:** See technical design (§5) for implementation, but essentially the HNClient will check cache first:  
  - If data is available and fresh, use it. If not, fetch from API and then store it in cache.  
  - The cache layer should be abstracted so it's easy to call (e.g., `cache.get_story(id)` returns a Story object or None).  
  - Consider atomic operations: if writing to SQLite, use transactions to avoid partial writes (particularly if caching multiple comments, etc.). 

- **Cache Size Management:**  
  - Over time, cache might grow. For v1, the volume is text (which is not huge unless you cache thousands of stories). We can potentially ignore eviction until it’s a problem. But to be safe:  
  - We could implement a simple LRU: keep only the last N stories fetched or limit total cache size (e.g., 100 MB).  
  - Or provide a command/option to clear cache (`hews --clear-cache`).  
  - Since this is not critical for initial functionality, we can document that cache may grow and let user clear it by deleting the cache file if needed. Implementing LRU eviction could be a later improvement.

- **Cache Location and Config:**  
  - Use OS conventions (on macOS, maybe `~/Library/Caches/Hews`; on Linux, `~/.cache/hews`). The code can detect platform or use an env var override.  
  - The user can configure via environment variables: e.g., allow `.env` to specify `HEWS_CACHE_PATH` or similar if they want a custom location.  
  - Also possibly config for cache expiry time or max size if we implement those.

- **Offline Mode Detection:**  
  - On startup or section load, if network requests fail (e.g., no internet), the app should gracefully enter “offline mode.”  
  - Indicate offline status (e.g., a message in header or popup: “Offline – showing cached data”).  
  - In offline mode, automatically use cache for sections and stories. If something isn’t in cache, inform the user (e.g., “Not available offline” if they try to view a story not seen before).  
  - Disable actions that require network: e.g., login, voting (they wouldn’t work offline).  
  - The app could attempt to ping the HN API at startup; if unreachable, toggle a global offline flag.

### 4.6 **User Authentication and Interactions**

Reading content is primary, but logging in enables upvoting and commenting which can enhance engagement for power users. This is optional (the tool works read-only without login).

- **Login Mechanism:** HN’s official API is read-only; login requires using the website’s form and cookies. Plan:  
  - The user provides HN credentials via environment or input. We prefer not to prompt on every run, so encourage putting `HN_USERNAME` and `HN_PASSWORD` in `.env` (which is loaded at startup). Alternatively, a manual login command could prompt (with hidden password input).  
  - Use **httpx** to perform the login:  
    - GET `https://news.ycombinator.com/login` to retrieve the form and a hidden token (`fnid`).  
    - POST credentials to the same URL. If successful, we get a session cookie (HN uses a `user` cookie).  
    - Store the session cookie in the httpx client for subsequent requests (so upvotes/comments will be authenticated).  
    - If login fails (wrong password), handle gracefully (don’t crash; show an error message in the UI like “Login failed”).  
    - Security: Do not print the password anywhere. If prompting, use proper no-echo input. If using `.env`, the user is responsible for keeping it secure on disk.

- **Upvoting:** Once logged in (session cookie present), allow upvoting stories and comments:  
  - Indicate upvote-ability in the UI: For example, show an ▲ arrow next to items when logged in. Possibly highlight it if the user has already upvoted (though detecting that might require additional info; might skip that detail).  
  - Key binding: pressing `u` (or `+`) on a selected story or comment triggers an upvote action.  
  - Implementation: HN’s voting is done via a GET request to a vote URL (with `id`, `how=up`, and an `auth` token, plus a `goto` parameter for redirect). The `auth` token is present in the HTML of the item page for each upvote link.  
    - We may need to fetch the item page HTML to get that token for each item or find a way to derive it. This is a bit hacky but known solutions exist (like parsing the HTML for the upvote link).  
    - Simpler: maybe only allow upvoting the story (not individual comments) initially, to avoid parsing every comment’s link. Upvoting the story’s link is easier because we can fetch the story page when needed. Upvoting comments would require parsing the entire thread’s HTML to get each comment’s link, which is heavy.  
  - For v1, possibly implement story upvotes (and leave comment upvotes for later, or treat them similarly if time allows).  
  - Feedback: after upvoting, increment the points in the UI or mark the story as upvoted (maybe change the arrow color). The HN API itself won’t reflect the new vote immediately (and it doesn’t provide user-specific info about votes), so we just do a local UI update. If the request fails (network or other issue), show an error message.  
  - If user is not logged in and presses `u`, prompt them to log in or show a notice “Login required”.

- **Commenting:** Allow the user to post comments (reply to a story or another comment):  
  - Trigger: perhaps `c` (or `r` for reply) when on the story or a comment.  
  - If on a story (top-level reply), or if on a comment (reply to that comment).  
  - Open an input box where the user can type the comment text. This could be a modal overlay or even a simple prompt at the bottom. Support multiline text if possible (maybe allow newline input or open an external editor via $EDITOR for multiline; but that may be overkill). Possibly just allow a single-line comment for simplicity, but HN comments often need multiple lines. Maybe allow `Shift+Enter` to input a newline in the text box.  
  - Implementation: After text is entered, send a POST to `https://news.ycombinator.com/comment` with fields `fnid` (the form token from the story page), `text`, and `parent` (the item id to reply to). The story page HTML (for the story or comment thread) contains the form for adding a comment if user is logged in, including a hidden `fnid`. So similar to upvote, we need to have fetched or kept the story HTML to get that. Perhaps when we fetch the story for display, we could also fetch the HTML page in the background if the user is logged in (to have tokens for upvote/comment). This is an advanced implementation detail for the dev.  
  - If posting succeeds, ideally update the UI to show the new comment (maybe re-fetch comments or just insert the comment under the parent). The HN API might not immediately return the new comment via the official API (and Algolia might index it after a short delay). But since the user wrote it, we can optimistically add it to the comment list with some marker (or just refresh the story after a couple seconds).  
  - If fails (e.g., network or HN error), show error. 

  Given complexity, commenting can be considered a stretch goal. Upvoting is simpler and likely more commonly desired, so prioritize upvote; commenting can be implemented if time allows or left for a future update.

- **Post-Login UI:** If logged in, show that status in the UI (e.g., in header: “Logged in as [username]”). Enable features like upvote arrows, comment input. If not logged in, hide or disable those interactive elements.

- **Security:**  
  - Never log the password or session cookie. (Loguru logging of HTTP requests should be careful; perhaps avoid logging the actual URL with tokens for upvote/comment, or sanitize them).  
  - The `.env` with credentials is a potential risk if someone gains access to the user’s machine; advise the user to secure it (maybe mention it in README).  
  - If we store the cookie in cache for “remember me” (not planned, but if we did), consider encryption or just re-login each session. Simpler: just perform login each time the app runs if creds are in .env.  
  - All communication is over HTTPS, as we will use HN’s HTTPS URLs and httpx defaults to SSL.

- **Graceful Degradation:** If the user never provides creds or if login fails, the tool should still function fully in read-only mode. So all login-dependent UI elements should either not appear or be inert when not logged in (e.g., don’t show upvote arrows or comment input prompts if no login). Essentially, the default experience remains simple and read-only, which is fine for most users.

### 4.7 **User Interface & Experience Details**

This section covers polish and design aspects (colors, theming, responsiveness). 

We want the interface to be **visually striking** and stand out compared to ordinary CLI tools, providing a delightful user experience through thoughtful design.

- **Look and Feel:** The TUI should feel modern and pleasant:  
  - Use **Rich** styling to add **color** and **formatting** liberally. For example, use orange or bright yellow for titles (to mimic HN’s orange), dim gray for metadata, and perhaps alternating indent colors for nested comments (to visually separate threads).  
  - Use box-drawing characters or subtle lines to separate sections or comments (for instance, a thin line between comments or under the story header). Not too heavy, just enough to structure content.  
  - Utilize full terminal width for content. Wrap text nicely (Rich can handle word wrapping) so we don’t truncate text unless absolutely necessary (like an extremely long word).  
  - Provide a consistent header and footer area: e.g., a header bar with the app name (“Hews”) and current section or story title, and a footer bar with a brief hint of keys (like “↑/↓: navigate, Enter: select, ?: help, q: quit”). Textual has a Header/Footer widget we can use for this purpose.

- **Theming Support:** Not all users have the same preference (dark vs light terminals). Provide at least two themes:  
  - **Dark theme** (default, optimized for dark backgrounds with bright text colors) and **Light theme** (for terminals with light backgrounds). Possibly a third **Monochrome/minimal** theme for no colors (for accessibility or for systems where color might not show).  
  - Implement themes via Textual’s CSS support. We can define CSS classes for UI elements (e.g., `.story-title`, `.metadata`, `.comment`, `.comment.op` for OP comment, etc.) and then have separate CSS files for dark and light that assign different colors.  
  - Alternatively, use a Python dictionary of color codes. But leveraging Textual’s theming might be cleaner: e.g., load `dark.css` or `light.css` based on user preference.  
  - The user can select theme via an environment variable (`HEWS_THEME=light`) or a CLI option (`--theme light`). Even better, allow toggling theme at runtime with a key (maybe `T`). Textual might support reloading CSS on the fly or we can programmatically switch styles.  
  - **Accessibility:** Ensure colors have sufficient contrast. Also consider a `--no-color` mode or auto-detect if output is not a TTY (Rich will drop colors if piping to file automatically). We should ensure our UI still is readable in no-color mode (e.g., maybe using different indentation or symbols since color won’t differentiate). Rich’s auto-detection should handle most of this.

- **Smart Highlights:** We already mentioned highlighting OP’s comments. Other potential highlights:  
  - Highlight **new comments** since last view: if a user opens a story they viewed before and now it has more comments, we could color those new ones differently. This requires storing a timestamp of last view and comparing comment timestamps. This might be overkill for v1, but it’s a nice idea for an enhanced UX.  
  - Any comment by HN moderators or YC staff (hard to detect reliably, not necessary unless there is a known list of such usernames, which we won’t worry about).

- **Responsiveness:** The TUI should adapt to different terminal sizes:  
  - On narrow terminals (< 80 cols), maybe we drop some metadata or truncate more aggressively. Ensure that at least titles are visible in some form. Possibly the layout could switch to single-line per story (title only, with maybe score and comments count on same line truncated). It's acceptable that very narrow terminals result in some info not shown.  
  - On very wide terminals, we could consider multi-column layouts. For example, if width > 120 cols, maybe show the story list in a left column and a preview or the comments in a right column. This is a potential future improvement (we even mentioned two-pane mode in differentiators). For v1, we might keep it single column but just use the extra width for more text.  
  - On tall terminals, obviously more list items or comments can be shown without scrolling. Textual should automatically allow the container to expand.  
  - If the terminal is resized during use, Textual will emit a resize event and re-layout. We should test that the UI reflows correctly (in most cases Textual and Rich handle reflow, but e.g., we might need to recalc some width-based formatting). This should largely “just work” but worth verifying manually.

- **Animations/Feedback:**  
  - Provide loading indicators for actions that take time: e.g., when fetching stories or comments, show a spinner or a message “Loading…”. Rich has spinner animations that can be used, or even just an ASCII spinner in place. Since Textual can run asynchronous tasks, we might, for example, display a spinner widget in the center of the screen while loading comments.  
  - Collapsing/expanding comments could be instantaneous, or we could do a slight animation (like indenting gradually). Textual might not support smooth animations easily, and it's not critical. Instant show/hide is fine.  
  - If an upvote is cast, we might flash a little “[upvoted]” text or briefly highlight the item to acknowledge the action. Similarly for posting a comment. These kinds of micro-feedback help UX.  
  - If we implement a debug log panel (not for end-user, but if dev mode), that could be hidden normally. (Not required for v1, just a thought.)

- **Error Handling in UI:** When errors occur (network down, API returns error, etc.), inform the user in a friendly way:  
  - Use a popup dialog or a message area to show errors like “Network error, please check your connection.”  
  - Do not dump stack traces or Python exceptions to the terminal in normal mode; those should go to the log file.  
  - Provide a way to continue or retry after an error. For example, if the top stories fetch failed, allow the user to hit `r` to retry. If a search fails (e.g., Algolia down), show an error “[Search service unavailable]” and allow them to go back.

- **CLI output mode considerations:** If the user runs with `--print`, we output to stdout and exit, which should be plain text (maybe still with colors if stdout is a terminal). Ensure no interactive control sequences are emitted in this mode. Likely, in `--print` mode, we bypass Textual entirely and just use Rich to print formatted text (Rich will auto-handle whether to use color based on TTY).

- **Performance & UI Responsiveness:**  
  - Because the UI runs in the terminal, blocking operations can freeze the interface. We must ensure that network fetches are `await`ed properly and do not block the event loop. Textual allows running background tasks; we will make use of that. For instance, when a screen is mounted and we start fetching data, we should do it asynchronously and perhaps show a loading message while awaiting.  
  - Large content rendering: if a story has hundreds of comments, adding hundreds of widgets could be slow. We might consider only rendering what's visible, but Textual (especially newer versions) might handle large scrollable lists efficiently. If performance issues arise, we might limit initial rendering to a subset and then add more as the user scrolls (virtual scrolling). However, this is an advanced optimization likely not needed unless we see lag.  
  - Using Rich’s renderables and Textual’s ListView should handle a lot under the hood. We just need to be mindful in Python to not do extremely heavy computations on the main thread (like parsing huge HTML). For example, parsing can be done quickly, but if needed we could offload HTML-to-markdown conversion to a separate thread using `asyncio.to_thread`. 

### 4.8 **Unique Differentiators and Extra Features**

To set *Hews* apart from existing Hacker News CLI tools, we propose some innovative features (some mentioned earlier, but highlighted here):

- **Modern Visual Design:** A core differentiator of *Hews* is its polished and modern interface. Unlike many terminal tools that stick to plain text, this app employs creative layouts, vibrant colors, and even ASCII art elements to make the user interface visually appealing. By leveraging the latest TUI design patterns (thanks to Textual/Rich) and thoughtful aesthetics, *Hews* delivers a terminal experience that feels fresh, engaging, and memorable.

- **Visual Thread Navigation Aids:** Use subtle graphics to illustrate comment threads. For example, draw vertical lines for nested replies to visually connect them. This mimics GUI forum threading in text form and helps users follow deep threads. We’ll ensure these line characters render well in terminals (most support UTF-8 box drawings).

- **Inline Metadata Summaries:** Offer quick info on-demand:  
  - *User info:* The user could press a key (say `i`) when a comment or story author is focused to fetch that user’s profile (karma, join date) via the HN API (`/v0/user/<name>.json`) and display it in a popup. This gives context about the commenter (novice vs veteran user). We can cache user profiles to avoid repeat fetch.  
  - *External link info:* If a story link is highlighted, maybe a key to fetch a one-liner summary or the page title of that link (this might be overkill, but it’s a thought; likely skip for v1). At least showing the domain in the story list covers some of this.  
  - *Thread stats:* At the top of a comments section, we could show an overview like “150 comments (20 top-level, longest thread: 50 replies)”. We can compute that after fetching the comments by traversing the tree. It gives insight like how deep/wide the discussion is. (Nice-to-have).

- **Unique Layouts (Multi-pane):** Consider a dual-pane UI mode:  
  - e.g., Split screen: left side shows the list of stories, right side shows the currently selected story’s content (or comments). This allows browsing and reading simultaneously, similar to email clients or IDEs.  
  - This is advanced to implement (synchronizing selection with what’s displayed on the right, handling focus between panes, etc.). For v1, stick to single pane (one screen at a time). But keep the architecture flexible (Textual’s Layout and Screen management could later allow this). It’s a potential feature to switch into a “preview mode” or “split mode” in future.

- **Comment Filtering/Ordering:** Additional ways to view comments:  
  - Filter: allow the user to press, say, `f` and enter a keyword, then temporarily hide all comments that do not contain that keyword. This can help find specific info in a long thread. We can implement this by traversing the comment tree and marking visible only those that match (and maybe their parents for context).  
  - Sorting: HN comments are naturally in thread order (oldest first in each thread). Sometimes you might want to see newest comments or all comments in flat chronological order. We could provide a toggle to flatten and sort by time, or sort top-level comments by points if we had that (we don’t). Sorting by time could be done by collecting all comments and sorting by timestamp, but then threading is lost. Probably out of scope; filtering is more plausible for v1.

- **Integration with Other Tools:** Make it easy to jump out to external systems if needed:  
  - A key (maybe `O`) to open the current story or HN page in a web browser (we already have story link opening).  
  - A key to copy the story or comment URL to clipboard (on macOS we could pipe to `pbcopy`, on Linux maybe use `xclip` if available, but this gets environment-specific). Possibly not do this by default, but could mention as an idea.  
  - If we wanted, we could allow saving a story or comment to a text file via a command, but the user can always copy from terminal or rely on HN bookmarks.

- **Logging & Debug Mode:** For development and support, using **Loguru** allows us to provide a debug log file. This is not a user feature per se, but it differentiates in terms of maintainability: if a user encounters a bug, they can send the `hews.log` file. We plan to log extensive debug info (when debug enabled) like all API calls, cache hits, etc.. Normal mode will only log warnings/errors to keep size small. This approach makes troubleshooting easier compared to a tool that prints minimal info.

In summary, these differentiators aim to make *Hews* more than a basic HN reader by providing a rich, enjoyable terminal experience:

- A **visually appealing TUI** with colors, banners, and graphical thread indicators.  
- Quick access to extra info (user profiles, etc.) to enrich the reading experience.  
- Efficient search and offline capabilities combined (many tools have either search or offline, few have both).  
- Customizability with themes.  
- Developer-friendly touches like logging and potential future extensibility.

We ensure these ideas are documented so they can be implemented either in v1 or in future versions as enhancements.

## 5. **Technical Design and Architecture**

This section outlines how to structure the code and how data flows through the system, to guide the developer in implementing the features above in a clean, maintainable way.

### 5.1 **Technology Stack and Libraries**

Our tool will be built entirely in Python (3.12+) with these major libraries:

- **Textual** – Framework for building the Terminal UI. We’ll create a subclass of `textual.app.App` for the application, utilize Textual widgets (Header, Footer, Panels, etc.) for layout, and take advantage of its async event loop integration. Textual uses **Rich** for rendering, so we get styling and layout capabilities with it.

- **Rich** – Used directly for things like formatting text (colored strings, maybe rendering markdown for story text, creating the ASCII banner, etc.). Rich complements Textual by providing pretty printing and styling in the console.

- **Click** – For CLI argument parsing. We’ll implement a `cli.py` that defines commands/options and invokes the appropriate mode (interactive TUI or print mode). Click will also handle the `--help` text generation.

- **httpx** – For all HTTP requests (to HN API, Algolia, and HN website for login/upvote). We will use `httpx.AsyncClient` for async calls to fetch multiple endpoints in parallel. We can set a global timeout and handle exceptions gracefully. HTTPX also supports persistent sessions and cookies, which we need for login.

- **python-dotenv** – To load environment variables from a `.env` file at startup. This will allow user credentials and configuration (like theme) to be set without hardcoding. We call `dotenv.load_dotenv()` early on.

- **Loguru** – For logging. We’ll initialize logging in the CLI entrypoint. For example, log to a file in the cache directory (e.g., `~/.cache/hews/hews.log`). Use an appropriate log level (INFO by default, DEBUG if an env var is set). We’ll sprinkle logging statements in the code to track key events (fetches, user actions, errors). Loguru simplifies logging (no boilerplate for logger instances).

- **uv (Astral)** – For package management and setting up the project. This doesn’t affect runtime, but we note it’s used to manage dependencies (i.e., the developer will use `uv` to add packages and create the lockfile).

- **SQLite3** – (Standard library) for caching if we go with SQLite. We might also consider using a small ORM or query builder, but likely the standard `sqlite3` module is fine. Alternatively, use simple file I/O if not using SQLite.

- **pyfiglet or Rich text** – (Optional) for the ASCII banner generation at startup. We can either include `pyfiglet` to generate ASCII art text, or use Rich’s text styling with big fonts if available. `pyfiglet` is small and can be added if needed.

All these libraries work on Python 3.12. We will use **type hints** extensively (PEP 484) to make the code easier to navigate and to catch errors with static checkers. (We may also set up `mypy` in CI to enforce this).

We should also consider using `pytest` and other dev tools, but that’s covered in the testing section.

### 5.2 **High-Level Architecture and Data Flow**

We will structure the project in layers/modules for clarity:

1. **CLI Layer (Entry Point):**  
   - File: `cli.py` (for example). This uses Click to define commands and options.  
   - Functionality: Parse `sys.argv` inputs and then either start the TUI or handle non-interactive tasks.  
   - Process: 
     - Load environment variables (via dotenv). 
     - Configure logging (e.g., `logger.add("hews.log", level=INFO)`).
     - Initialize core components (like instantiate the HN API client).
     - If `--print` mode or other direct query, perform that action (e.g., fetch data and print).
     - Otherwise, launch the Textual app (pass initial parameters like a search query if provided).  
   - Click could define subcommands too (e.g., `hews search <query>` as an alternative to `--search`). But either approach is fine.

2. **Core Logic / Backend:**  
   - This includes the Hacker News API client and caching subsystem, which are independent of the UI.  
   - Class **HNClient** (in `hnapi.py` or similar): Encapsulates all data fetching and actions:  
     - Holds an `httpx.AsyncClient` (perhaps created with `base_url="https://hacker-news.firebaseio.com/v0/"` for convenience with official API). Also possibly an `httpx.Client` (sync) for login if we do that outside async context, or we use AsyncClient for login as well via `.post`.  
     - Methods: 
       - `async fetch_stories(section)` – Given a section name ("top", "new", etc.), fetch IDs and then fetch each story item. Return a list of Story objects (or dicts). Possibly accept a `limit` parameter.  
       - `async fetch_item(id)` – Fetch a single item (story or comment) by ID from the official API. Return a Story or Comment object. This would be used recursively for comments or on-demand loads.  
       - `async search(query)` – Call Algolia API and return list of Story objects (or at least basic info objects). Could also return a lightweight representation since Algolia results may not have full story text. We might decide to not fully construct Story objects for search results, and instead just store what we have; then fetch detail when opened. Either way.  
       - `login(username, password)` – Perform login (could be async or sync; if using AsyncClient, we can do `await client.post(...)`). After login, the client’s cookie jar is set. We might not need this to be async if we call it at startup; but using async is fine.  
       - `upvote(item_id)` – Perform an upvote. This might need the item’s `auth` token, so perhaps `HNClient` should have a method to get that token (maybe a method like `get_upvote_token(item_id)` which fetches the item HTML page). Or we pass in something like the item type (story or comment). Implementation detail. But the method will GET the vote URL and return success/failure.  
       - `post_comment(parent_id, text)` – Post a comment/reply. Similar needing a token from the parent’s page. 
       - Possibly methods to fetch user profiles (`get_user(username)`).

     - Internally, **HNClient** uses the **Cache**: 
       - It might accept a CacheManager instance in its constructor, or create one. 
       - Before making a network call, check cache (if caching is enabled for that call). E.g., in `fetch_item`, first see if cache has that item and is fresh. If yes, return cached data; if no, fetch and then save to cache. 
       - The HNClient can be a singleton (we instantiate one and use it globally, as it holds state like login session and caches).

   - **CacheManager** (in `cache.py`): 
     - If using SQLite: open a connection to `cache.db`. Ensure tables exist (create if not). Provide methods like `get_story(id)`, `save_story(story_obj)`, `get_comments(story_id)`, `save_comments(story_id, comments_list)` etc. 
     - For simplicity, perhaps one generic `get_item(id)` and `save_item(item)` where item could be story or comment, identified by type in the data. We can have one table for all items or separate tables. 
     - If implementing FTS, set up an FTS virtual table and update it on save. 
     - If not using SQLite, CacheManager could just keep a dict in memory and optionally flush to disk as JSON. But that loses persistence across runs unless we write to disk. SQLite seems more robust. 
     - Ensure thread-safety if needed (but if everything is happening in one async loop, we are okay; if we might access the cache from different threads for any reason, we’d need to guard or use a separate connection per thread).

   - **Data Models:** 
     - Define dataclasses for Story and Comment (and possibly User). This makes it easier to work with structured data rather than raw dicts. 
     - `Story` fields: id (int), title (str), url (str or None), text (str or None), points (int), author (str), time (int or datetime), descendants (int), kids (List[int] of comment IDs). Possibly a field for comment objects if we load them, but we might not store that in the story object itself to avoid recursion issues; instead handle comments separately. 
     - `Comment` fields: id, author, text, time, parent (int), kids (List[int]). Possibly a boolean for deleted/dead. 
     - Provide factory methods or constructors to create these from the API JSON (the official API returns a JSON with fields like `by`, `text`, etc., which can map directly). 
     - We might not strictly need dataclasses, but they help with type hints and readability. 
     - These models can also include convenience methods, like `Story.age()` to return a human-readable age, or `Comment.is_deleted()`. They can also be used for caching (store them via pickling or JSON if needed).

   - These core components (HNClient and CacheManager) should be usable independently of the UI. This separation ensures easier testing (we can test HNClient with dummy HTTP responses, test CacheManager with a temp DB, etc.).

3. **UI Layer:**  
   - We use **Textual** to build the UI. Plan a few key classes:  
     - `HewsApp` (subclass of `textual.app.App`): The main application controller.  
       - It sets up the overall structure and contains logic to switch between screens, handle global keys, and load theme CSS.  
       - On start (`on_mount` or `on_start`), it might attempt login (if creds provided) by calling `await hn_client.login()` so that’s done before any UI requiring login.  
       - It should push the initial screen (StoryListScreen for a section, or SearchScreen if a search query was provided via CLI). It might take parameters like `initial_section` or `initial_search` (passed from CLI).  
       - Manage a reference to `hn_client` (so that screens can call it, or we pass the client to screens). Possibly store the client in `self.client` or make it globally accessible (perhaps the simpler is to have it as a global or a singleton that UI can import, but dependency injection is cleaner).  
       - Handle theme: before running, decide which CSS to load (if theme specified in env or CLI). Use `self.load_css(path)` or similar Textual method to load the appropriate stylesheet.  
       - Define key bindings: e.g., in Textual you can set `BINDINGS = [("q", "quit", "Quit"), ("?", "toggle_help", "Help")]` which automatically associates keys with action methods. This can cover global keys like quit and toggling help overlay.  
       - It can also contain a help overlay widget that can be shown/hidden.  
     
     - **Screens**:  
       - `StoryListScreen`: Shows the list of stories for a given section or search results. 
         - Likely takes an argument on init, e.g., `section="top"` or `search_query="something"`. 
         - In `on_mount`, trigger data load: 
           ```python
           if self.section:
               stories = await app.hn_client.fetch_stories(self.section)
           elif self.search_query:
               stories = await app.hn_client.search(self.search_query)
           ``` 
           Then populate the list.  
         - Use a Textual `ListView` or `DataTable` for the list of stories. Possibly `ListView` with custom `ListItem` widgets for each story entry (so we can format multi-line). Each `ListItem` could contain a Rich rendered text or a small layout of two lines.  
         - Handle events: arrow keys and enter to select (Textual might handle basic up/down navigation in ListView). On Enter, call `self.app.push_screen(CommentsScreen(story=selected_story))`. Also handle the number keys or section switch keys to quickly change section (that could either be handled here or at the app level globally). If user presses `/`, we could either handle it here by pushing a Search input modal, or allow the App to catch it and push a SearchScreen. Implementation choice.  
         - If we implement continuous scroll for more stories: detect if selection goes beyond current loaded list (need to handle that event to fetch more). If we use `ListView`, maybe hooking on reaching end-of-list event. For v1, maybe not needed if we load enough items up front or keep it manual via a key.
         - The StoryListScreen might also own the logic for refreshing (if `r` pressed, call fetch_stories again and update list).

       - `CommentsScreen`: Shows the story detail and comments thread.
         - Init with a Story object or story_id. Possibly if we only have an ID (like from a search result which had partial data), we may need to fetch the story first. 
         - In `on_mount`, ensure story data is loaded (if we got a Story object passed, use it; if just an id, call `await hn_client.fetch_item(id)` to get story).
         - Display story header (title, metadata, text if any) at the top. Could be a simple `Static` widget with Rich text, or a small layout (maybe a `Header` widget re-purposed to show story title? But likely custom to include the metadata nicely).
         - Then display comments. We can either:
           - Use a scrollable container and manually add comment widgets (with indentation).
           - Or create a custom `CommentTree` widget that manages its children. But probably easier: for each top-level comment, create a `CommentWidget` (which includes its text and an indicator if it has kids). Add all top-level comment widgets to a vertical layout or ScrollView.
         - Each `CommentWidget` can contain the rendered text of the comment plus perhaps a prefix for collapse/expand (like a `[+]` that we can highlight when focused). 
         - We need to handle input: when a CommentWidget is focused and user presses Right/Enter, call something like `toggle()` on that widget to show or hide replies.
         - If showing replies, and they haven’t been loaded yet, fetch them via hn_client (this might happen in the toggle method or via an event the CommentsScreen listens to).
         - Navigation: possibly rely on Textual’s focus mechanism to move between widgets (Tab order might go in sequence, but up/down arrow might need custom handling to focus previous/next comment widget). Alternatively, maybe we avoid individual focus on every comment and instead have one big Text widget where we can’t individually select comments (but then we can’t collapse easily). So likely individual focusable comment entries is needed.
         - If `u` (upvote) is pressed, decide if it's on the story or a comment based on focus. Perhaps we allow focus on the story header too (maybe the story title at top can be focusable, so pressing `u` there upvotes the story; if focus on a comment, upvote that comment).
         - If `c` (comment) pressed, handle accordingly (maybe open input for new comment).
         - `b` or Left key to go back (pop screen).

       - `SearchScreen`: Alternatively, we might incorporate search results into the StoryListScreen class (just with a different parameter). But we could also separate it for clarity. However, they’re similar in UI (a list of stories). So maybe one class StoryListScreen that handles both use cases by checking if `self.search_query` is set. That might be simpler than a whole separate screen type.

       - Possibly a `HelpScreen` or overlay widget. Textual can layer widgets on top without changing screen. Simpler: we could implement help as a modal dialog that is triggered by `?`. This could just be a big text panel listing controls, which the user closes with any key.

   - **Design Decision:** Screens vs dynamic content in one screen: Textual encourages separate Screen classes for distinct views. Here, StoryList vs Comments are clearly separate states, so screens are appropriate. We push CommentsScreen on stack and pop it to return.

   - **Widgets:**  
     - We might have custom widget classes like `StoryListItem` (subclass of `ListItem` or `Static`) to format a story entry. It might store a reference to the Story object for when it’s selected.  
     - `CommentWidget`: to represent an individual comment and its children. Fields: comment data (author, text, etc.), a flag for expanded/collapsed, child CommentWidgets if any. If collapsed, children are not in the layout; if expanded, children are inserted after this widget. It might manage its own indentation (maybe the widget’s `indent` property or just prefix spaces in the text).
     - We will need to reflow the comments when a collapse/expand happens (i.e., removing or adding widgets to the ScrollView). Textual’s layout should update accordingly. We just must ensure to update focus if needed (e.g., if collapsing, ensure focus doesn’t jump to a now-nonexistent widget weirdly).

   - **Event flow:**  
     - HewsApp will catch global key events or actions (like quit or help). 
     - StoryListScreen catches events specific to story list (like opening a story, switching section). 
     - CommentsScreen catches events in comments view (like expanding, going back, upvote, reply). 
     - We can also use Textual message passing: for instance, a CommentWidget could emit an event to the CommentsScreen when it needs to load children (so CommentsScreen then fetches via HNClient and sends data back to CommentWidget). But that might be over-engineering; perhaps CommentWidget directly calls HNClient if it has access. Might be okay for it to call a global client or a passed reference.

   - **Integration with Data Layer:** 
     - We ensure HNClient is accessible wherever needed. Could store it in the App (HewsApp.hn_client). Then a screen can do `self.app.hn_client.fetch_stories(...)`. This is likely easiest. 
     - The screens should await these calls. Textual supports `on_mount` being async to allow initial data load. Also, actions triggered later (like expanding a comment) may need to run async tasks; Textual has mechanisms (like `create_task` or using the message loop to run an async function and then update UI).

   - **Error Handling:** 
     - The HNClient should raise exceptions or return error statuses, which screens should handle to show messages. For example, if fetch_stories fails due to network, HNClient could raise a custom `NetworkError`. The StoryListScreen would catch that and perhaps call a method to display an error popup. 
     - We might implement an `ErrorPopup` widget that can be summoned with a message. The App could manage a global one (like, call `self.app.show_error("message")` that adds the popup widget).

   - **Login Integration:** 
     - If creds in env, we do login at startup (before showing story list). If login fails, perhaps log it and continue (with user not logged in). If success, HNClient is now authenticated. 
     - We might not implement an interactive login screen, but if we did, it could be a simple input form that appears if user tries an auth action when not logged in. Given time constraints, .env-based login is fine.

   - **Themes Implementation:** 
     - We prepare CSS files, e.g., `dark.css` and `light.css`, in a `themes/` folder. 
     - Example (dark theme snippet). Light theme would invert some colors. 
     - Load the chosen CSS in HewsApp (Textual’s `add_stylesheet` or `load_css`). 
     - Ensure our widgets have the appropriate class names set. For instance, when creating the title Text, we might do something like `title_text.stylize("class:story-title")`. Or use Textual’s ability to set class on a widget (e.g., `CommentWidget` could have classes based on state like "comment deleted", etc., and the CSS can target `.comment.deleted`). 
     - This separation of style is great for maintainability and allows theme switching by loading a different stylesheet.

   - **Modularity:** 
     - The UI should be separate from logic so we could test logic without running the UI (for example, we can test HNClient and Cache alone). 
     - We could also consider a mode to run the app without curses (we have `--print` for that, which essentially bypasses the UI and directly uses logic). 
     - We should avoid deeply coupling UI and data. For instance, do not fetch data in the middle of render logic without going through HNClient, so it can be swapped in tests or replaced with a dummy.

   - We should maintain readability in code: e.g., break up the UI code into multiple files or classes logically, rather than one giant file.

### 5.3 **Class and Module Breakdown**

**Proposed module structure and key classes:**

- **`cli.py`:**  
  - Contains the entrypoint function (which Click will use).  
  - Defines CLI options: `--section`, `--story`, `--search`, `--print`, etc.  
  - On execution, does `load_dotenv()`, sets up logging.  
  - Depending on options:
    - If `--print`: calls appropriate HNClient method and prints output using Rich (formatted similar to the TUI but static). Then exits.  
    - Otherwise: creates an instance of HewsApp (passing initial_section or search query) and calls `app.run()`. (Textual’s App.run starts the event loop).  
  - If needed, handle Ctrl+C or graceful exit (Textual might handle that itself). 

- **`hnapi.py`:** (Hacker News API client and data handling)  
  - `class HNClient`: as described above.  
    - Attributes: `async_client` (httpx.AsyncClient), possibly `sync_client` or reuse async for login, `cache` (CacheManager), `logged_in` (bool), `user` (username or user object if logged in).  
    - Implement methods: `fetch_stories(section)`, `fetch_item(id)`, `search(query)`, `login(user, pw)`, `upvote(id)`, `post_comment(parent, text)`.  
    - Internally uses `await async_client.get()` or `.post()` as needed.  
    - Use cache: e.g., `fetch_item` might do: `if cache.has(id): return cache.get(id)` (if fresh) else fetch and then `cache.put(item)`.  
    - It should handle exceptions (httpx might throw RequestError, etc.). Perhaps catch and raise our own exception types like `NetworkError`. Or just let them bubble and handle in UI. Either way, document what it does.  
    - Could include helper like `_get_item_url(id)` returning f"{base_url}item/{id}.json", etc., or use httpx.BaseURL as noted.  
    - For login/upvote, might use `self.sync_client` if easier to handle cookies (httpx AsyncClient can maintain cookies too, so we could stick to async all the way and just `await async_client.post(login_url)` etc.).  

  - `class CacheManager`:  
    - If SQLite: open connection in __init__, and perhaps set row_factory to sqlite3.Row for convenience.  
    - Methods: `get_story(id)` returns a Story or None; `get_comment(id)` similarly or a generic `get_item(id)`. `save_story(story)` inserts or replaces into DB. Could also have `get_top_stories(section)` if we store the list of IDs for sections, but easier might be to always fetch those from network (they’re quick). Or we could cache the list of IDs too.  
    - Possibly `clear_old()` to prune stale entries, if implementing expiry. Or simply always overwrite on new fetch.  
    - If not using SQLite, then perhaps using a dictionary and writing out to a JSON file on disk occasionally. But let’s assume SQLite for robustness.

  - Data models can live here or in a separate `models.py`. E.g., 
    - `@dataclass class Story`, `@dataclass class Comment`, etc.  
    - They help with type hints and can have methods for printing or computing age (though printing logic might belong in UI, maybe provide a formatted timestamp property here and let UI use it).

- **`ui/` package or `ui.py`:**  
  - If it gets large, a package with multiple modules: e.g., `ui/app.py` for HewsApp, `ui/screens.py` for screens, `ui/widgets.py` for custom widgets. Or keep it in a single file if manageable. 
  - `class HewsApp(App)`:  
    - Possibly set `CSS_PATH = "themes/dark.css"` or dynamically load. If Textual requires specifying CSS beforehand, might need to override App.load_css based on env.  
    - Define `BINDINGS = [("q", "quit", "Quit"), ("?", "toggle_help", "Help")]` for global keys. 
    - Attributes: `hn_client` (the instance created in cli and passed in, or created inside App). Perhaps we can pass it via `app = HewsApp(hn_client=client, initial_section=..., initial_search=...)`. 
    - Methods: `on_mount` (async) – can do login if needed (`if credentials provided and not logged_in: await self.hn_client.login()`). Then push initial screen (`await self.push_screen(StoryListScreen(...))`). 
    - Action methods corresponding to bindings: `action_quit` to exit (perhaps confirm or just exit), `action_toggle_help` to show/hide help. 
    - A container or layer for help overlay (maybe create it once hidden). 
    - Possibly handle theme switching action if we allow it (like `action_toggle_theme` to swap CSS).

  - `class StoryListScreen(Screen)`:  
    - Attributes: `section` (str or None), `search_query` (str or None). Possibly also store `stories` list if needed. 
    - In `on_mount` (async): 
      - If section specified, set a status like "Loading stories..." (maybe update a status widget), then `stories = await self.app.hn_client.fetch_stories(section)`. 
      - If search_query, similar call to search. 
      - If this fails, catch and maybe show an error (like create an error popup or set a message in place of the list). If success, populate the list. 
    - UI layout: Could override `compose()` to create a vertical list. Textual 0.10+ has `ListView` which simplifies handling selectable list items. We can do:
      ```python
      def compose(self):
          yield ListView(id="stories")
      ```
      And later populate that ListView by doing:
      ```python
      list_view = self.query_one("#stories", ListView)
      for story in stories:
          item_text = ...  # format with Rich
          list_view.append(ListItem(Static(item_text), id=str(story.id)))
      ```
      Or something along those lines. 
      - Alternatively, use a `DataTable` which can have columns, but our data is multi-line. ListView is more suited. 
    - Event handling: 
      - Textual ListView might emit an event like `on_list_view_selected` when an item is selected (if using arrow keys). Or we handle key events:
        * On Enter: get the selected item’s id (we stored it) and then `self.app.push_screen(CommentsScreen(story_id=... or story=obj))`. We likely have the Story object in a list parallel to the ListView. Could store it in the ListItem via an attribute or use the item id to look it up in a dict.
      - On pressing section switch keys (t, n, etc.): We could either handle in App (like global key bindings for 1-5 to switch screens), or handle here by replacing the content. Possibly easier: if user presses e.g. 'n' for new, we could simply call `await self.app.hn_client.fetch_stories("new")` and update the same screen’s list rather than creating a new screen. That might flicker less and reuse the view. Or we push a new StoryListScreen for that section. Either way. Since switching sections is a core navigation, maybe one StoryListScreen that dynamically loads different sections might be fine. But separate screens could also be fine. 
      - If refresh key `r`: re-fetch current section and update list.

  - `class CommentsScreen(Screen)`:  
    - Attribute: `story` (Story object or minimal info). Or we pass story_id and CommentsScreen will fetch story & comments. If the Story object from list has kids list, we might need to fetch comments anyway individually (the official API doesn’t give comment text in the story object, just IDs). So CommentsScreen will definitely be fetching comment details. Possibly fetch story again too to ensure updated points count, but not necessary if story was passed in.
    - `on_mount` (async):
      - If `self.story` is just an ID or has no comments loaded, do: `await self.app.hn_client.fetch_item(story_id)` to get story (with its text maybe) and then for each top-level comment id in story.kids, `await self.app.hn_client.fetch_item(comment_id)` or provide a method to batch fetch them. Possibly HNClient could have `fetch_comments(story_id)` that returns all top-level Comment objects and maybe one level of replies? But simpler: loop through kids and fetch each comment concurrently (gather tasks).
      - Once have top-level comments, create CommentWidgets for each and add to layout.
    - Layout:
      - Perhaps use a `ScrollView` that contains:
        - A Static for story title & metadata (maybe styled differently).
        - A Static for story text if exists (with some padding or separator).
        - Then comment widgets (each possibly a Static or Container).
      - Or possibly separate the story header in a fixed panel and comments in a ScrollView below. But fixed header might be tricky if window resizes or if the story text is very long (then it should scroll too). Probably easier: let everything scroll together.
      - We can visually separate story content and comments with a line or a blank line.
    - Event handling:
      - Up/Down arrow: move focus between comments. We might implement focus by making each CommentWidget focusable (maybe each one is a Static that can receive focus). Alternatively, capture up/down in CommentsScreen and manage an index of which comment is "selected" (since visually focus might just be a highlight or arrow next to it).
      - Expand/Collapse: Right arrow or Enter on a focused comment toggles. If toggling to expand:
        * If children not loaded, fetch them (maybe the CommentWidget will call HNClient for its kids).
        * Insert child CommentWidgets right after the parent in the ScrollView (maintain indentation).
      - Possibly handle left arrow to collapse as well.
      - `b` or left arrow when at top-level (or if nothing focused) means go back: `self.app.pop_screen()`.
      - `u` for upvote: 
        * If focus is on a comment: call `await self.app.hn_client.upvote(comment.id)`. If success, maybe add a small "[upvoted]" note or simply log it. The HN site doesn’t give immediate points, and we don’t display points for comments, so just a subtle confirmation is fine. 
        * If focus is on story (maybe if we allow focusing the title), upvote story: call upvote and increment points in UI or mark it.
      - `c` for commenting: 
        * If focus on story: open an input to add a top-level comment.
        * If on a comment: input to reply to that comment.
        * This could be a modal text input widget. Textual has an Input widget we can use. We may need to capture multiline input. We could accept input until user presses Esc or a send key.
        * Once text is captured, call `await hn_client.post_comment(parent_id, text)`. On success, perhaps immediately reflect it by creating a new CommentWidget for that comment and adding to UI. Or simpler: after posting, just refresh the comments by re-fetching story comments (the new comment might not appear via official API immediately, but presumably once HN returns 200 OK to the post, the comment is there).
        * We’ll consider this optional given complexity.

- **`themes/`:**  
  - `dark.css`, `light.css` etc., containing style definitions for classes. This allows easy tuning of colors. These are not Python files but part of the project package data.

Summarizing classes:

- *CLI layer:* `cli.py -> main()`
- *Core layer:* `HNClient`, `CacheManager`, `Story`, `Comment`
- *UI layer:* `HewsApp`, `StoryListScreen`, `CommentsScreen`, `CommentWidget`, possibly `StoryListItem`, etc.

We will ensure that each component has clear responsibilities, and we avoid duplication (e.g., the logic to format a story entry for display should ideally be in one place, not repeated in print mode and TUI mode separately – perhaps have a helper function or reuse Rich formatting code in both contexts).

### 5.4 **Data Flow Examples**

Let’s trace a couple of typical flows to illustrate interactions between components:

- **Flow: Launch app and view Top Stories**  
  1. User runs `hews` with no args.  
  2. In `cli.py`, `load_dotenv()` loads environment variables (say user had none or some for login).  
  3. `cli.py` creates `client = HNClient()` (which internally might create httpx client and cache). If `HN_USERNAME` in env, calls `await client.login(user, pass)`.  
     - Suppose login succeeds (if creds provided) – now `client.logged_in=True`.  
  4. `cli.py` then does `app = HewsApp(hn_client=client, initial_section="top")` and `app.run()`.  
  5. HewsApp.on_start: 
     - Perhaps already logged in from step 3, so skip additional login. 
     - It loads theme (default dark) from file. 
     - `self.push_screen(StoryListScreen(section="top"))`.  
  6. StoryListScreen.on_mount: 
     - It calls `stories = await self.app.hn_client.fetch_stories("top")`. 
       * HNClient.fetch_stories: 
         + Makes GET request to `/v0/topstories.json`, gets list of top IDs. 
         + For first ~30 IDs, in parallel, GET `/v0/item/<id>.json` for each. Uses asyncio.gather to do concurrently. 
         + Parse each JSON into a Story object, store in list. 
         + Maybe also save each to cache via CacheManager. 
         + Return list of Story objects. 
       * If the HN API was slow or fails for one item, handle accordingly (maybe skip that item or try sequential fallback). 
     - Once returned, the StoryListScreen builds the list view with these stories. 
     - It displays them. Possibly the app header shows "Top Stories". 
  7. User sees list almost immediately (target ~1 second if all goes well for 30 items). 
     - If we implemented ASCII banner, maybe that showed for a split second at startup or is part of header. But anyway.
  8. User scrolls with arrow keys: Textual ListView highlights selection, no network activity here. 
  9. User presses Enter on a story (say story with id 12345): 
     - StoryListScreen catches Enter, finds selected story. We have either the Story object or at least its id. 
     - It does `self.app.push_screen(CommentsScreen(story=selected_story))`. 
  10. Textual pushes CommentsScreen on top of StoryListScreen (which might still be in memory for back navigation). 
  11. CommentsScreen.on_mount: 
      - It sees it has a Story object passed (from earlier fetch). If that Story has a `kids` list of comment IDs, it will proceed to fetch comments. 
      - It calls for each top-level comment id in story.kids: `comment_objs = await asyncio.gather(*[self.app.hn_client.fetch_item(id) for id in story.kids])`. 
      - HNClient.fetch_item for a comment id: 
        * Checks cache, if not present, GET `/v0/item/<id>.json`. That returns comment JSON with text, by, kids, etc. 
        * Makes a Comment object and returns. Also caches it. 
      - Once CommentsScreen has top-level comments list, it creates CommentWidgets for each and adds to ScrollView. By default, it might not fetch replies of replies yet (we decided on-demand deeper). 
      - However, we might choose to prefetch one level deeper to show a bit more on initial load. Perhaps not, to avoid too many requests. 
      - The story header (title, link) is displayed at top of this screen. 
  12. User now sees the story title and first-level comments (comments might be initially expanded or we decided to collapse replies beyond top-level). Let's say we decided top-level comments shown, replies collapsed. So each top-level comment with replies has a “[+]  (10 replies)” indicator or something. 
  13. User navigates comments: arrow down moves to next comment, etc. 
  14. User presses Right on a comment with “[+]”: 
      - CommentsScreen catches that, or the CommentWidget itself handles it:
        * If CommentWidget handles, it calls `if not loaded_children: children = await self.app.hn_client.fetch_item(child_id) for each child_id` (or perhaps HNClient has a method to fetch a list of ids). 
        * It creates child CommentWidgets (indent level+1) and inserts them in the ScrollView right after this parent. 
        * It changes its indicator to “[-]”. 
      - The UI updates to show those replies. 
  15. User can continue expanding deeper as needed, triggering more fetches on demand. All these get cached, so if user collapses and expands again, no new request. 
  16. If user hits `u` to upvote a comment:
      - If logged in (from step 3), then:
        * CommentsScreen calls `await self.app.hn_client.upvote(comment_id)`. 
        * HNClient.upvote: 
          + If we have not gotten the upvote token: might fetch the story’s HTML from news.ycombinator.com (or perhaps we fetched it on CommentsScreen mount as a side effect, which could be an optimization – e.g., fetch story HTML when we fetched API data, to have tokens for all comments; but that’s a lot of HTML scraping).
          + Let’s assume a simple approach: upon first upvote action, HNClient does:
            - GET `https://news.ycombinator.com/item?id=12345` (the story’s HTML page).
            - Parse it (maybe using BeautifulSoup or even regex) to find the vote link for the item with id equal to the target comment or story. These links look like `<a id="up_12345" href="vote?id=12345&how=up&auth=...&goto=item?id=12345">`.
            - Extract `auth` token. 
            - Then GET `https://news.ycombinator.com/vote?id=12345&how=up&auth=<token>&goto=item?id=12345` with the session cookie.
            - If 200 OK (or redirect to item page), consider it success.
          + This is a bit heavy but doable. Ideally, to avoid parsing each time, we could parse once and store tokens for each visible item. Or simpler: fetch story page and use it for story upvote and perhaps top-level comments, but for nested comments you'd have to scroll the HTML too. Possibly easiest is to fetch the item page each time we upvote a comment to get its specific token (but that's multiple requests). There's room for optimizing or using an unofficial API, but we'll not over-optimize in the PRD; say we do straightforward method.
        * If upvote success, we update UI (maybe change comment author text color or put a small "▲" next to it indicating user upvoted).
      - If not logged in (shouldn’t be in this case because we logged in), but if they weren’t, we’d prompt login.

  17. User finishes reading, presses `b` to go back. Textual pops CommentsScreen, returning to StoryListScreen with the same scroll position and highlighted story. 
  18. User can then press `q` to quit the app. App closes, returning to shell.

- **Flow: Search**  
  1. Starting from top stories list (or if launched with `--search` it would start differently): user presses `/`. 
  2. We could handle this by either directly using an Input widget on the StoryListScreen (like open a small prompt). Possibly easier: push a transient screen or overlay that is basically a full-screen or centered modal with an Input asking “Search query:”. But maybe just an overlay at bottom. 
  3. User types “Python” and presses Enter. We capture that and then push a new StoryListScreen with `search_query="Python"`. (Alternatively, we could reuse the current StoryListScreen and just load search results into it, but might be simpler to push a new screen so that the user can press back to return to the previous view if desired. But maybe back from search goes to previous list; that could be nice. Possibly just reusing the same screen instance but with different data might complicate back behavior. Instead, treat search results as another screen on stack.)
  4. The Search StoryListScreen calls `await hn_client.search("Python")`. 
     - HNClient.search does one GET to Algolia API, gets JSON of hits. 
     - Parse hits to Story objects (or at least stub objects). Possibly get 20 hits by default.
     - No caching needed unless we wanted to store searches (we likely won’t cache search results, but we might individually cache any story IDs that appear).
  5. Display the search results in a list (UI similar to top stories list). Possibly show a header like “Search results for 'Python'”. 
  6. User selects a result, presses Enter. It pushes CommentsScreen just like before. The flow for comments is identical: fetch via official API etc., because Algolia gave us just enough to list, we still use the id to get full details.
  7. Back from comments goes to search results, back again could go to the top stories (depending how we manage screen stack; if we pushed search screen on top of top, then yes back pops to top stories).

- **Flow: Offline usage** (suppose user has run it before, so some cache exists):  
  1. User runs `hews` while offline (no network). 
  2. In CLI, `hn_client.fetch_stories("top")` will try network, which will raise an exception (RequestError). HNClient could catch this and either:
     - If cache has that section’s data, return cached stories (even if stale). But we probably didn’t store section listing separately. More likely: HNClient throws, and StoryListScreen catches.
  3. StoryListScreen, on exception, can detect offline scenario. It could then try to load some cached data:
     - Maybe CacheManager could have a method to get the most recently cached stories from that section (if we had cached it explicitly, which we might not unless we store section info).
     - Alternatively, if our cache just has story items from previous runs, we could still show something: perhaps the last 30 stories that were fetched for Top (if we kept track).
     - For simplicity, let’s assume we did store the last fetched list of top IDs and their data in cache.
  4. So offline, we populate list from cache (but mark in header “Offline”). 
  5. If user tries to open a story that wasn’t cached (like one that wasn’t opened before and not in the top list if that list was cached partially), then HNClient.fetch_item will fail (no network). If not in cache, we show error “[Not available offline]”. 
  6. Ideally, the UI would prevent selecting such a story or indicate it's not cached. Possibly simpler: if user selects a story and we have it cached (from list data we do have title etc., but we might not have comments), we can show what we have: maybe title and whatever, and say "comments not available offline".
  7. These details can get complex, but the key is not crashing and informing the user gracefully.

### 5.5 **Logging and Error Handling**

Throughout the app, we will use **Loguru** to capture events and errors:

- **Configuration:** In `cli.py`, after loading env, do something like:  
  ```python
  logger.remove()  # remove default stderr logger  
  log_path = Path("~/.cache/hews/hews.log").expanduser()  
  logger.add(log_path, rotation="1 week", retention="1 month", level="DEBUG" if DEBUG else "INFO")  
  ```  
  This way we have a file log. We might also leave a stderr logger at WARNING level so that serious errors print to console in red, but that might conflict with our UI, so maybe not in TUI mode. Possibly only in print mode or for CLI errors we allow stderr logging. In TUI mode, we don't want random log output messing the UI.

- **Logging Use Cases:**  
  - At startup, log version and startup arguments. 
  - After fetching stories or comments, log how many items fetched and how long it took (could time it).  
  - On cache usage, log whether it was a cache hit or miss for each item (in DEBUG mode). e.g., "Cache miss for item 12345, fetching from API" or "Cache hit for item 67890".  
  - On errors/exceptions, log stack trace to file (Loguru will do this if an exception is not caught, but we aim to catch and handle gracefully; still, we can log the error details).  
  - On user actions: maybe log "User upvoted story 12345" or "User opened search 'Python'".

- **Error Handling Strategy:**  
  - At the network layer, any failure to reach the API should be caught and not crash the program. e.g., HNClient.fetch_stories should ideally catch httpx.RequestError and raise a custom error or return an empty result with an error indicator.
  - In UI, we show a message and allow user to retry or go back.  
  - Example: if `fetch_stories` fails, the StoryListScreen could display a centered message "Failed to load stories. Check connection. Press r to retry or q to quit." The user can press `r` to attempt again.
  - For less critical failures, e.g., one story’s detail failed to load, we could skip it or show "[Error loading details]" as that story’s title (rare if using official API, unless an ID no longer exists).
  - Authentication errors: if login fails (wrong password), just log "Login failed" (we might also show a brief on-screen message). The app continues as guest.
  - Upvote errors: if a vote action returns an error (maybe network down or token expired), show a popup "Unable to upvote. Try again." and log it.

- If the app does crash due to an unhandled exception (our goal is none in normal use), Loguru will by default print the traceback to stderr. That would appear messed up in the terminal UI. We should prevent that by catching exceptions in places likely to throw. Possibly run Textual with try/except around app.run, but that might not catch inside tasks. Better is to anticipate errors and handle them.

- We'll set httpx timeouts (like 5 seconds) to avoid hanging. If a timeout occurs, treat as failure and perhaps let user retry.

- **Debugging Aids:** 
  - If we have a debug mode (e.g., if env `HEWS_DEBUG=1`), we can enable some on-screen debug info or extra logging.
  - Could add a hidden key to open a debug log panel for dev (not necessary for users though).

### 5.6 **Performance Considerations**

We want the app to be snappy:

- **Startup speed:** The goal is to display something (even if it's cached content or a loading spinner) quickly (~1 second). 
  - Using async fetch for stories is a major improvement over sequential (which would be too slow for 30 stories). 
  - If cache is warm, we could show cached top stories instantly and then update them when fresh data comes (that would be ideal offline support). But for v1, we might just show a spinner until data is fetched if not cached.
  - Possibly parallelize fetching story list and maybe other data. The story list (IDs) call is quick, the slow part is fetching each item. But we already parallelize those.
  - We should also initialize httpx AsyncClient once to reuse connections.

- **Memory usage:** The data we handle (stories, comments) is text and not too heavy. 500 HN stories might be a few MB in JSON, similarly comments. Python overhead is okay. If memory ever is an issue, we could limit how many comments we keep in memory by not storing beyond what's needed, but likely fine.

- **Large threads:** A story with 1000 comments could be heavy to render. Some strategies:
  - We already plan to not fetch all 1000 at once (on-demand loading). So initial load for that story might just fetch top-level (say 100 top-level comments) which is manageable.
  - As user expands, each sub-thread fetch is similarly manageable (rarely will someone expand everything manually).
  - If they did want to see all, we might allow an "expand all" which could be slow; but we can warn or avoid implementing it.
  - Rendering 1000 comments at once might be slow. If we find performance issues, we could implement virtualization (only create widgets for visible ones). But that’s complex. We assume typical usage and our partial loading will keep it within reason.

- **Rate limiting:** 
  - The official API has no fixed rate limit besides not spamming (500 items for top stories is fine, and our usage is within normal).
  - Algolia might have a rate limit (maybe a few hundred queries per minute) but a user likely won't exceed that manually.
  - We can implement a basic check: if user triggers multiple searches quickly (like spamming enter on empty query), maybe ignore duplicates or introduce a half-second delay.

- **Parallel connections:** httpx AsyncClient uses HTTP/2 if possible, which can multiplex requests on a single TCP connection (Firebase API might support HTTP/2). That could further speed up fetching many items. If not, it will open multiple connections but that's fine for 30 requests.
  
- **Potential Optimizations:** 
  - Caching already helps for repeated openings (like if user goes back to top stories and then returns to comments, those comments are cached).
  - We could also prefetch some data: e.g., while user is reading comments, we might in background fetch the next set of stories or some such. But likely unnecessary.

- **Testing Performance:** We should test a case: open a story with say 300 comments. Ensure expanding/collapsing operations are quick (they should be O(n) for number of comments expanded/collapsed, which is fine). If we see any slowdown, adjust logic (maybe avoid repeated heavy operations).
  
- We should also consider the speed of pyfiglet for banner at startup (should be negligible relative to network ops).
  
### 5.7 **Security and Privacy**

- We treat user credentials carefully:
  - They are only read from environment, not stored in code or output. 
  - If user uses interactive login (if we had that), ensure password is not echoed and not logged.
  - The session cookie is stored in memory (httpx client) and possibly in cache if we decided to (but we probably won't store it to disk for now).
  - If we did store any auth token (like we might store the HN `user` cookie in cache for persistence), it should be treated as secret. Probably simplest: require login each session for now if they want (since .env will supply credentials).
  
- Use HTTPS endpoints for all external communication:
  - Official API is on `hacker-news.firebaseio.com` (which is HTTPS).
  - Algolia API is `hn.algolia.com` (HTTPS).
  - HN website is `https://news.ycombinator.com`.
  - So yes, all secure. httpx by default verifies SSL.

- We ensure not to include secure info in logs:
  - Don’t log full URLs for upvote or comment actions since they contain the `auth` token (or if we do, sanitize it).
  - Don’t log cookies or credentials. Loguru’s default exception logging might include request info, so be cautious to catch exceptions from login/upvote before loguru prints them (maybe log a generic message instead of letting it dump any object with secrets).

- If using `.env`, highlight in docs that this file contains plain text credentials and should be protected (e.g., add to .gitignore, etc., which we will).

- **Input validation:** 
  - The user input (search query) is sent to Algolia as part of URL; httpx will encode it properly, but we should ensure no special characters break our URL format (maybe use `httpx.QueryParams` or at least `quote_plus` on query).
  - Comment text: We send it to HN as form data, which is fine. But also, if we ever displayed user-provided content in our UI (the comments from HN are HTML sanitized by HN, but there could be some content that might do weird things in terminal? Possibly not, HN strips dangerous tags. The terminal could theoretically interpret some sequences as control codes if not handled, but Rich likely escapes or handles control codes in text).
  - To be safe, ensure we don't directly print user content to terminal without Rich (which would escape or hide control sequences). Rich by default won’t allow terminal escape sequences in the content (unless explicitly told to, I think).
  
- **Denial of Service/Misuse:** 
  - This tool is client-side and single-user, so not much risk of DoS except the user overloading HN’s API with too many requests. Our usage is typical (similar to browsing HN website, which also loads data and comments in similar volume).
  - If someone maliciously scripted our tool to e.g. constantly search or fetch item ids in a loop, that’s on them; it's not an open server that others can misuse.

With the technical approach outlined, a developer should be able to proceed with implementation confident about how components interact and what the expectations are.

## 6. **Non-Functional Requirements**

### 6.1 **Performance & Efficiency**

- **Fast Startup:** The tool should launch and display content quickly (ideally ~1 second for initial Top stories on a decent connection). Using asynchronous HTTP requests and caching ensures minimal delay. If network is slow, we will at least show a loading indicator immediately to reassure the user the app is working. Expensive operations (network calls, large text rendering) are done off the main UI thread to keep the interface responsive.

- **Low Resource Usage:** The app should remain lightweight. Memory use should be modest (only storing text and data needed). CPU usage should mostly be idle when user is reading; spikes when loading data (which is fine). Even with hundreds of comments loaded, the app should not consume excessive CPU. Rich/Textual are designed for performance, but we will test to avoid pathological cases (like rendering 1000 items unnecessarily).

- **Scalability:** While typical usage might be reading top stories and a few discussions, we design to handle edge cases: 
  - If a story has 1000+ comments, the app should handle it by lazy loading and possibly not rendering all at once to avoid slowdown. 
  - The caching system and data structures should handle hundreds or thousands of items without significant slowdown. SQLite can handle many records fine. Searching within cached content (if implemented) might slow if we had thousands of entries without an index, hence suggestion of FTS indexing if needed.
  - The tool is single-user, so throughput (requests per second) is not a huge concern beyond making sure we parallelize logically for latency hiding.

- **Compatibility:** 
  - Platform: Primarily macOS (per user’s target), but since it’s Python and Textual, it should also run on Linux out-of-the-box. Windows support depends on Textual’s compatibility with Windows terminals (Textual does aim to support Windows, though colors might differ). We won’t do OS-specific code except perhaps for default cache paths.
  - Terminal: It requires a UTF-8 capable terminal (most modern ones). We use colors (ANSI escape codes via Rich) and box-drawing characters – these work on most terminals (xterm, iTerm2, Windows Terminal, etc.). If someone uses a very old or non-UTF8 terminal, Rich might fall back to ASCII approx or no color. We’ll rely on Rich’s detection; e.g., it will disable color if TERM=dumb or piping to file.
  - Python version: 3.12+. We should ensure no usage of deprecated libraries that would cause performance or compatibility issues.

### 6.2 **Reliability & Robustness**

- **Error Handling:** The application should handle unexpected situations gracefully, without crashing:
  - **Network failures:** If the HN API or Algolia are unreachable (timeout, no internet), the app should detect this and either fall back to cached data or inform the user and allow retry. E.g., if initial fetch fails, show error and let user press retry. 
  - **API errors:** If the API returns malformed data or a 500 error (rare), similarly handle by showing an error. 
  - Use httpx timeouts (set reasonable timeout, e.g., 5 seconds connect, 10 seconds read) to avoid hanging indefinitely. Use try/except around requests to catch `httpx.RequestError` and `httpx.HTTPStatusError`.
  - **UI errors:** The UI should not crash on invalid input. For example, if user tries to expand a comment that we fail to fetch, just show “[Failed to load replies]” rather than crash.
  - Textual is built to handle a lot of UI logic robustly, but we must ensure our callback logic doesn’t throw unhandled exceptions. We will test various scenarios (like network down, invalid credentials, etc.).

- **Data Consistency:** 
  - Ensure caching logic doesn’t corrupt data. For instance, if we are writing multiple related records (story and its comments), ideally do it in a transaction if using SQLite so partial writes don’t leave things inconsistent. SQLite by default is transactional per statement, but if writing multiple, wrap them in `BEGIN...COMMIT`.
  - If the app crashes or is killed while writing cache, SQLite might have a rollback journal to maintain integrity, so usually okay.
  - In memory, ensure that if we mark something as cached after fetch, the data is indeed fully fetched. If a comment fetch fails halfway, better not insert half the comments as if complete. Maybe use flags or fetch comments individually so either each comment is cached or not.
  - Also ensure that if user logs out (not really a concept here, we only login once at start or not at all), the state is consistent (we won't implement logout likely; exit is the only way to "log out").

- **Logging & Debugging:** 
  - Keep a detailed log (in debug mode) of actions to aid troubleshooting. This way if a user reports a bug, developers can ask for the log to see what happened (without requiring the user to reproduce with a debugger).
  - For reliability, log catches of exceptions along with tracebacks to debug issues that we might not anticipate.
  - Possibly include version info and environment info in logs at startup for context.

### 6.3 **Maintainability & Extensibility**

- **Code Structure:** We’ve separated concerns (CLI vs data vs UI) so future modifications can be localized:
  - If HN changes its API (say to v1 or GraphQL), ideally only HNClient needs to change, and the UI would remain largely unaffected as long as it still gets Story/Comment objects with needed fields.
  - If we add a new HN section (imagine HN adds a "Best" section), we just add the option in CLI and perhaps key binding, and call HNClient for that section (assuming API provides it).
  - If we add a feature like viewing user profiles, we can add a new screen for that without touching core browsing logic much.
  - The UI design using Textual screens means new screens can be added modularly (like a “settings” screen or similar in future).

- **Documentation:** 
  - We should have a README explaining installation and usage (with examples of commands). Also, the `--help` provides usage info. 
  - In code, comment any complex or non-obvious logic (like the algorithm for comment collapse/expand, or the login scraping). 
  - The PRD itself serves as documentation for design; a developer might also add docstrings to public methods (like HNClient methods).
  - Possibly maintain a small wiki or doc for how to extend (if handing over to a team or open source). But at least internal documentation is important for a junior dev to understand the flow.

- **Extensibility:** The architecture allows adding features:
  - Adding support for “Best” or “Trending” stories (if HN API has endpoints) – would just be a matter of adding an option and calling the client for that endpoint. UI list can reuse existing code.
  - Enhanced search filters (e.g., search comments) – could extend HNClient.search to allow tag parameter, and perhaps add UI options in the search prompt (like if user enters a prefix or selects a filter).
  - If we wanted to create a GUI or web version: interestingly, Textual has a project “Textual Web” to render the same UI in a browser. If that matures, we could potentially run Hews as a web app with minimal changes. So keeping UI code using Textual’s abstraction means down the line, we could explore that.
  - Theming can be easily extended by just adding new CSS files. The code wouldn’t need changes to support a new theme as long as it's named and loaded. Could even allow user-created themes dropped in a folder.
  - Perhaps plugin system: not needed now, but if each major piece is modular, one could imagine adding an extension e.g., to integrate text-to-speech or something, by tapping into the data or UI events.

- **Dependency Management:** We use **uv** for managing dependencies, which creates a lock file for reproducibility. So adding/upgrading a library is straightforward (e.g., `uv add textual@0.11` when a new version comes, and test if everything still works). 
  - This ensures that the environment can be easily replicated by other developers (via `uv` or even pip installing from pyproject with pinned versions).
  - We should keep libraries up-to-date but pinned to known good versions to prevent breaking changes from affecting our app.

### 6.4 **Security**

- **Credential Safety:** 
  - We never hard-code credentials; they come from environment variables (or user prompt), which aligns with 12-factor principles (config in environment). 
  - We should ensure `.env` is in .gitignore so it's not accidentally committed anywhere (we will include a sample `.env.example` if needed for reference).
  - Logging: make sure no sensitive info is logged. This means never logging the full login POST payload or cookies. Also, if logging HTTP requests, scrub out Authorization or Cookie headers if present. Using Loguru, we will likely not log request details at INFO level, only at DEBUG, and even then we'll be careful to filter.
  - When storing cache, the only potentially sensitive data would be user’s own comments if they wrote any (but that’s not really secret). The cookie if we ever stored it would be sensitive, but we plan not to store cookies on disk by default.

- **HTTPS Only:** Use https URLs for everything (which we have enumerated). Ensure httpx is not instructed to allow insecure connections. We keep certificate verification on (default). 
  - In case a corporate user is behind a proxy with custom CA, they might have to configure SSL for httpx, but that’s on them; we won’t disable SSL verify by default.

- **Session Cookie Management:** 
  - Keep the cookie in memory (httpx AsyncClient) which by default stores cookies in a CookieJar. When the app exits, the cookie is gone (unless user put credentials in .env, then it will login again next time).
  - If persistent login was desired, we could save cookies in cache, but it's probably not needed since .env covers that or the user can just not log out.

- **User Input Handling:** 
  - When we take text input for search or comment, ensure we handle special characters safely. (E.g., user might search for something with quotes or semicolons, etc. We should quote them in URL. We will likely use httpx with params, which handles encoding).
  - For comments, HN expects plain text (with newlines). If user input contains characters like `<` or `&`, that’s fine, HN will escape them on their end (or interpret as part of their formatting, e.g., they allow some HTML in comments like <i>). We don't need to sanitize outgoing text, just send as is; HN will sanitize and store. 
  - On the display side, since HN returns comment text as HTML, we need to sanitize *for terminal output*. We'll strip tags and maybe decode HTML entities. Rich can render a subset of HTML or markdown if we convert it. We'll be careful that no unhandled ANSI codes slip through. Possibly use Rich's `escape` on raw text to avoid accidental interpretation of something like `\x1b` if it ever appeared (which is unlikely from HN content).
  - One risk: HN comments can contain ASCII color codes in backtick code blocks? Probably not, HN strips those. So likely fine.

- **Misuse scenarios:** 
  - If someone did want to spam upvotes or comments via our tool (which would essentially be scripting their account), they'd hit HN's rate limiting or anti-abuse eventually (e.g., too many upvotes too fast might temporarily ban the account). That's not our responsibility but just something to be aware of. Our tool doesn't encourage or automate such actions beyond normal use.

By adhering to these non-functional requirements, we ensure *Hews* is not only feature-rich but also reliable, easy to maintain, and secure.

## 7. **Development & Delivery**

This section outlines how a developer should implement the project using this PRD and how to verify it, including project setup and CI/CD integration.

- **Project Setup:** Initialize a new Python project (we’ll use **uv** for this):  
  - **Repository:** Create a new Git repository for the project under the user’s GitHub account (for example, at `https://github.com/indrasvat/hews`). All source code and documentation will be version-controlled in this repo, which will be the primary deliverable.  
  - Create `pyproject.toml` with project metadata (name `hews`, version, authors) and specify Python ≥3.12. List dependencies: textual, rich, click, python-dotenv, httpx, loguru (and possibly pyfiglet if used).  
  - Use `uv` (Astral) to install and lock dependencies. This generates a `pyproject.lock` file ensuring reproducible installs. Commit `pyproject.toml` and `pyproject.lock` to the repo.  
  - Set up the console entry point in `pyproject.toml` (under `[project.scripts]`), e.g., `hews = "cli:main"`. This means after installation, running `hews` invokes `cli.main()`.  
  - Prepare a basic project structure: e.g., have a `hews/` directory with `__init__.py`, and modules for the code (`cli.py`, `hnapi.py`, `ui.py`, etc. as needed).  
  - Include a `.gitignore` (ignore `.env`, cache files, etc.).  
  - Include a README.md with project description, usage examples, and installation instructions (like “pip install .” or “uv run” etc.).  

- **Development Plan:** Implement features in a logical sequence, verifying each layer:
  1. **Basic CLI and API fetching:** Start by implementing `HNClient` with the ability to fetch top stories and a single story. Also implement CLI argument parsing to call these functions. For example, add a `--print` mode early for testing: `hews --section top --print` could print top story titles using the HNClient. This ensures the API access works and we can parse JSON correctly. Write a quick test or run manually to see output. Logging can also be set up here to see what's happening.  
  2. **TUI List View:** Next, introduce Textual. Create a minimal `HewsApp` and `StoryListScreen` that displays a static list of strings first. Then integrate it with `HNClient`: on mount, load top stories and display them. Ensure arrow key navigation and Enter key (maybe just print something or log on Enter for now). This step confirms that Textual is working and we can populate UI with dynamic data.  
  3. **Comments View:** Implement `CommentsScreen` to display comments for a story. Initially, to simplify, you can skip collapse logic: just fetch story and all comments recursively (this might be slow for huge threads, but start simple). Render them indented (even as plain text) to verify nesting. Then add the collapse/expand functionality: manage child comment widgets and show/hide them. Test that you can navigate, expand and collapse without issues. At this stage, upvote and login aren’t done yet, focus on reading.  
  4. **Search:** Add the search functionality using Algolia. This involves calling the search API in `HNClient` and maybe creating a new screen or reusing `StoryListScreen`. Ensure that input (via `/` key or a separate CLI invocation) triggers the search and results show. Test with various queries. Make sure special characters in query don’t break (maybe try a query with spaces, punctuation).  
  5. **Caching:** Integrate the caching layer. This might involve setting up SQLite and writing the CacheManager. Once that’s done, ensure `HNClient` uses it: e.g., fetch_item first checks cache. Test by running the app, viewing a story, exiting, then disconnect internet, run again and see if it uses cached data. Also test that performance is okay with caching (no major delays writing to DB).  
  6. **Polish & Features:** Add remaining niceties:
     - Theming support: create CSS files, allow a theme toggle or at least respect an env var. Ensure colors look good. 
     - Login & Upvote: implement login using `python-dotenv` (already loaded in CLI). If credentials are present, log in. Then implement upvote action and comment post if doing that. This can be tricky due to needing to parse HTML, so take time to test upvote on a known story. Possibly use a test account to avoid affecting a real account heavily. 
     - ASCII banner: generate with pyfiglet or similar and print it when app starts (maybe in CLI before launching Textual, or within Textual as part of header). Experiment with how it looks (ensure it doesn’t mess up terminal sizing).
     - Mouse support: ensure you didn’t disable it; Textual by default supports it. You might need to add on_click handlers for list items and comment widgets. Test clicking around if possible. 
     - Offline handling: test by simulating no network (maybe run with wifi off or patch httpx to throw errors) and see that app behaves (shows cached data or errors). Tweak accordingly.
     - Help screen: design a help overlay listing keys and maybe short instructions, triggered by `?`.
  7. **Testing & Bugfix:** After implementing all features, do thorough manual testing:
     - Try narrow terminal vs wide terminal.
     - Try switching between sections quickly, search after switching, etc. (Look for any state bugs or memory leaks).
     - Input wrong password in .env to see behavior.
     - Force an API failure (change base URL to wrong one temporarily) to see error message.
     - If possible, test on macOS and Linux to ensure compatibility (colors, etc.). 
     - Address any crashes or glitches found.
     - Possibly run `mypy` to ensure type correctness if using type hints.
     - Run `flake8` or Black to ensure code style (if CI will enforce it).

- **Continuous Integration:** Set up CI to automate quality checks:  
  - Use **GitHub Actions** to run tests and linters on each push/PR. Write a workflow YAML that sets up Python 3.12, installs deps (possibly using `pip install .[dev]` if we define dev extras with pytest, etc.).  
  - Have it run `pytest` (which will run any tests we write; by final delivery, at least ensure the suite in Section 8 passes), run a linter (flake8) and a formatter check (black --check) and `mypy` for type checking.  
  - Ensure CI uses appropriate OS (Linux is standard; maybe also run on macOS to catch any OS-specific stuff, optional).  
  - The CI should fail if any test fails or if code doesn’t meet formatting/type standards. This will maintain code quality going forward.  

- **Definition of Done:** We consider the project complete when:  
  - All functional requirements are met: one can browse HN sections, read comments, search stories, use offline cache, and (if logged in) upvote/comment. The TUI interactions are smooth (keyboard/mouse).  
  - The app does not crash during normal use, and handles error conditions gracefully (with user-visible messages).  
  - The UI/UX conforms to the description: correct key bindings, layouts, color themes, etc., matching what’s in this PRD.  
  - We have documentation: at minimum, a README with usage examples, and the `--help` output is informative. Possibly also docstring comments for important functions.  
  - Tests: Ideally, we have automated tests (see Section 8) covering key parts. At minimum, the developer should have manually tested a variety of scenarios as described. 

Once complete, this tool will provide developers and HN readers a powerful new way to consume content directly from their terminal, combining modern Python TUI capabilities with the rich content of Hacker News. By following this PRD step-by-step, even a relatively junior developer should be able to implement the system in a structured way, verifying each part as they build, and end up with a high-quality, visually appealing, and differentiating Hacker News CLI application.

**Sources:**

- Hacker News CLI design inspiration (Rich + Click + Textual combo) – discussion on HN about making CLI tools with Rich (demonstrates viability of colorful TUIs).  
- Async HTTP concurrency with httpx – shows benefit of parallel requests vs sequential.  
- Environment config via python-dotenv (12-factor config) – why .env is used for creds/config.  
- Logging best practices with Loguru – justification for using Loguru over basic logging.  
- Fast dependency management with uv – rationale for using uv (ease of use, locking).  
- Hacker News API usage and caching ideas – guidelines on using official API efficiently (like not fetching more than needed, caching to reduce requests).  
- Existing Hacker News TUI tools – to confirm that using both official API for data and Algolia for search is a proven approach (as seen in aome510’s hackernews-TUI project).

