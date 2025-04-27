# UI/UX Architecture Reference for Hews

This document provides a comprehensive reference for the UI/UX architecture of Hews, focusing on the Rich and Textual libraries that will be used to implement the terminal-based Hacker News client.

## 1. Rich Library Components

[Rich](https://rich.readthedocs.io/) provides rich text and beautiful formatting in the terminal, which will be essential for creating a visually appealing interface.

### 1.1 Tables

Tables in Rich will be useful for displaying story listings in a structured format:

- **Customizable columns**: Arrange story metadata (title, author, score, comments count) in columns
- **Border styling**: Visual separation between rows and columns with various border styles
- **Row highlighting**: Highlight the currently selected story
- **Vertical alignment**: Properly align multi-line entries

### 1.2 Panels

Panels provide visual framing for content:

- **Titled containers**: Frame story content or comments with a titled border
- **Nested panels**: Group related information (e.g., story metadata)
- **Border styles**: Different styles to indicate focus or importance
- **Padding control**: Add whitespace for readability

### 1.3 Markdown Rendering

Essential for rendering formatted content from Hacker News:

- **Inline formatting**: Support for bold, italic, links
- **Code blocks**: Properly format code snippets in comments
- **Automatic conversion**: Render HN's HTML-like format as readable text

### 1.4 Progress Indicators

Show loading status during network operations:

- **Spinners**: Indicate when stories or comments are loading
- **Progress bars**: Show progress for longer operations
- **Multiple indicators**: Track different parallel operations

### 1.5 Live Display

Support dynamic content updates:

- **Auto-refresh**: Update content periodically
- **User-triggered refresh**: Respond to user commands to refresh content
- **Smooth transitions**: Update content without jarring UI changes

### 1.6 Text Styling

Create visual hierarchy and improve readability:

- **Color systems**: Use colors to indicate different content types
- **Console markup**: Simplified styling with markup like `[bold red]text[/]`
- **Text effects**: Highlight important elements with underline, bold, etc.

## 2. Textual Framework Architecture

[Textual](https://textual.textualize.io/) is a TUI (Text User Interface) framework built on Rich, providing a higher-level approach to building interactive terminal applications.

### 2.1 Application Structure

```python
class HewsApp(App):
    """Main Hews application."""
    
    CSS_PATH = "hews.tcss"  # Load app styling
    
    BINDINGS = [  # Global keybindings
        ("q", "quit", "Quit"),
        ("?", "toggle_help", "Help"),
        ("/", "search", "Search"),
        ("t", "section('top')", "Top Stories"),
        ("n", "section('new')", "New Stories"),
        ("a", "section('ask')", "Ask HN"),
        ("s", "section('show')", "Show HN"),
        ("j", "section('jobs')", "Jobs"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        yield StoryListScreen()
        yield Footer()
    
    def on_ready(self) -> None:
        """Called once when app is ready."""
        self.update_stories()
        # Set up auto-refresh
        self.set_interval(60, self.update_stories)
        
    def action_section(self, section_name: str) -> None:
        """Switch to a different section."""
        # Implementation here
```

### 2.2 Screen Navigation

Textual uses a screen stack for navigation:

```python
# Navigate to story comments
def on_list_view_selected(self, event: ListView.Selected) -> None:
    """Handle story selection."""
    story_id = self.stories[event.index].id
    self.app.push_screen(CommentsScreen(story_id=story_id))

# Return to previous screen
def action_back(self) -> None:
    """Go back to previous screen."""
    self.app.pop_screen()
```

### 2.3 Async Operations

Textual is designed to work with asynchronous operations:

```python
async def update_stories(self) -> None:
    """Fetch and display stories."""
    with self.screen.loading("Fetching stories..."):
        stories = await self.app.hn_client.fetch_stories("top")
    self.story_list.clear()
    for story in stories:
        self.story_list.append(self._render_story(story))
```

### 2.4 Screens and Views

Different screens for main application views:

#### 2.4.1 StoryListScreen

```python
class StoryListScreen(Screen):
    """Screen for displaying story listings."""
    
    def __init__(self, section: str = "top") -> None:
        super().__init__()
        self.section = section
        self.stories = []
    
    def compose(self) -> ComposeResult:
        yield Header(f"{self.section.title()} Stories")
        yield ListView(id="story-list")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Load stories when screen is mounted."""
        await self.load_stories()
    
    async def load_stories(self) -> None:
        """Fetch stories from HN API."""
        with self.app.loading("Loading stories..."):
            self.stories = await self.app.hn_client.fetch_stories(self.section)
            story_list = self.query_one("#story-list", ListView)
            story_list.clear()
            
            for story in self.stories:
                story_list.append(StoryListItem(story))
```

#### 2.4.2 CommentsScreen

```python
class CommentsScreen(Screen):
    """Screen for displaying story details and comments."""
    
    def __init__(self, story_id: int) -> None:
        super().__init__()
        self.story_id = story_id
        self.story = None
        self.comments = {}
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(id="story-content"),
            Tree(id="comments-tree"),
            id="story-container"
        )
        yield Footer()
    
    async def on_mount(self) -> None:
        """Load story and comments when screen is mounted."""
        await self.load_story()
    
    async def load_story(self) -> None:
        """Fetch story and comments from HN API."""
        with self.app.loading("Loading story..."):
            self.story = await self.app.hn_client.fetch_item(self.story_id)
            self.comments = await self.app.hn_client.fetch_comments(self.story_id)
            
            # Update story content
            story_content = self.query_one("#story-content", Static)
            story_content.update(self._render_story_content())
            
            # Build comment tree
            comments_tree = self.query_one("#comments-tree", Tree)
            self._build_comment_tree(comments_tree)
```

### 2.5 Tree View for Comments

Implementing a tree view for nested comments:

```python
def _build_comment_tree(self, tree: Tree) -> None:
    """Build comment tree from fetched comments."""
    tree.clear()
    
    # Add top-level comments first
    for comment_id in self.story.kids:
        if comment_id in self.comments:
            comment = self.comments[comment_id]
            node = tree.root.add(f"[bold]{comment.author}[/] - {comment.age}")
            node.expand()
            
            # Add comment text
            text_node = node.add(comment.text)
            
            # Add replies recursively
            self._add_comment_replies(comment, node)

def _add_comment_replies(self, comment: Comment, node: TreeNode) -> None:
    """Recursively add replies to comment node."""
    if hasattr(comment, 'kids') and comment.kids:
        for kid_id in comment.kids:
            if kid_id in self.comments:
                reply = self.comments[kid_id]
                reply_node = node.add(f"[bold]{reply.author}[/] - {reply.age}")
                
                # Add reply text
                text_node = reply_node.add(reply.text)
                
                # Continue recursion
                self._add_comment_replies(reply, reply_node)
```

### 2.6 Search Dialog

Modal dialog for search functionality:

```python
class SearchDialog(ModalScreen):
    """Search dialog for Hacker News."""
    
    def compose(self) -> ComposeResult:
        yield Container(
            Label("Search Hacker News:"),
            Input(placeholder="Enter search terms"),
            Button("Search", variant="primary"),
            Button("Cancel"),
            id="search-dialog"
        )
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the dialog."""
        if event.button.label == "Search":
            query = self.query_one(Input).value
            self.dismiss(query)
        else:
            self.dismiss(None)
```

Usage:

```python
async def action_search(self) -> None:
    """Show search dialog and handle result."""
    query = await self.push_screen(SearchDialog())
    if query:
        await self.search_stories(query)
```

### 2.7 Custom Widgets

#### 2.7.1 StoryListItem

```python
class StoryListItem(ListItem):
    """Custom widget for displaying a story in list view."""
    
    def __init__(self, story: Story) -> None:
        super().__init__()
        self.story = story
    
    def compose(self) -> ComposeResult:
        """Render story item."""
        yield Static(
            f"[bold]{self.story.title}[/]" + 
            (f" ({self.story.domain})" if hasattr(self.story, 'domain') else ""),
            classes="story-title"
        )
        yield Static(
            f"{self.story.score} points by {self.story.author} | " +
            f"{self.story.comments_count} comments | {self.story.age}",
            classes="story-meta"
        )
```

#### 2.7.2 CommentWidget

```python
class CommentWidget(Static):
    """Custom widget for displaying a comment."""
    
    def __init__(self, comment: Comment, depth: int = 0) -> None:
        super().__init__()
        self.comment = comment
        self.depth = depth
        self.collapsed = False
    
    def compose(self) -> ComposeResult:
        indent = "  " * self.depth
        toggle = "[-]" if not self.collapsed else "[+]"
        
        yield Static(
            f"{indent}{toggle} [bold]{self.comment.author}[/] - {self.comment.age}",
            classes="comment-header"
        )
        
        if not self.collapsed:
            yield Static(
                f"{indent}  {self.comment.text}",
                classes="comment-text"
            )
```

## 3. Widget Recommendations

These Textual widgets are particularly suitable for Hews implementation:

### 3.1 ListView

Perfect for displaying story listings with selection capabilities:

- **Keyboard navigation**: Up/down to select stories
- **Mouse support**: Click to select
- **Focus handling**: Clear visual indication of selection
- **Event handling**: `Selected` event when item is selected

### 3.2 Tree

Ideal for nested comment threads:

- **Hierarchical display**: Shows parent-child relationships
- **Collapsible nodes**: Expand/collapse comment threads
- **Custom node rendering**: Format each comment
- **Keyboard navigation**: Up/down/left/right for navigation

### 3.3 DataTable

Alternative for story listings with more structured display:

- **Column headers**: Clearly label data fields
- **Sorting**: Sort by score, date, etc.
- **Row selection**: Similar to ListView
- **Custom cell rendering**: Format individual cells

### 3.4 Header/Footer

For app navigation and status display:

- **App title**: Show "Hews" and current section
- **Command display**: Show available commands
- **Status information**: Show online/offline status

### 3.5 ContentSwitcher

For toggling between different app views:

- **Multiple children**: Only one visible at a time
- **Programmatic switching**: Change visible content based on user action
- **Smooth transitions**: Can animate between views

### 3.6 TabbedContent

For section navigation:

- **Tab headers**: Top, New, Ask, Show, Jobs
- **Content panes**: One per section
- **User selection**: Click or keyboard shortcuts to switch

### 3.7 ProgressBar

For visualizing loading operations:

- **Determinate progress**: Show percentage complete
- **Indeterminate progress**: Show activity without specific percentage
- **Customizable appearance**: Colors, width, etc.

## 4. Styling with TCSS

Textual CSS (TCSS) provides powerful styling capabilities:

### 4.1 Base Styling

```css
Screen {
    background: $background;
}

Header {
    background: $accent;
    color: $text;
    text-style: bold;
    content-align: center middle;
}

Footer {
    background: $accent;
    color: $text;
}
```

### 4.2 Story List Styling

```css
StoryList {
    layout: grid;
    grid-size: 1;
    grid-rows: 1fr;
    padding: 1 2;
    height: 100%;
    border: $accent;
}

.story {
    height: auto;
    margin: 1 0;
    padding: 0 1;
    background: $boost;
    border: tall $background;
}

.story-title {
    color: $text;
    text-style: bold;
}

.story-meta {
    color: $text-muted;
}

.story:focus {
    border: tall $accent;
}
```

### 4.3 Comments Styling

```css
#story-container {
    width: 100%;
    height: 1fr;
}

#comments-tree {
    margin: 1 0 0 0;
}

.comment-header {
    color: $text-muted;
}

.comment-text {
    margin: 0 0 1 0;
}

.comment-text code {
    background: $accent-darken-2;
    color: $text;
}

.comment-deleted {
    color: $error;
    text-style: italic;
}

.comment-op {
    background: $accent-darken-1;
    color: $text;
    text-style: bold;
}
```

### 4.4 Search Dialog Styling

```css
#search-dialog {
    width: 60%;
    height: auto;
    border: thick $accent;
    background: $surface;
    padding: 1 2;
    margin: 1 2;
}

Input {
    width: 100%;
    margin: 1 0;
}

Button {
    margin: 1 1;
}
```

## 5. Event Handling Patterns

Textual's event system is key to creating an interactive interface:

### 5.1 Key Binding

```python
BINDINGS = [
    ("q", "quit", "Quit"),
    ("?", "toggle_help", "Help"),
    ("/", "search", "Search"),
    ("r", "refresh", "Refresh"),
    ("u", "upvote", "Upvote"),
]

def action_refresh(self) -> None:
    """Refresh current content."""
    if isinstance(self.screen, StoryListScreen):
        self.load_stories()
    elif isinstance(self.screen, CommentsScreen):
        self.load_story()
```

### 5.2 Widget Events

```python
def on_list_view_selected(self, event: ListView.Selected) -> None:
    """Handle list selection."""
    story = self.stories[event.index]
    self.app.push_screen(CommentsScreen(story_id=story.id))

def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
    """Handle comment selection."""
    if hasattr(event.node, "comment_id"):
        # Perhaps highlight the selected comment
        pass

def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
    """Handle comment thread expansion."""
    if not event.node.children and hasattr(event.node, "comment_id"):
        # Load and add child comments if not already loaded
        comment_id = event.node.comment_id
        self._load_comment_replies(comment_id, event.node)
```

### 5.3 Focus Handling

```python
def on_focus(self, event: events.Focus) -> None:
    """Handle widget receiving focus."""
    if isinstance(event.widget, StoryListItem):
        self.current_story = event.widget.story

def watch_focused(self, focused: str) -> None:
    """React to focus changes."""
    if focused == "story-list":
        self.footer.update("↑/↓: Navigate • Enter: View Story • r: Refresh")
    elif focused == "comments-tree":
        self.footer.update("↑/↓: Navigate • ←/→: Collapse/Expand • u: Upvote")
```

### 5.4 Mouse Handling

```python
def on_click(self, event: events.Click) -> None:
    """Handle mouse clicks."""
    # Identify target and handle accordingly
    widget = self.app.get_widget_at(event.x, event.y)
    if isinstance(widget, StoryListItem):
        self.view_story(widget.story)
    elif isinstance(widget, CommentWidget):
        widget.toggle_collapsed()
```

## 6. Responsive Design

Textual supports responsive design for different terminal sizes:

```css
/* Base styles */
StoryList {
    width: 100%;
}

/* For wide terminals */
@media (min-width: 120) {
    StoryList {
        width: 30%;
    }
    
    CommentView {
        width: 70%;
    }
    
    #main-container {
        layout: horizontal;
    }
}

/* For narrow terminals */
@media (max-width: 60) {
    .story-meta {
        display: none;
    }
}
```

## 7. Theme Support

Implementing dark and light themes:

```python
class HewsApp(App):
    """Main Hews application."""
    
    # Default to dark theme
    DARK_THEME = "hews-dark.tcss"
    LIGHT_THEME = "hews-light.tcss"
    
    def __init__(self, theme: str = "dark") -> None:
        super().__init__()
        self.theme = theme
        self.CSS_PATH = self.DARK_THEME if theme == "dark" else self.LIGHT_THEME
    
    def action_toggle_theme(self) -> None:
        """Toggle between dark and light theme."""
        self.theme = "light" if self.theme == "dark" else "dark"
        self.CSS_PATH = self.DARK_THEME if self.theme == "dark" else self.LIGHT_THEME
        self.refresh_css()
```

With corresponding theme CSS files:

**hews-dark.tcss:**
```css
Screen {
    background: #121212;
    color: #ffffff;
}

.story-title {
    color: #ff6600;
}

.story-meta {
    color: #aaaaaa;
}
```

**hews-light.tcss:**
```css
Screen {
    background: #ffffff;
    color: #000000;
}

.story-title {
    color: #ff6600;
}

.story-meta {
    color: #666666;
}
```

This document serves as a comprehensive reference for implementing the UI/UX architecture of the Hews terminal-based Hacker News client using Rich and Textual libraries.