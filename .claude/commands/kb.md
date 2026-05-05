Save knowledge to the CCP (Central Context Package) team knowledge base.

The user will provide: a title, team, content type, and the content to save. Parse these from the argument string: `/kb <title> --team <team> --type <type>`.

If arguments are missing, ask the user:
- **title**: What to call this entry (required)
- **team**: One of `data`, `ops`, `product`, `engineering` (required)
- **type**: One of `analysis`, `query`, `playbook`, `decision`, `insight`, `model` (default: `analysis`)

Steps:
1. Get the content to save. It can come from:
   - The user pasting it in the conversation
   - A file path the user provides (read it)
   - The output/result of work done earlier in this conversation (summarize the key findings, queries, and conclusions)
2. Run: `export PATH="$HOME/bin:$PATH" && echo '<content>' | kb "<title>" --team <team> --type <type>`
3. If the save succeeds, show the user the file path and confirm.
4. If it fails (secrets detected, review failed), show the error and help the user fix it.

Example usage:
- `/kb Weekend SLA Analysis --team data --type analysis` then paste content
- `/kb` (interactive — ask for title, team, type, and content)
- After doing analysis work: `/kb` to save the findings from this conversation
