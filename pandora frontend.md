# Pandora Knowledge Guardian — V0 Frontend Prompt

> Copy everything inside the code block below and paste it into [v0.ai](https://v0.dev) to generate the UI.

```
Create a full-page React web application UI called "Pandora Knowledge Guardian" — an AI-powered RAG (Retrieval-Augmented Generation) system for environmental researchers, community guardians, and citizens of a fictional bioluminescent moon called Pandora. The app helps users ask questions about environmental threats, marine ecosystems, emergency responses, and conservation policies using uploaded documents.

### Visual Theme & Aesthetic
- Dark bioluminescent ocean world — inspired by deep-sea bioluminescence, coral reefs, and glowing forest networks
- Color palette:
  - Background: #050d1a (deep ocean black-blue)
  - Surface cards: #0a1628 with subtle #0d2040 border
  - Primary glow: #00e5ff (cyan bioluminescent)
  - Secondary glow: #39ff8f (green bioluminescent, like glowing plants)
  - Accent purple: #a855f7 (for metadata/tags)
  - Warning amber: #f59e0b
  - Critical red: #ef4444
  - Text primary: #e2f4ff
  - Text muted: #7faec7
- Glowing effects: Use CSS box-shadow and text-shadow in cyan/green to simulate bioluminescent glow on active elements, borders, and icons
- Background: Subtle animated floating particles or soft radial gradient suggesting deep ocean depth
- Organic shapes: Slightly rounded cards (12–16px radius), soft blurs, no harsh straight edges
- Typography: Use font-family 'Orbitron', sans-serif for headings (futuristic, clean), 'Inter' for body text

### Layout — Three-Column Desktop Layout

Column 1 (left sidebar, 280px wide):
- App logo at top: glowing cyan leaf/network icon + text "PANDORA" in Orbitron font, "Knowledge Guardian" subtitle in small caps
- Role Selector section with label "I am a..." and three pill buttons:
  - Guardian (cyan active state with glow)
  - Researcher (purple active state)
  - Citizen (green active state)
  - Each pill changes the answer style when selected
- Document Library section below:
  - A drag-and-drop upload zone with dashed cyan border, glowing on hover, with icon and text "Drop knowledge documents here" and subtext "PDF, TXT, DOCX supported"
  - Below the drop zone, show 2 pre-loaded document cards each with:
    - Glowing file icon (cyan)
    - Document title in white
    - Small metadata: "56 pages · Loaded" with a green dot
    - A small "x" remove button
  - Documents shown: "Pandora Knowledge Corpus" and "Environmental Field Reports"
- Active Regions filter at bottom of sidebar: small toggle chips for the 10 Pandora regions (Luminous Shelf, Emerald Canopy, Cloudspine Highlands, Silverreed Wetlands, Obsidian Reach, Whispering Dunes, Deep Current Expanse, Mistroot Basin, Aurora Mangroves, Sunfall Archipelago) — each a small pill that glows when active

Column 2 (center main panel, flex-grow):
- Top bar: breadcrumb showing current role + "Ecosystem Intelligence Interface" label on right side + a small status indicator showing "Knowledge Base: Active · 56 pages indexed"
- Conversation area (scrollable, takes most of the height):
  - Welcome state (empty): Large centered bioluminescent icon (branching network/tree of life), headline "Ask the Living Network", subtext "Query Pandora's environmental knowledge base. Every answer is grounded in retrieved documents." + 4 suggested question chips:
    - "What causes unusual water color near Awa Reef?"
    - "Which marine species are most vulnerable to contamination?"
    - "Emergency steps after detecting coral damage?"
    - "Compare water contamination vs. volcanic event responses"
  - User message bubble: right-aligned, dark surface with subtle cyan left border, white text
  - AI answer bubble: left-aligned, dark surface with glowing cyan top-left corner accent, structured content inside:
    - Answer text in white, with inline bold for key terms
    - At the bottom of the answer, an Evidence Quality Badge row showing the knowledge label: check Verified Observation (green), tilde Provisional Interpretation (amber), exclamation Disputed Report (red) — with small tooltip explaining what each means
    - If the answer involves conflicting sources, show a yellow warning Conflicting Evidence Detected banner with brief summary of the conflict
    - If there is insufficient information, show a muted gray card with icon: "The Pandora knowledge base does not contain sufficient evidence to answer this question. Try rephrasing or uploading additional documents."
  - Typing indicator: three glowing cyan dots pulsing
- Input area at bottom (fixed):
  - Large input box with inner placeholder: "Ask about Pandora's ecosystems, species, emergencies, or conservation..."
  - Left side of input: small microphone icon (voice input hint)
  - Right side: a glowing send button (cyan arrow)
  - Below input bar: small text "Answers are grounded in retrieved documents only · Sources shown below each response"

Column 3 (right panel, 320px wide):
- Header: "Retrieved Sources" with a small cyan database icon
- Source cards (shown after each answer, 2–4 cards):
  - Each source card:
    - Document name in cyan at top
    - Chapter/section reference (e.g., "Chapter 12 · Page 40")
    - Relevance score as a horizontal glowing bar (0–100%), color transitions from green to yellow to red
    - Excerpt text in muted color, 2–3 lines
    - Small tag chips: region tag (e.g., Luminous Shelf), category tag (e.g., Environmental Incident)
    - Evidence quality label badge
  - Cards separated by thin glowing dividers
- Below sources: Confidence Score widget — a circular gauge 0–100 showing overall answer confidence, glowing cyan if above 75, amber if 50–75, red if below 50. Label: "Answer Confidence"
- Emergency Level Classifier widget at bottom right:
  - W1 Observation (gray)
  - W2 Advisory (yellow glow)
  - W3 Emergency (orange glow)
  - W4 Regional Crisis (red pulsing glow)
  - CRITICAL (red with animated pulse border)
  - Shows "No active incident detected" in muted text when not triggered

### Top Navigation Bar (full width, above the three columns):
- Left: App logo (small version)
- Center: "PANDORA KNOWLEDGE GUARDIAN" in Orbitron font with subtle cyan text glow
- Right: New Session button (outlined cyan), settings gear icon, small circular avatar placeholder

### Loading / Processing State:
- Full-width thin cyan glowing progress bar at top of page when query is processing
- Step-by-step status indicator in center panel:
  - Step 1: Searching knowledge base...
  - Step 2: Retrieving relevant chunks...
  - Step 3: Generating grounded answer...
  - Each step lights up sequentially with a glowing cyan checkmark when complete

### Mobile Responsive:
- On mobile: single column layout
- Sidebar becomes a slide-up bottom sheet
- Sources panel becomes a collapsible accordion below each answer
- Keep the full bioluminescent theme on mobile

### Micro-interactions & Details:
- Hover on source card: cyan border glow intensifies, card lifts with stronger box-shadow
- Hover on role pill: glow animation preview before selection
- Send button: pulse animation when clicked
- Evidence quality badge: tooltip on hover explaining the quality level in plain language
- Conflicting evidence banner: expandable to show both conflicting source excerpts side by side
- Suggested question chips: hover glow plus slight scale transform (1.03)
- Document upload zone: animated dashed border on hover, full cyan glow fill on drag-over

### Sample Populated State to Show in the Preview:
Show the UI in a state where the user has already asked: "What are the possible causes of the turquoise water color near Awa Reef, and what should guardians do first?"

Answer panel shows:
- A structured response with 4 bullet points listing possible causes: mineral sediment, plankton bloom, chemical release, light reflection
- A yellow warning Conflicting Evidence Detected banner that reads: "Field Note FN-A suggests a natural plankton bloom. Field Note FN-B notes upstream pigment workshop damage. Cause is unconfirmed."
- Evidence quality badge: tilde Provisional Interpretation (amber)
- Emergency level badge: W2 Advisory (yellow glow)

Right panel sources show 3 retrieved cards:
- Card 1: "Pandora Knowledge Corpus" — "Chapter 12 · Page 40" — Relevance 94% — tag: Luminous Shelf — tag: Environmental Incident
- Card 2: "Field Note FN-A, 2026-06-02" — Relevance 87% — badge: Provisional Interpretation
- Card 3: "Field Note FN-B, 2026-06-03" — Relevance 81% — badge: Disputed Report

Confidence Score circular gauge shows 68% in amber.
Emergency Level shows W2 Advisory with yellow glow.

Use Tailwind CSS for all styling. Create glow effects using Tailwind arbitrary values like shadow-[0_0_20px_rgba(0,229,255,0.4)] and shadow-[0_0_30px_rgba(57,255,143,0.3)]. Use lucide-react for all icons. The overall feel should be cinematic, intelligent, and alive — like querying a living ecosystem's memory.
```
